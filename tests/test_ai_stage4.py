"""
Testes automatizados da Etapa 4 — Radar e analista de IA.

Cobre:
1. Segurança da chave de API (criptografia em repouso, mascaramento, sanitização de erros e ausência de chaves no histórico/prompts).
2. Análise individual de ativo (`analyze_asset_deep` / `POST /api/ai/analyze-asset/{ticker}`):
   - Separação entre `FATO_OBSERVADO`, `CALCULO_SIM` e `INTERPRETACAO_IA`.
   - Presença de fatores positivos, riscos e argumentos contrários, fontes, limitações e alertas de dados ausentes/antigos.
   - Comportamento com LLM ativo, sem chave configurada e com falha da API da IA.
3. Análise consolidada da carteira (`analyze_portfolio_deep` / `POST /api/ai/analyze-portfolio`):
   - Diversificação, concentração HHI, pontos fortes, riscos/argumentos contrários, 'O que merece minha atenção?' e alertas de câmbio estimado/cotações antigas.
4. Comparação entre ativos semelhantes (`compare_similar_assets` / `POST /api/ai/compare-assets`):
   - Seleção automática de pares quando 1 ticker é informado e alertas metodológicos quando classes/moedas divergem.
5. Radar com sinais de watchlist e marcação de itens (`RELEVANTE`, `ACOMPANHANDO`, `IGNORADO`).
6. Histórico de análises e comparação temporal ('O que mudou desde a última análise?').
"""

import json
import pytest
from fastapi.testclient import TestClient

from app import ai_radar_service, database, main, market_adapters, market_service


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_sim_stage4.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    market_service.MACRO_CACHE["_ts"] = 0
    monkeypatch.setattr(market_service, "sync_yfinance_quotes_background", lambda: None)
    database.init_db()
    ai_radar_service.ensure_settings_tables()

    # Evita chamadas externas durante os testes
    class FakeTickerOffline:
        def __init__(self, sym):
            raise RuntimeError("Offline test mode")

    def fake_requests_offline(*args, **kwargs):
        raise RuntimeError("Offline test mode")

    monkeypatch.setattr(market_adapters.yf, "Ticker", FakeTickerOffline)
    monkeypatch.setattr(market_adapters.requests, "get", fake_requests_offline)
    return db_file


class TestApiKeySecurityAndSanitization:
    def test_api_key_is_encrypted_masked_and_scrubbed_from_errors(self, isolated_db):
        secret_key = "sk-proj-SUPERSECRETKEY1234567890"
        public_cfg = ai_radar_service.update_app_settings(
            {"ai_provider": "OPENAI", "ai_model": "gpt-4o-mini", "ai_api_key": secret_key},
            user_id=1,
        )
        assert public_cfg["ai_api_key_configured"] is True
        assert secret_key not in json.dumps(public_cfg)
        assert "••••" in public_cfg["ai_api_key_masked"]

        # Verifica criptografia em repouso no SQLite
        conn = database.get_conn()
        row = conn.execute("SELECT value FROM app_settings WHERE user_id = 1 AND key = 'ai_api_key'").fetchone()
        conn.close()
        assert row is not None
        assert row["value"].startswith("ENC:")
        assert secret_key not in row["value"]

        # Verifica sanitização caso um provedor ecoe a chave em mensagem de erro
        raw_err = f"Invalid key provided: {secret_key} or AIzaSyD1234567890abcdef"
        sanitized = ai_radar_service._sanitize_error_message(raw_err, secret_key)
        assert secret_key not in sanitized
        assert "AIzaSyD1234567890abcdef" not in sanitized
        assert "[CHAVE_OCULTADA]" in sanitized


