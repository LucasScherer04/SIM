"""
Testes de regressao da Etapa 1: fixam o comportamento ATUAL dos calculos da carteira
(preco medio, vendas, resultado realizado, moedas, proventos e renda fixa).

Rede e banco real nunca sao usados: o banco e temporario e as funcoes de mercado sao mockadas.
Casos marcados como "CARACTERIZACAO" descrevem comportamento atual que o diagnostico
(docs/diagnostico-sim.md) classifica como questionavel; eles NAO endossam a regra.
"""
from datetime import date, timedelta

import pytest

from app import database, market_service

USD_BRL = 7.0
MACRO = {"usd_brl": USD_BRL, "cdi": 10.0, "selic": 10.5, "ipca_12m": 4.0}


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(market_service, "fetch_macro_indicators", lambda force=False: dict(MACRO))
    monkeypatch.setattr(market_service, "sync_yfinance_quotes_background", lambda: None)
    database.init_db()
    return database


def _catalog(ticker, cls, price, currency="BRL"):
    conn = database.get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO assets_catalog (ticker, name, asset_class, currency, last_price, updated_at) "
        "VALUES (?, ?, ?, ?, ?, '2026-01-01 10:00:00')",
        (ticker, ticker, cls, currency, price),
    )
    conn.commit()
    conn.close()


def _tx(date_, ticker, cls, typ, qty, price, fees=0.0, currency="BRL", fx=1.0):
    conn = database.get_conn()
    conn.execute(
        "INSERT INTO transactions (user_id, tx_date, ticker, asset_class, tx_type, quantity, unit_price, "
        "fees, currency, fx_rate, notes) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'negociacao')",
        (date_, ticker, cls, typ, qty, price, fees, currency, fx),
    )
    conn.commit()
    conn.close()


def _pos(summary, ticker):
    return next((p for p in summary["positions"] if p["ticker"] == ticker), None)


# ---------------------------------------------------------------- Renda variavel BRL

def test_compras_preco_medio_inclui_taxas(db):
    _catalog("ITUB4", "ACAO_BR", 40.0)
    _tx("2024-01-02", "ITUB4", "ACAO_BR", "BUY", 10, 30.0, fees=5.0)
    _tx("2024-02-02", "ITUB4", "ACAO_BR", "BUY", 10, 40.0, fees=5.0)

    s = market_service.get_portfolio_summary()
    p = _pos(s, "ITUB4")

    # PM = (300 + 5 + 400 + 5) / 20
    assert p["quantity"] == 20
    assert p["avg_price"] == pytest.approx(35.5)
    assert p["invested_brl"] == pytest.approx(710.0)
    assert p["current_brl"] == pytest.approx(800.0)
    assert p["profit_brl"] == pytest.approx(90.0)
    assert s["kpis"]["realized_profit_brl"] == 0


def test_venda_parcial_mantem_pm_e_calcula_realizado_com_taxas(db):
    _catalog("ITUB4", "ACAO_BR", 40.0)
    _tx("2024-01-02", "ITUB4", "ACAO_BR", "BUY", 10, 30.0, fees=5.0)
    _tx("2024-02-02", "ITUB4", "ACAO_BR", "BUY", 10, 40.0, fees=5.0)
    _tx("2024-03-02", "ITUB4", "ACAO_BR", "SELL", 5, 50.0, fees=2.0)

    s = market_service.get_portfolio_summary()
    p = _pos(s, "ITUB4")

    assert p["quantity"] == 15
    assert p["avg_price"] == pytest.approx(35.5)  # venda nao altera o PM
    # (50 - 35.5) * 5 - 2
    assert s["kpis"]["realized_profit_brl"] == pytest.approx(70.5)


def test_venda_total_zera_posicao_e_recompra_reinicia_pm(db):
    _catalog("ITUB4", "ACAO_BR", 40.0)
    _tx("2024-01-02", "ITUB4", "ACAO_BR", "BUY", 10, 30.0)
    _tx("2024-02-02", "ITUB4", "ACAO_BR", "SELL", 10, 20.0)

    s = market_service.get_portfolio_summary()
    assert _pos(s, "ITUB4") is None
    assert s["kpis"]["realized_profit_brl"] == pytest.approx(-100.0)

    _tx("2024-03-02", "ITUB4", "ACAO_BR", "BUY", 4, 50.0)
    s = market_service.get_portfolio_summary()
    assert _pos(s, "ITUB4")["avg_price"] == pytest.approx(50.0)  # PM antigo descartado


