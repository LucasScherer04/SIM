import json
import pytest
from datetime import date, timedelta, datetime
from unittest.mock import patch, MagicMock

from app import database
from app.b3_sync_service import (
    _parse_br_float,
    _is_table_header_row,
    _partition_sheet_into_sections,
    parse_b3_spreadsheet,
    apply_b3_sync,
    ensure_b3_sync_tables,
)
from app.ai_radar_service import (
    _clean_json_markdown,
    generate_portfolio_and_market_radar,
    update_app_settings,
    call_configured_llm,
)
from app.market_service import (
    is_quote_stale,
    get_portfolio_summary,
    OBSOLETE_OR_DELISTED_TICKERS,
)


@pytest.fixture()
def audit_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "audit_test.db")
    monkeypatch.setattr(database, "DB_PATH", db_file)
    database.init_db()
    ensure_b3_sync_tables()
    monkeypatch.setattr("app.market_service.sync_yfinance_quotes_background", lambda: None)
    monkeypatch.setattr("app.b3_sync_service.fetch_macro_indicators", lambda *a, **k: {"usd_brl": 5.0})
    monkeypatch.setattr("app.market_service.fetch_macro_indicators", lambda *a, **k: {"usd_brl": 5.0})
    return db_file


# -----------------------------------------------------------------------------
# 1. Test _parse_br_float (CSV vs XLSX numeric handling)
# -----------------------------------------------------------------------------
def test_parse_br_float_handles_thousands_and_decimals():
    # Brazilian thousand separator with dot
    assert _parse_br_float("1.000") == 1000.0
    assert _parse_br_float("25.000") == 25000.0
    assert _parse_br_float("100.000") == 100000.0
    assert _parse_br_float("1.000.000") == 1000000.0
    assert _parse_br_float("R$ 1.000") == 1000.0
    assert _parse_br_float(" 1.000 ") == 1000.0

    # Brazilian thousand + decimal comma
    assert _parse_br_float("1.000,50") == 1000.50
    assert _parse_br_float("1.234,56") == 1234.56
    assert _parse_br_float("1000,50") == 1000.50

    # Decimal without thousands
    assert _parse_br_float("0,18") == 0.18
    assert _parse_br_float("0.123") == 0.123
    assert _parse_br_float("1.50") == 1.50
    assert _parse_br_float("1.5") == 1.5

    # Plain integers and edge cases
    assert _parse_br_float("100") == 100.0
    assert _parse_br_float(1000) == 1000.0
    assert _parse_br_float(1000.5) == 1000.5
    assert _parse_br_float("-") == 0.0
    assert _parse_br_float(None) == 0.0


# -----------------------------------------------------------------------------
# 2. Test AI radar error propagation and JSON markdown extraction
# -----------------------------------------------------------------------------
def test_clean_json_markdown_handles_llm_code_fences():
    # Standard markdown fence
    s1 = "```json\n{\"executive_briefing\": \"Teste\", \"action_recommendations\": [\"Aporte\"]}\n```"
    assert json.loads(_clean_json_markdown(s1))["executive_briefing"] == "Teste"

    # Fence without 'json' tag
    s2 = "```\n{\"executive_briefing\": \"Sem tag\", \"action_recommendations\": []}\n```"
    assert json.loads(_clean_json_markdown(s2))["executive_briefing"] == "Sem tag"

    # Conversational text before and after (common in Groq/OpenAI)
    s3 = (
        "Aqui está o diagnóstico solicitado:\n"
        "```json\n"
        "{\"executive_briefing\": \"Bom desempenho\", \"action_recommendations\": [\"Rebalancear\"]}\n"
        "```\n"
        "Qualquer dúvida estou à disposição!"
    )
    res3 = json.loads(_clean_json_markdown(s3))
    assert res3["executive_briefing"] == "Bom desempenho"
    assert res3["action_recommendations"] == ["Rebalancear"]

    # Raw JSON without fences but with leading/trailing text
    s4 = "Parecer: {\"executive_briefing\": \"Direto\", \"action_recommendations\": []} Fim."
    assert json.loads(_clean_json_markdown(s4))["executive_briefing"] == "Direto"