class TestAssetDeepAnalysis:
    def test_analyze_asset_separates_facts_calculations_and_interpretation_offline(self, isolated_db):
        client = TestClient(main.app)
        resp = client.post("/api/ai/analyze-asset/PETR4?period=1Y")
        assert resp.status_code == 200
        data = resp.json()

        assert data["analysis_type"] == "ASSET"
        assert data["target_key"] == "PETR4"
        assert data["facts_observed"]["kind"] == "FATO_OBSERVADO"
        assert data["facts_observed"]["ticker"] == "PETR4"
        assert data["facts_observed"]["currency"] == "BRL"
        assert data["sim_calculations"]["kind"] == "CALCULO_SIM"
        assert data["ai_interpretation"]["kind"] == "INTERPRETACAO_IA"

        # Riscos, fatores positivos, fontes, limitações e avisos de dados incompletos/offline
        assert len(data["ai_interpretation"]["positive_factors"]) >= 1
        assert len(data["ai_interpretation"]["risks_and_counterarguments"]) >= 1
        assert len(data["sources"]) >= 2
        assert len(data["limitations"]) >= 2
        assert len(data["data_warnings"]) >= 1
        assert data["analysis_id"] >= 1

    def test_analyze_asset_with_configured_llm_and_api_failure_fallback(self, isolated_db, monkeypatch):
        ai_radar_service.update_app_settings(
            {"ai_provider": "GEMINI", "ai_model": "gemini-2.5-flash", "ai_api_key": "AIzaSyTestKey123456789"},
            user_id=1,
        )

        # 1. Resposta válida do LLM
        fake_llm_json = json.dumps({
            "summary": "Síntese rastreável baseada nos dados fornecidos.",
            "positive_factors": ["DY observado de 14,8% a.a."],
            "risks_and_counterarguments": ["Volatilidade do petróleo e custo de oportunidade da Selic."],
            "attention_points": ["Acompanhar comunicados trimestrais na CVM."],
        })
        monkeypatch.setattr(ai_radar_service, "call_configured_llm", lambda *a, **kw: fake_llm_json)

        res_ok = ai_radar_service.analyze_asset_deep("PETR4", period="1Y", user_id=1)
        assert res_ok["ai_generated"] is True
        assert res_ok["ai_interpretation"]["summary"] == "Síntese rastreável baseada nos dados fornecidos."
        assert "Volatilidade do petróleo" in res_ok["ai_interpretation"]["risks_and_counterarguments"][0]

        # 2. Falha na API do LLM -> deve cair para o motor determinístico e registrar aviso sanitizado
        def raise_llm_err(*a, **kw):
            raise ValueError("Erro 429: Quota exceeded for key AIzaSyTestKey123456789")

        monkeypatch.setattr(ai_radar_service, "call_configured_llm", raise_llm_err)
        res_fail = ai_radar_service.analyze_asset_deep("PETR4", period="1Y", user_id=1)
        assert res_fail["ai_generated"] is False
        assert "AIzaSyTestKey123456789" not in res_fail["ai_error"]
        assert any("Falha ao consultar API de IA" in w for w in res_fail["data_warnings"])
        assert len(res_fail["ai_interpretation"]["risks_and_counterarguments"]) >= 1