def test_caracterizacao_venda_acima_da_quantidade_zera_sem_erro(db):
    # CARACTERIZACAO: nao ha validacao de venda a descoberto; a posicao e limitada a zero
    # e o resultado realizado considera a quantidade vendida inteira.
    _catalog("ITUB4", "ACAO_BR", 40.0)
    _tx("2024-01-02", "ITUB4", "ACAO_BR", "BUY", 10, 30.0)
    _tx("2024-02-02", "ITUB4", "ACAO_BR", "SELL", 15, 40.0)

    s = market_service.get_portfolio_summary()
    assert _pos(s, "ITUB4") is None
    assert s["kpis"]["realized_profit_brl"] == pytest.approx(150.0)  # (40-30)*15


def test_aliases_compra_venda_em_portugues(db):
    _catalog("ITUB4", "ACAO_BR", 40.0)
    _tx("2024-01-02", "ITUB4", "ACAO_BR", "COMPRA", 10, 30.0)
    _tx("2024-02-02", "ITUB4", "ACAO_BR", "VENDA", 4, 40.0)

    s = market_service.get_portfolio_summary()
    assert _pos(s, "ITUB4")["quantity"] == 6
    assert s["kpis"]["realized_profit_brl"] == pytest.approx(40.0)


def test_ticker_e_isolado_por_usuario(db):
    _catalog("ITUB4", "ACAO_BR", 40.0)
    _tx("2024-01-02", "ITUB4", "ACAO_BR", "BUY", 10, 30.0)
    s2 = market_service.get_portfolio_summary(user_id=2)
    assert s2["positions"] == []
    assert s2["kpis"]["total_current_brl"] == 0


# ---------------------------------------------------------------- Moedas (USD)

def _usd_setup():
    _catalog("AAPL", "STOCK_US", 130.0, currency="USD")
    _tx("2024-01-02", "AAPL", "STOCK_US", "BUY", 10, 100.0, currency="USD", fx=5.0)
    _tx("2024-02-02", "AAPL", "STOCK_US", "BUY", 10, 120.0, currency="USD", fx=6.0)


def test_usd_preco_medio_nativo_e_cambio_medio_ponderado(db):
    _usd_setup()
    p = _pos(market_service.get_portfolio_summary(), "AAPL")

    assert p["quantity"] == 20
    assert p["avg_price"] == pytest.approx(110.0)  # em USD
    # custo em BRL: 1000*5 + 1200*6 = 12200 -> cambio medio = 12200 / (20*110)
    assert p["avg_fx"] == pytest.approx(12200.0 / 2200.0)
    assert p["currency"] == "USD"


def test_usd_venda_usa_cambio_da_venda_menos_custo_historico_em_brl(db):
    _usd_setup()
    _tx("2024-03-02", "AAPL", "STOCK_US", "SELL", 10, 130.0, fees=10.0, currency="USD", fx=6.5)

    s = market_service.get_portfolio_summary()
    # recebido: (130*10 - 10) * 6.5 = 8385 ; custo vendido: 12200 * 10/20 = 6100
    assert s["kpis"]["realized_profit_brl"] == pytest.approx(2285.0)
    assert _pos(s, "AAPL")["quantity"] == 10


def test_caracterizacao_usd_posicao_aberta_usa_cambio_atual_nos_dois_lados(db):
    # CARACTERIZACAO: invested_brl = qtd * PM_usd * cambio ATUAL (e nao o custo historico em BRL).
    # Logo o lucro em BRL de um ativo em USD ignora o efeito cambial desde a compra.
    _usd_setup()
    p = _pos(market_service.get_portfolio_summary(), "AAPL")

    assert p["invested_brl"] == pytest.approx(20 * 110.0 * USD_BRL)  # 15400, nao 12200
    assert p["current_brl"] == pytest.approx(20 * 130.0 * USD_BRL)
    assert p["profit_brl"] == pytest.approx(20 * 20.0 * USD_BRL)


def test_total_em_usd_usa_cambio_atual(db):
    _usd_setup()
    k = market_service.get_portfolio_summary()["kpis"]
    assert k["total_current_usd"] == pytest.approx(k["total_current_brl"] / USD_BRL, abs=0.01)


# ---------------------------------------------------------------- Proventos

def test_proventos_somam_total_amount(db):
    conn = database.get_conn()
    for d, t, aps, q in [("2024-05-10", "HGLG11", 1.10, 10), ("2024-06-10", "HGLG11", 1.20, 10)]:
        conn.execute(
            "INSERT INTO dividends_received (user_id, pay_date, ticker, amount_per_share, shares_qty, total_amount) "
            "VALUES (1, ?, ?, ?, ?, ?)",
            (d, t, aps, q, round(aps * q, 2)),
        )
    conn.commit()
    conn.close()

    s = market_service.get_portfolio_summary()
    assert s["kpis"]["total_dividends_brl"] == pytest.approx(23.0)
    assert len(s["dividends"]) == 2