def test_ai_radar_propagates_error_instead_of_silent_pass(audit_db):
    update_app_settings({"ai_provider": "OPENAI", "ai_api_key": "sk-invalid-key-test"}, user_id=1)

    # Simula erro de chave não autorizada (401)
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = '{"error": {"message": "Incorrect API key provided"}}'
        mock_post.return_value = mock_resp

        radar = generate_portfolio_and_market_radar(force_refresh=True, user_id=1)

    assert radar["ai_generated"] is False
    assert "401" in radar["ai_error"]
    assert "OPENAI" in radar["ai_error"] or "inválida" in radar["ai_error"].lower()
    assert radar["executive_briefing"]  # Conteúdo alternativo nativo gerado
    assert "Contingência" in radar["ai_provider_used"]


# -----------------------------------------------------------------------------
# 3. Test obsolete tickers removed from catalog and stale quote detection
# -----------------------------------------------------------------------------
def test_obsolete_tickers_not_in_catalog_and_stale_detection(audit_db):
    conn = database.get_conn()
    rows = conn.execute("SELECT ticker FROM assets_catalog").fetchall()
    tickers = {r["ticker"].upper() for r in rows}
    conn.close()

    for obsolete in ("CPLE6", "ELET3", "BCFF11", "IRDM11"):
        assert obsolete not in tickers, f"{obsolete} não deveria constar no catálogo ativo!"
        assert obsolete in OBSOLETE_OR_DELISTED_TICKERS

    # Test is_quote_stale
    now = datetime.now()
    fresh_time = now.strftime("%Y-%m-%d %H:%M:%S")
    stale_time = (now - timedelta(hours=30)).strftime("%Y-%m-%d %H:%M:%S")

    assert is_quote_stale("") is True
    assert is_quote_stale(None) is True
    assert is_quote_stale(stale_time, max_age_hours=24) is True
    assert is_quote_stale(fresh_time, max_age_hours=24) is False


# -----------------------------------------------------------------------------
# 4. Test robust spreadsheet section detection
# -----------------------------------------------------------------------------
def test_spreadsheet_section_detection_resilient_to_keywords():
    # Cabeçalho legítimo
    header = ["Produto", "Instituição", "Conta", "Código de Negociação", "CNPJ da Empresa", "Tipo", "Quantidade", "Preço de Fechamento", "Valor Atualizado"]
    assert _is_table_header_row(header) is True

    # Linha de dados contendo palavras como 'Produto', 'Valor' e números
    data_row = [
        "CDB BANCO C6 - Produto Renda Fixa",
        "NU INVESTIMENTOS S.A.",
        "BANCO C6",
        "CDB123",
        "DI",
        "01/10/2024",
        "01/10/2027",
        "100",
        "133,16",
        "Valor Atualizado 133,16",
    ]
    assert _is_table_header_row(data_row) is False

    # Planilha com dados que contêm palavras-chave na descrição
    csv_text = """Produto;Instituição;Conta;Código de Negociação;CNPJ da Empresa;Tipo;Quantidade;Preço de Fechamento;Valor Atualizado
ITUB4 - Produto de Alto Valor e Liquidez;NU INVEST;1;ITUB4;60872504000123;PN;10;35,00;350,00
BBDC4 - Ativo com Preço Atraente;NU INVEST;1;BBDC4;60746948000112;PN;20;15,00;300,00
"""
    res = parse_b3_spreadsheet(csv_text.encode("utf-8"), "carteira.csv")
    assert len(res["positions"]) == 2
    assert res["positions"][0]["ticker"] == "ITUB4"
    assert res["positions"][1]["ticker"] == "BBDC4"