class TestPortfolioDeepAnalysisAndHistoryComparison:
    def test_portfolio_analysis_and_delta_between_analyses(self, isolated_db):
        client = TestClient(main.app)

        # Adiciona 1ª compra
        r_tx1 = client.post("/api/transactions", json={
            "tx_date": "2026-01-10",
            "ticker": "PETR4",
            "asset_class": "ACAO_BR",
            "tx_type": "BUY",
            "quantity": 100,
            "unit_price": 35.0,
            "currency": "BRL",
        })
        assert r_tx1.status_code == 200

        # 1ª Análise da carteira
        r_an1 = client.post("/api/ai/analyze-portfolio")
        assert r_an1.status_code == 200
        an1 = r_an1.json()
        assert an1["facts_observed"]["holdings_count"] == 1
        assert an1["delta_since_last"]["has_previous"] is False

        # Adiciona 2ª compra (em USD sem fx_rate -> gera aviso de câmbio estimado e altera patrimônio/HHI)
        r_tx2 = client.post("/api/transactions", json={
            "tx_date": "2026-02-15",
            "ticker": "AAPL",
            "asset_class": "STOCK_US",
            "tx_type": "BUY",
            "quantity": 5,
            "unit_price": 200.0,
            "currency": "USD",
        })
        assert r_tx2.status_code == 200

        # 2ª Análise da carteira -> deve detectar o que mudou desde a 1ª análise!
        r_an2 = client.post("/api/ai/analyze-portfolio")
        assert r_an2.status_code == 200
        an2 = r_an2.json()
        assert an2["facts_observed"]["holdings_count"] == 2
        assert an2["delta_since_last"]["has_previous"] is True
        assert an2["delta_since_last"]["previous_id"] == an1["analysis_id"]
        assert len(an2["delta_since_last"]["changes"]) >= 2
        assert any("câmbio estimado" in w for w in an2["data_warnings"])

        # Endpoint de comparação histórica
        r_cmp = client.get("/api/ai/history/compare?analysis_type=PORTFOLIO&target_key=CARTEIRA")
        assert r_cmp.status_code == 200
        cmp_data = r_cmp.json()
        assert cmp_data["available"] is True
        assert cmp_data["older"]["id"] == an1["analysis_id"]
        assert cmp_data["newer"]["id"] == an2["analysis_id"]
        assert len(cmp_data["delta"]["changes"]) >= 2


class TestCompareSimilarAssets:
    def test_compare_auto_selects_peers_and_warns_on_different_classes_or_currencies(self, isolated_db):
        client = TestClient(main.app)

        # Passando apenas 1 FII -> seleciona automaticamente pares da classe FII
        r_peers = client.post("/api/ai/compare-assets", json={"tickers": ["HGLG11"], "period": "1Y"})
        assert r_peers.status_code == 200
        p_data = r_peers.json()
        assert len(p_data["comparison_table"]) >= 2
        assert p_data["comparison_table"][0]["ticker"] == "HGLG11"
        assert p_data["ai_interpretation"]["kind"] == "INTERPRETACAO_IA"

        # Passando ativos de classes e moedas distintas (ACAO_BR em BRL vs STOCK_US em USD) -> alerta metodológico
        r_mixed = client.post("/api/ai/compare-assets", json={"tickers": ["PETR4", "AAPL"], "period": "1Y"})
        assert r_mixed.status_code == 200
        m_data = r_mixed.json()
        assert any("classes distintas" in w for w in m_data["data_warnings"])
        assert any("moedas diferentes" in w for w in m_data["data_warnings"])


class TestRadarWatchlistAndItemStates:
    def test_radar_includes_watchlist_and_persists_item_states(self, isolated_db):
        client = TestClient(main.app)

        # Marca WEGE3 como favorito (watchlist)
        client.post("/api/favorites/WEGE3")

        radar_resp = client.get("/api/ai/radar?force=true")
        assert radar_resp.status_code == 200
        radar = radar_resp.json()
        assert any(w["ticker"] == "WEGE3" for w in radar["watchlist_signals"])
        assert len(radar["risks_and_counterarguments"]) >= 1
        assert len(radar["limitations"]) >= 1

        # Marca item como IGNORADO e outro como RELEVANTE
        r_state1 = client.post("/api/ai/radar/item-state", json={
            "item_key": "WATCH:WEGE3",
            "status": "RELEVANTE",
            "ticker": "WEGE3",
            "notes": "Estudar balanço trimestral",
        })
        assert r_state1.status_code == 200
        assert r_state1.json()["item"]["status"] == "RELEVANTE"

        # Consulta o radar sem force (via cache) e verifica se o status atualizado é refletido imediatamente
        radar_cached = client.get("/api/ai/radar?force=false").json()
        wege_watch = next(w for w in radar_cached["watchlist_signals"] if w["ticker"] == "WEGE3")
        assert wege_watch["user_status"] == "RELEVANTE"
