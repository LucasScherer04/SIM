"""
Testes automatizados da Etapa 3 — Dados de mercado, histórico e notícias.

Cobre:
1. Adaptador de histórico e cotação (`YahooFinanceAdapter`):
   - Persistência em `market_history_cache` com fonte, moeda e `updated_at`.
   - Fallback para cache SQLite (`data_state="CACHED"`) quando o provedor falha.
   - Estado explícito `UNAVAILABLE` com `points=[]` e `is_synthetic=False` quando não há rede nem cache (proibição de dados inventados).
2. Estatísticas históricas (`compute_historical_stats`) e comparação com benchmark (`compute_benchmark_comparison`):
   - Mínima, máxima, média, mediana, distância da média, posição na faixa e rotulagem `CALCULO_SIM`.
   - Comparação com Ibovespa (`^BVSP`) para ativos BR e S&P 500 (`^GSPC`) para `STOCK_US`.
3. Adaptador de câmbio e macro (`AwesomeBcbMacroAdapter`):
   - Primário AwesomeAPI + BCB SGS e persistência em `macro_indicators_cache`.
   - Fallback cambial para BCB PTAX (SGS 1) quando AwesomeAPI falha.
   - Fallback para cache SQLite quando toda a rede falha, sem bloquear a carteira.
4. Adaptador de notícias (`GoogleNewsRssAdapter` / `fetch_asset_news`):
   - Extração de título, fonte, data, link e resumo com persistência em `asset_news_cache`.
   - Fallback para cache SQLite quando o RSS falha.
   - Retorno vazio honesto (`items=[]`, `is_synthetic=False`) sem manchetes fabricadas quando não há cache.
5. Endpoint `/api/asset/{ticker}` fim a fim para ativos BR (`PETR4`, `HGLG11`) e EUA (`AAPL`).
"""

from datetime import datetime
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import database, intelligence_service, main, market_adapters, market_service


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """Cria um banco SQLite temporário isolado para cada teste."""
    db_file = tmp_path / "test_sim_stage3.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    market_service.MACRO_CACHE["_ts"] = 0
    database.init_db()
    return db_file


def _make_fake_df(rows):
    """Helper para montar DataFrame no formato retornado pelo yfinance.Ticker.history."""
    idx = pd.to_datetime([r[0] for r in rows])
    data = {
        "Open": [r[1] for r in rows],
        "High": [r[2] for r in rows],
        "Low": [r[3] for r in rows],
        "Close": [r[4] for r in rows],
        "Volume": [r[5] for r in rows],
    }
    return pd.DataFrame(data, index=idx)


class TestYahooFinanceAdapterAndHistoryCache:
    def test_live_fetch_persists_to_sqlite_and_returns_cached_on_failure(self, isolated_db, monkeypatch):
        adapter = market_adapters.YahooFinanceAdapter()

        fake_df = _make_fake_df([
            ("2026-01-02", 35.0, 36.2, 34.8, 36.0, 100000),
            ("2026-01-03", 36.0, 37.5, 35.9, 37.0, 120000),
            ("2026-01-04", 37.0, 38.2, 36.5, 38.0, 140000),
            ("2026-01-05", 38.0, 39.1, 37.8, 39.0, 110000),
        ])

        class FakeTickerOK:
            def __init__(self, sym):
                self.sym = sym

            def history(self, period="1y", interval="1d"):
                return fake_df

        monkeypatch.setattr(market_adapters.yf, "Ticker", FakeTickerOK)

        res_live = adapter.get_history("PETR4", "ACAO_BR", "1Y", currency="BRL", ttl_seconds=0)
        assert res_live["data_state"] == "LIVE"
        assert res_live["is_synthetic"] is False
        assert res_live["currency"] == "BRL"
        assert "Yahoo Finance" in res_live["source"]
        assert res_live["updated_at"] != ""
        assert len(res_live["points"]) == 4
        assert res_live["points"][0]["price"] == 36.0
        assert res_live["points"][-1]["price"] == 39.0

        # Agora simula queda total do Yahoo Finance: deve servir o cache SQLite sem inventar dados
        class FakeTickerFail:
            def __init__(self, sym):
                raise RuntimeError("Yahoo Finance indisponível")

        monkeypatch.setattr(market_adapters.yf, "Ticker", FakeTickerFail)

        res_cached = adapter.get_history("PETR4", "ACAO_BR", "1Y", currency="BRL", ttl_seconds=-1)
        assert res_cached["data_state"] == "CACHED"
        assert res_cached["is_synthetic"] is False
        assert res_cached["is_fresh"] is False
        assert res_cached["warning"] != ""
        assert len(res_cached["points"]) == 4
        assert res_cached["points"][-1]["price"] == 39.0

    def test_unavailable_when_no_network_and_no_cache_never_invents_series(self, isolated_db, monkeypatch):
        adapter = market_adapters.YahooFinanceAdapter()

        class FakeTickerFail:
            def __init__(self, sym):
                raise RuntimeError("Sem conexão")

        monkeypatch.setattr(market_adapters.yf, "Ticker", FakeTickerFail)

        res = adapter.get_history("ATIVO_SEM_CACHE", "ACAO_BR", "1Y", currency="BRL", ttl_seconds=0)
        assert res["data_state"] == "UNAVAILABLE"
        assert res["is_synthetic"] is False
        assert res["points"] == []
        assert res["warning"] != ""