# -----------------------------------------------------------------------------
# 5. Test dollar realized profit uses historical fx_rate (IR rule)
# -----------------------------------------------------------------------------
def test_dollar_realized_profit_uses_historical_fx_rate(audit_db):
    conn = database.get_conn()
    cur = conn.cursor()

    # Compra de 10 ações a $100 com câmbio histórico de R$ 5,00 no dia da compra (custo total = R$ 5.000)
    cur.execute("""
        INSERT INTO transactions (user_id, tx_date, ticker, asset_class, tx_type, quantity, unit_price, fees, currency, fx_rate, broker)
        VALUES (1, '2026-01-10', 'NVDA', 'STOCK_US', 'BUY', 10, 100.0, 0.0, 'USD', 5.00, 'Avenue')
    """)

    # Venda de 5 ações a $120 com câmbio histórico de R$ 5,50 no dia da venda (receita = $600 * 5,50 = R$ 3.300)
    # Custo de aquisição da parcela vendida: 5 * $100 * 5,00 = R$ 2.500
    # Lucro Realizado IR em BRL: R$ 3.300 - R$ 2.500 = R$ 800,00
    cur.execute("""
        INSERT INTO transactions (user_id, tx_date, ticker, asset_class, tx_type, quantity, unit_price, fees, currency, fx_rate, broker)
        VALUES (1, '2026-03-15', 'NVDA', 'STOCK_US', 'SELL', 5, 120.0, 0.0, 'USD', 5.50, 'Avenue')
    """)
    conn.commit()
    conn.close()

    # Câmbio atual hoje é R$ 5,00 (mockado).
    # Se o cálculo usasse o câmbio de hoje, o lucro seria ($120 - $100) * 5 * 5.00 = R$ 500,00 (ERRADO).
    # Com a apuração exata do IR, deve ser R$ 800,00 (CERTO).
    summary = get_portfolio_summary(user_id=1)
    kpis = summary["kpis"]
    assert kpis["realized_profit_brl"] == pytest.approx(800.00, abs=0.01)


# -----------------------------------------------------------------------------
# 6. Test fixed income: identical CDBs in different brokers are not merged
# -----------------------------------------------------------------------------
def test_fixed_income_distinct_brokers_are_not_merged(audit_db):
    cdb_nu = {
        "title_name": "CDB Banco C6 110% CDI",
        "issuer": "Banco C6 S.A.",
        "asset_class": "RENDA_FIXA",
        "indexer": "CDI",
        "rate_value": 110.0,
        "invested_amount": 5000.0,
        "market_value": 5200.0,
        "market_net_value": 5150.0,
        "market_value_date": "2026-10-30",
        "start_date": "2026-01-15",
        "maturity_date": "2027-01-15",
        "daily_liquidity": 0,
        "tax_exempt": 0,
        "broker": "Nu Invest",
        "has_cost_amount": True,
        "has_start_date": True,
    }

    cdb_xp = {
        "title_name": "CDB Banco C6 110% CDI",
        "issuer": "Banco C6 S.A.",
        "asset_class": "RENDA_FIXA",
        "indexer": "CDI",
        "rate_value": 110.0,
        "invested_amount": 10000.0,
        "market_value": 10400.0,
        "market_net_value": 10300.0,
        "market_value_date": "2026-10-30",
        "start_date": "2026-01-15",
        "maturity_date": "2027-01-15",
        "daily_liquidity": 0,
        "tax_exempt": 0,
        "broker": "XP Investimentos",
        "has_cost_amount": True,
        "has_start_date": True,
    }

    # Importa primeira aplicação via Nu Invest
    apply_b3_sync({"fixed_income": [cdb_nu]}, "MERGE", user_id=1)

    # Importa segunda aplicação via XP Investimentos
    apply_b3_sync({"fixed_income": [cdb_xp]}, "MERGE", user_id=1)

    conn = database.get_conn()
    rows = conn.execute("SELECT * FROM fixed_income WHERE user_id = 1 ORDER BY id ASC").fetchall()
    conn.close()

    # Ambas devem existir separadamente!
    assert len(rows) == 2, "As aplicações em corretoras distintas não devem ser fundidas!"
    brokers = {r["broker"] for r in rows}
    assert brokers == {"Nu Invest", "XP Investimentos"}
    assert rows[0]["invested_amount"] == 5000.0
    assert rows[1]["invested_amount"] == 10000.0

    # Re-importação da aplicação da Nu Invest atualiza a mesma sem duplicar
    cdb_nu_updated = dict(cdb_nu, market_value=5300.0)
    apply_b3_sync({"fixed_income": [cdb_nu_updated]}, "MERGE", user_id=1)

    conn = database.get_conn()
    rows_after = conn.execute("SELECT * FROM fixed_income WHERE user_id = 1 ORDER BY id ASC").fetchall()
    conn.close()

    assert len(rows_after) == 2, "Re-sincronizar a mesma corretora deve atualizar sem criar duplicata!"
    nu_row = next(r for r in rows_after if r["broker"] == "Nu Invest")
    assert nu_row["market_value"] == 5300.0