def test_caracterizacao_provento_em_usd_e_somado_sem_conversao(db):
    # CARACTERIZACAO (problema comprovado): total_dividends_brl soma total_amount sem converter
    # moeda; um provento de US$ 10 entra como R$ 10.
    conn = database.get_conn()
    conn.execute(
        "INSERT INTO dividends_received (user_id, pay_date, ticker, amount_per_share, shares_qty, total_amount, currency) "
        "VALUES (1, '2024-05-10', 'AAPL', 1.0, 10, 10.0, 'USD')"
    )
    conn.commit()
    conn.close()

    assert market_service.get_portfolio_summary()["kpis"]["total_dividends_brl"] == pytest.approx(10.0)


# ---------------------------------------------------------------- Renda fixa

def _fi(start, indexer="PRE", rate=10.0, invested=1000.0, tax_exempt=0):
    return {
        "invested_amount": invested,
        "indexer": indexer,
        "rate_value": rate,
        "tax_exempt": tax_exempt,
        "start_date": start.strftime("%Y-%m-%d"),
    }


@pytest.mark.parametrize(
    "days,ir",
    [(100, 22.5), (180, 22.5), (181, 20.0), (360, 20.0), (361, 17.5), (720, 17.5), (721, 15.0), (1000, 15.0)],
)
def test_renda_fixa_tabela_regressiva_de_ir(days, ir):
    r = market_service.calculate_fixed_income_position(_fi(date.today() - timedelta(days=days)), MACRO)
    assert r["ir_rate"] == ir
    assert r["net_amount"] == pytest.approx(r["gross_amount"] - r["ir_tax"], abs=0.01)


def test_renda_fixa_isenta_nao_paga_ir():
    r = market_service.calculate_fixed_income_position(
        _fi(date.today() - timedelta(days=200), tax_exempt=1), MACRO
    )
    assert r["ir_rate"] == 0.0
    assert r["ir_tax"] == 0.0
    assert r["net_amount"] == r["gross_amount"]


def test_renda_fixa_pre_capitaliza_por_dias_uteis_estimados():
    days = 365
    r = market_service.calculate_fixed_income_position(_fi(date.today() - timedelta(days=days)), MACRO)
    bd = int(days * 252.0 / 365.0)
    expected_gross = 1000.0 * (1.10 ** (bd / 252.0))
    assert r["gross_amount"] == pytest.approx(expected_gross, abs=0.01)
    assert r["ir_rate"] == 17.5  # 361-720 dias
    assert r["net_profit"] == pytest.approx(r["net_amount"] - 1000.0, abs=0.01)


def test_renda_fixa_cdi_percentual_e_ipca_mais_taxa():
    start = date.today() - timedelta(days=252 * 365 // 252)  # ~365 dias
    cdi = market_service.calculate_fixed_income_position(_fi(start, "CDI", 110.0), MACRO)
    ipca = market_service.calculate_fixed_income_position(_fi(start, "IPCA", 6.0), MACRO)
    bd = int(365 * 252.0 / 365.0)
    assert cdi["gross_amount"] == pytest.approx(1000.0 * ((1 + 0.10 * 1.10) ** (bd / 252.0)), abs=0.01)
    assert ipca["gross_amount"] == pytest.approx(1000.0 * ((1.04 * 1.06) ** (bd / 252.0)), abs=0.01)


def test_renda_fixa_com_ancora_de_mercado_nao_recapitaliza_desde_o_inicio():
    row = _fi(date.today() - timedelta(days=400))
    row.update(market_value=1200.0, market_net_value=1150.0, market_value_date=date.today().strftime("%Y-%m-%d"))
    r = market_service.calculate_fixed_income_position(row, MACRO)
    assert r["value_source"] == "MARKET_ANCHOR"
    assert r["gross_amount"] == pytest.approx(1200.0)
    assert r["net_amount"] == pytest.approx(1150.0)


def test_carteira_soma_renda_fixa_liquida_no_patrimonio(db):
    conn = database.get_conn()
    conn.execute(
        "INSERT INTO fixed_income (user_id, title_name, issuer, asset_class, indexer, rate_value, invested_amount, "
        "start_date, maturity_date, tax_exempt) VALUES (1, 'CDB X', 'Banco', 'RENDA_FIXA', 'PRE', 10.0, 1000.0, ?, '2030-01-01', 0)",
        ((date.today() - timedelta(days=365)).strftime("%Y-%m-%d"),),
    )
    conn.commit()
    conn.close()

    s = market_service.get_portfolio_summary()
    fi = s["fixed_income"][0]
    assert s["kpis"]["total_invested_brl"] == pytest.approx(1000.0)
    assert s["kpis"]["total_current_brl"] == pytest.approx(fi["net_amount"], abs=0.01)
    assert s["kpis"]["holdings_count"] == 1