class TestHistoricalStatsAndBenchmark:
    def test_compute_historical_stats_calculates_exact_metrics(self):
        points = [
            {"label": "01/01/2026", "price": 10.0},
            {"label": "02/01/2026", "price": 20.0},
            {"label": "03/01/2026", "price": 30.0},
        ]
        stats = market_adapters.compute_historical_stats(points, current_price=24.0, currency="BRL")
        assert stats["available"] is True
        assert stats["kind"] == "CALCULO_SIM"
        assert stats["min_price"] == 10.0
        assert stats["max_price"] == 30.0
        assert stats["avg_price"] == 20.0
        assert stats["median_price"] == 20.0
        # (24 - 20) / 20 = +20%
        assert stats["distance_from_avg_pct"] == 20.0
        # (24 - 10) / (30 - 10) = 14 / 20 = 70%
        assert stats["position_in_range_pct"] == 70.0

    def test_compute_benchmark_comparison_br_and_us(self, isolated_db, monkeypatch):
        adapter = market_adapters.YahooFinanceAdapter()

        bench_df = _make_fake_df([
            ("2026-01-02", 100.0, 101.0, 99.0, 100.0, 1000),
            ("2026-01-03", 100.0, 106.0, 100.0, 105.0, 1000),
            ("2026-01-04", 105.0, 111.0, 104.0, 110.0, 1000),
        ])

        class FakeTickerBench:
            def __init__(self, sym):
                self.sym = sym

            def history(self, period="1y", interval="1d"):
                return bench_df

        monkeypatch.setattr(market_adapters.yf, "Ticker", FakeTickerBench)

        asset_pts = [
            {"label": "02/01/2026", "price": 50.0},
            {"label": "03/01/2026", "price": 55.0},
            {"label": "04/01/2026", "price": 60.0},
        ]
        # Ativo subiu +20%, benchmark subiu +10% -> diferença relativa = +10 p.p.
        comp_br = market_adapters.compute_benchmark_comparison(adapter, asset_pts, "ACAO_BR", "1Y")
        assert comp_br["available"] is True
        assert comp_br["benchmark_symbol"] == "^BVSP"
        assert comp_br["asset_return_pct"] == 20.0
        assert comp_br["benchmark_return_pct"] == 10.0
        assert comp_br["relative_diff_pp"] == 10.0
        assert comp_br["kind"] == "CALCULO_SIM"

        comp_us = market_adapters.compute_benchmark_comparison(adapter, asset_pts, "STOCK_US", "1Y")
        assert comp_us["available"] is True
        assert comp_us["benchmark_symbol"] == "^GSPC"


class TestAwesomeBcbMacroAdapter:
    def test_macro_fallback_to_bcb_ptax_and_sqlite_cache(self, isolated_db, monkeypatch):
        adapter = market_adapters.AwesomeBcbMacroAdapter()

        class FakeResp:
            def __init__(self, status_code, payload):
                self.status_code = status_code
                self._payload = payload

            def json(self):
                return self._payload

        def fake_get_ptax_fallback(url, timeout=4, headers=None):
            if "awesomeapi" in url:
                raise RuntimeError("AwesomeAPI timeout")
            if "bcdata.sgs.1/" in url:
                return FakeResp(200, [{"data": "06/11/2026", "valor": "5,81"}])
            if "bcdata.sgs.432/" in url:
                return FakeResp(200, [{"data": "06/11/2026", "valor": "11,25"}])
            if "bcdata.sgs.4389/" in url:
                return FakeResp(200, [{"data": "06/11/2026", "valor": "11,15"}])
            if "bcdata.sgs.13522/" in url:
                return FakeResp(200, [{"data": "06/11/2026", "valor": "4,50"}])
            return FakeResp(500, {})

        monkeypatch.setattr(market_adapters.requests, "get", fake_get_ptax_fallback)

        cache_live = {}
        res = adapter.refresh_macro(cache_live)
        assert res["usd_brl"] == 5.81
        assert res["selic"] == 11.25
        assert res["cdi"] == 11.15
        assert res["ipca_12m"] == 4.50
        assert "Banco Central PTAX" in res["sources"]["usd_brl"]["source"]
        assert res["sources"]["usd_brl"]["data_state"] == "LIVE"

        # Simula queda total da internet: deve carregar os valores persistidos no SQLite
        def fake_get_offline(url, timeout=4, headers=None):
            raise RuntimeError("Offline total")

        monkeypatch.setattr(market_adapters.requests, "get", fake_get_offline)

        cache_offline = {}
        res_offline = adapter.refresh_macro(cache_offline)
        assert res_offline["usd_brl"] == 5.81
        assert res_offline["selic"] == 11.25
        assert res_offline["sources"]["usd_brl"]["data_state"] == "CACHED"


class TestGoogleNewsRssAdapter:
    def test_rss_parses_persists_and_falls_back_to_cache_without_fake_news(self, isolated_db, monkeypatch):
        now_str_rss = datetime.now().strftime("%Y-%m-%d %H:%M")
        rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>Petrobras anuncia lucro recorde e dividendos - Valor Econômico</title>
              <link>https://example.com/petr4-lucro</link>
              <pubDate>{now_str_rss}</pubDate>
              <description>&lt;p&gt;Resultado trimestral superou consenso do mercado.&lt;/p&gt;</description>
              <source>Valor Econômico</source>
            </item>
          </channel>
        </rss>
        """.strip().encode("utf-8")

        class FakeResp:
            def __init__(self, status_code, content):
                self.status_code = status_code
                self.content = content

        monkeypatch.setattr(
            market_adapters.requests,
            "get",
            lambda url, headers=None, timeout=5: FakeResp(200, rss_xml),
        )

        news_live = intelligence_service.fetch_asset_news("PETR4", ttl_seconds=0)
        assert news_live["data_state"] == "LIVE"
        assert news_live["is_synthetic"] is False
        assert news_live["updated_at"] != ""
        assert len(news_live["items"]) == 1
        item = news_live["items"][0]
        assert item["title"] == "Petrobras anuncia lucro recorde e dividendos"
        assert item["source"] == "Valor Econômico"
        assert item["link"] == "https://example.com/petr4-lucro"
        assert "Resultado trimestral" in item["summary"]
        assert item["sentiment"] == "POSITIVO"

        # Simula queda de rede: deve retornar notícia em cache com data_state="CACHED" e warning
        def raise_offline(url, headers=None, timeout=5):
            raise RuntimeError("Sem internet")

        monkeypatch.setattr(market_adapters.requests, "get", raise_offline)

        news_cached = intelligence_service.fetch_asset_news("PETR4", ttl_seconds=-1)
        assert news_cached["data_state"] == "CACHED"
        assert news_cached["is_synthetic"] is False
        assert news_cached["warning"] != ""
        assert len(news_cached["items"]) == 1
        assert news_cached["items"][0]["title"] == "Petrobras anuncia lucro recorde e dividendos"

        # Ativo sem cache e sem rede: deve retornar lista vazia, NUNCA fabricar manchetes falsas
        news_empty = intelligence_service.fetch_asset_news("ZZZZ4", ttl_seconds=0)
        assert news_empty["data_state"] == "UNAVAILABLE"
        assert news_empty["is_synthetic"] is False
        assert news_empty["items"] == []


class TestAssetDetailEndpointEndToEnd:
    def test_asset_detail_endpoint_works_offline_for_br_and_us_assets(self, isolated_db, monkeypatch):
        # Simula provedores externos todos offline para garantir que a consulta local jamais trava
        class FakeTickerOffline:
            def __init__(self, sym):
                raise RuntimeError("Yahoo offline")

        def fake_requests_offline(*args, **kwargs):
            raise RuntimeError("Network offline")

        monkeypatch.setattr(market_adapters.yf, "Ticker", FakeTickerOffline)
        monkeypatch.setattr(market_adapters.requests, "get", fake_requests_offline)

        client = TestClient(main.app)

        for ticker, expected_curr, expected_mkt in [
            ("PETR4", "BRL", "BR"),
            ("HGLG11", "BRL", "BR"),
            ("AAPL", "USD", "US"),
        ]:
            resp = client.get(f"/api/asset/{ticker}?period=1Y")
            assert resp.status_code == 200
            payload = resp.json()
            assert payload["asset"]["ticker"] == ticker
            assert payload["asset"]["currency"] == expected_curr
            assert payload["quote_meta"]["currency"] == expected_curr
            assert payload["quote_meta"]["market"] == expected_mkt
            assert payload["quote_meta"]["source"]
            assert payload["history_meta"]["is_synthetic"] is False
            assert payload["history_meta"]["data_state"] == "UNAVAILABLE"
            assert payload["points"] == []
            assert "historical_stats" in payload
            assert "benchmark_comparison" in payload
            assert payload["news"]["is_synthetic"] is False
            assert payload["news"]["items"] == []
