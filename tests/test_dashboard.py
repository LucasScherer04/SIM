"""
Testes da Etapa 2: dashboard (totais conciliados, filtros, concentracao, proventos, evolucao,
snapshots, cambio) e exportacoes. Banco temporario; rede mockada.
"""
from datetime import date, timedelta
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app import dashboard_service, database, main, market_service

USD_BRL = 7.0
FX_TS = "2026-11-06 10:00:00"


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    macro = {"usd_brl": USD_BRL, "cdi": 10.0, "selic": 10.5, "ipca_12m": 4.0, "usd_brl_updated_at": FX_TS}
    monkeypatch.setattr(market_service, "fetch_macro_indicators", lambda force=False: dict(macro))
    monkeypatch.setattr(market_service, "sync_yfinance_quotes_background", lambda: None)
    monkeypatch.setattr(main, "fetch_macro_indicators", lambda force=False: dict(macro))
    database.init_db()
    return macro


def _catalog(ticker, cls, price, currency="BRL", sector=""):
    conn = database.get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO assets_catalog (ticker, name, asset_class, currency, sector, last_price, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, '2026-11-06 10:00:00')",
        (ticker, ticker, cls, currency, sector, price),
    )
    conn.commit()
    conn.close()


def _tx(d, ticker, cls, typ, qty, price, fees=0.0, currency="BRL", fx=1.0):
    conn = database.get_conn()
    conn.execute(
        "INSERT INTO transactions (user_id, tx_date, ticker, asset_class, tx_type, quantity, unit_price, fees, "
        "currency, fx_rate, notes) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'negociacao')",
        (d, ticker, cls, typ, qty, price, fees, currency, fx),
    )
    conn.commit()
    conn.close()


def _div(pay_date, ticker, total, currency="BRL", fx=0.0):
    conn = database.get_conn()
    conn.execute(
        "INSERT INTO dividends_received (user_id, pay_date, ticker, amount_per_share, shares_qty, total_amount, "
        "currency, fx_rate) VALUES (1, ?, ?, ?, 1, ?, ?, ?)",
        (pay_date, ticker, total, total, currency, fx),
    )
    conn.commit()
    conn.close()


def _fi(start, invested=1000.0):
    conn = database.get_conn()
    conn.execute(
        "INSERT INTO fixed_income (user_id, title_name, issuer, asset_class, indexer, rate_value, invested_amount, "
        "start_date, maturity_date, tax_exempt) VALUES (1, 'CDB X', 'Banco', 'RENDA_FIXA', 'PRE', 10.0, ?, ?, '2030-01-01', 0)",
        (invested, start),
    )
    conn.commit()
    conn.close()


def _portfolio():
    """ITUB4 (BR), HGLG11 (FII), AAPL (USD) e um CDB."""
    _catalog("ITUB4", "ACAO_BR", 40.0, sector="Bancos")
    _catalog("HGLG11", "FII", 110.0)
    _catalog("AAPL", "STOCK_US", 130.0, currency="USD", sector="Tecnologia")
    _tx("2026-01-10", "ITUB4", "ACAO_BR", "BUY", 10, 30.0)
    _tx("2026-02-10", "HGLG11", "FII", "BUY", 5, 100.0)
    _tx("2026-02-20", "AAPL", "STOCK_US", "BUY", 10, 100.0, currency="USD", fx=5.0)
    _fi((date.today() - timedelta(days=365)).strftime("%Y-%m-%d"))


def _dash(**kw):
    kw.setdefault("record", False)
    return dashboard_service.get_dashboard(1, **kw)


# ------------------------------------------------------------------ totais e conciliacao

def test_totais_conciliam_com_resumo_da_carteira_e_com_o_banco(db):
    _portfolio()
    s = market_service.get_portfolio_summary()
    d = _dash()

    assert d["kpis"]["total_current_brl"] == pytest.approx(s["kpis"]["total_current_brl"], abs=0.05)
    assert d["kpis"]["total_invested_brl"] == pytest.approx(s["kpis"]["total_invested_brl"], abs=0.05)
    assert d["reconciliation"]["checked"] is True and d["reconciliation"]["ok"] is True

    # conciliacao independente com o banco: 300 + 500 + 5000 (custo historico USD) + 1000 (renda fixa)
    assert d["kpis"]["total_invested_brl"] == pytest.approx(300 + 500 + 5000 + 1000)
    # valor atual variavel: 400 + 550 + 10*130*7
    fi_net = s["fixed_income"][0]["net_amount"]
    assert d["kpis"]["total_current_brl"] == pytest.approx(400 + 550 + 9100 + fi_net, abs=0.05)
    assert d["kpis"]["holdings_count"] == 4


def test_distribuicoes_somam_o_total_e_100_por_cento(db):
    _portfolio()
    d = _dash()
    total = d["kpis"]["total_current_brl"]
    for dim in ("by_class", "by_country", "by_currency", "by_sector"):
        rows = d["distribution"][dim]
        assert sum(r["current_brl"] for r in rows) == pytest.approx(total, abs=0.05), dim
        assert sum(r["weight_pct"] for r in rows) == pytest.approx(100.0, abs=0.1), dim

    countries = {r["key"]: r for r in d["distribution"]["by_country"]}
    assert set(countries) == {"BR", "US"}
    assert countries["US"]["current_brl"] == pytest.approx(9100.0)
    cur = {r["key"]: r for r in d["distribution"]["by_currency"]}
    assert cur["USD"]["current_native"] == pytest.approx(1300.0)  # moeda original preservada
    sectors = {r["key"] for r in d["distribution"]["by_sector"]}
    assert {"Bancos", "Tecnologia", "Renda fixa", "Não informado"} <= sectors


# ------------------------------------------------------------------ filtros

def test_filtro_por_pais_moeda_e_classe(db):
    _portfolio()
    us = _dash(country="US")
    assert [h["code"] for h in us["holdings"]] == ["AAPL"]
    assert us["kpis"]["total_current_brl"] == pytest.approx(9100.0)
    assert us["kpis"]["total_invested_brl"] == pytest.approx(5000.0)
    assert us["reconciliation"]["checked"] is False
    assert us["holdings"][0]["weight_pct"] == 100.0

    brl = _dash(currency="brl")
    assert "AAPL" not in [h["code"] for h in brl["holdings"]]
    assert len(brl["holdings"]) == 3

    fii = _dash(asset_class="FII")
    assert [h["code"] for h in fii["holdings"]] == ["HGLG11"]
    assert fii["kpis"]["profit_brl"] == pytest.approx(50.0)

    none = _dash(asset_class="FII", country="US")
    assert none["holdings"] == [] and none["kpis"]["total_current_brl"] == 0


def test_periodo_invalido_vira_all(db):
    assert _dash(period="XYZ")["filters"]["period"] == "ALL"


# ------------------------------------------------------------------ concentracao

def test_concentracao_e_hhi(db):
    _catalog("A", "ACAO_BR", 10.0)
    _catalog("B", "ACAO_BR", 10.0)
    _tx("2026-01-10", "A", "ACAO_BR", "BUY", 30, 10.0)  # 300
    _tx("2026-01-10", "B", "ACAO_BR", "BUY", 10, 10.0)  # 100
    c = _dash()["concentration"]
    assert [t["code"] for t in c["top"]] == ["A", "B"]
    assert c["top1_pct"] == 75.0 and c["top5_pct"] == 100.0
    assert c["hhi"] == pytest.approx((0.75 ** 2 + 0.25 ** 2) * 10000)
    assert c["effective_positions"] == pytest.approx(1 / (0.75 ** 2 + 0.25 ** 2), abs=0.05)


def test_carteira_vazia_nao_quebra_e_nao_grava_snapshot(db):
    d = dashboard_service.get_dashboard(1, record=True)
    assert d["kpis"]["total_current_brl"] == 0
    assert d["concentration"]["hhi"] == 0 and d["concentration"]["top"] == []
    assert d["evolution"]["snapshot_recorded_today"] is False
    conn = database.get_conn()
    assert conn.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0] == 0
    conn.close()


# ------------------------------------------------------------------ proventos

def test_proventos_por_mes_ano_ativo_e_conversao_usd(db):
    _portfolio()
    _div("2026-03-10", "HGLG11", 10.0)
    _div("2026-03-20", "HGLG11", 5.0)
    _div("2026-04-10", "ITUB4", 2.0)
    _div("2025-12-10", "ITUB4", 1.0)
    _div("2026-03-15", "AAPL", 2.0, currency="USD", fx=5.0)  # 10 BRL com cambio informado
    _div("2026-04-15", "AAPL", 1.0, currency="USD")  # 7 BRL pelo cambio atual (estimado)

    dv = _dash()["dividends"]
    months = {m["month"]: m["total_brl"] for m in dv["by_month"]}
    assert months == {"2025-12": 1.0, "2026-03": 25.0, "2026-04": 9.0}
    years = {y["year"]: y["total_brl"] for y in dv["by_year"]}
    assert years == {"2025": 1.0, "2026": 34.0}
    assert dv["total_brl"] == pytest.approx(35.0)
    assert dv["by_ticker"][0] == {"ticker": "AAPL", "total_brl": 17.0}  # 10 (informado) + 7 (atual)
    assert dv["by_ticker"][1] == {"ticker": "HGLG11", "total_brl": 15.0}
    assert dv["by_currency_original"] == {"BRL": 18.0, "USD": 3.0}
    assert dv["has_estimated_fx"] is True
    # confere com o resumo da carteira
    assert dv["total_brl"] == pytest.approx(market_service.get_portfolio_summary()["kpis"]["total_dividends_brl"])


def test_proventos_respeitam_periodo_e_filtros(db):
    _portfolio()
    _div(date.today().strftime("%Y-%m-%d"), "HGLG11", 4.0)
    _div("2020-01-10", "HGLG11", 100.0)
    _div(date.today().strftime("%Y-%m-%d"), "ITUB4", 3.0)

    assert _dash(period="1M")["dividends"]["total_brl"] == pytest.approx(7.0)
    assert _dash(period="ALL")["dividends"]["total_brl"] == pytest.approx(107.0)
    assert _dash(period="1M", asset_class="FII")["dividends"]["total_brl"] == pytest.approx(4.0)
    assert _dash(country="US")["dividends"]["total_brl"] == 0


# ------------------------------------------------------------------ evolucao e snapshots

def test_aportes_liquidos_reconstruidos_das_operacoes(db):
    _catalog("ITUB4", "ACAO_BR", 40.0)
    _catalog("AAPL", "STOCK_US", 130.0, currency="USD")
    _tx("2026-01-10", "ITUB4", "ACAO_BR", "BUY", 10, 30.0, fees=5.0)  # 305
    _tx("2026-01-20", "AAPL", "STOCK_US", "BUY", 2, 100.0, currency="USD", fx=5.0)  # 1000
    _tx("2026-02-10", "ITUB4", "ACAO_BR", "SELL", 4, 40.0, fees=10.0)  # -150

    ev = _dash()["evolution"]["contributions"]
    assert ev == [
        {"month": "2026-01", "net_contribution_brl": 1305.0, "cumulative_contribution_brl": 1305.0},
        {"month": "2026-02", "net_contribution_brl": -150.0, "cumulative_contribution_brl": 1155.0},
    ]
    # com filtro de moeda, so a parte em BRL
    ev_brl = _dash(currency="BRL")["evolution"]["contributions"]
    assert ev_brl[0]["net_contribution_brl"] == 305.0


def test_snapshot_diario_e_idempotente_e_so_para_carteira_completa(db):
    _portfolio()
    d1 = dashboard_service.get_dashboard(1, record=True)
    dashboard_service.get_dashboard(1, record=True)
    assert d1["evolution"]["snapshot_recorded_today"] is True
    conn = database.get_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM portfolio_snapshots")]
    conn.close()
    assert len(rows) == 1 and rows[0]["snap_date"] == date.today().strftime("%Y-%m-%d")
    assert rows[0]["total_current_brl"] == pytest.approx(d1["kpis"]["total_current_brl"], abs=0.05)
    assert rows[0]["usd_brl"] == USD_BRL

    f = dashboard_service.get_dashboard(1, country="US", record=True)
    assert f["evolution"]["snapshot_recorded_today"] is False
    assert f["evolution"]["snapshots"] == []
    assert f["evolution"]["period_return"]["available"] is False


def _snap(d, current, invested=0.0):
    conn = database.get_conn()
    conn.execute(
        "INSERT INTO portfolio_snapshots (user_id, snap_date, total_current_brl, total_invested_brl, usd_brl) "
        "VALUES (1, ?, ?, ?, 5.0)", (d, current, invested))
    conn.commit()
    conn.close()


def test_rentabilidade_do_periodo_dietz_modificado(db):
    _catalog("X", "ACAO_BR", 10.0)
    _tx("2026-02-01", "X", "ACAO_BR", "BUY", 10, 100.0)  # aporte de 1000 entre os snapshots
    _snap("2026-01-01", 10000.0)
    _snap("2026-03-01", 12000.0)

    pr = _dash()["evolution"]["period_return"]
    assert pr["available"] is True
    assert pr["net_contributions_brl"] == 1000.0
    assert pr["gain_brl"] == 1000.0  # 12000 - 10000 - 1000
    assert pr["return_pct"] == pytest.approx(1000.0 / 10500.0 * 100.0, abs=0.01)
    assert pr["from"] == "2026-01-01" and pr["to"] == "2026-03-01"


def test_rentabilidade_indisponivel_com_menos_de_dois_snapshots(db):
    _snap("2026-01-01", 10000.0)
    pr = _dash()["evolution"]["period_return"]
    assert pr["available"] is False and "insuficiente" in pr["reason"].lower()


# ------------------------------------------------------------------ cambio e qualidade de dados

def test_cambio_exibe_valor_fonte_e_data(db):
    _portfolio()
    fx = _dash()["fx"]
    assert fx["usd_brl"] == USD_BRL and fx["updated_at"] == FX_TS and fx["is_live"] is True
    assert fx["usd_holdings"] == 1 and "AwesomeAPI" in fx["source"]
    h = next(h for h in _dash()["holdings"] if h["code"] == "AAPL")
    assert h["currency"] == "USD" and h["fx_current"] == USD_BRL
    assert h["avg_fx"] == pytest.approx(5.0)  # cambio medio historico da compra


def test_cambio_sem_atualizacao_e_sinalizado_como_valor_padrao(db, monkeypatch):
    monkeypatch.setattr(market_service, "fetch_macro_indicators", lambda force=False: {"usd_brl": 5.72, "cdi": 10.0})
    fx = _dash()["fx"]
    assert fx["is_live"] is False and fx["updated_at"] is None and "padrão" in fx["source"]


def test_qualidade_dos_dados_aponta_cotacoes_antigas(db):
    _portfolio()
    now = date.today().strftime("%Y-%m-%d") + " 09:00:00"
    conn = database.get_conn()
    conn.execute("UPDATE assets_catalog SET updated_at = ?", (now,))
    conn.execute("UPDATE assets_catalog SET updated_at = '2020-01-01 00:00:00' WHERE ticker = 'ITUB4'")
    conn.commit()
    conn.close()
    q = _dash()["data_quality"]
    assert q["positions_total"] == 3
    assert q["positions_with_stale_quote"] == 1 and q["stale_codes"] == ["ITUB4"]
    assert q["oldest_quote_at"] == "2020-01-01 00:00:00"


def test_benchmark_declarado_como_indisponivel(db):
    b = _dash()["benchmark"]
    assert b["available"] is False and b["reason"]


# ------------------------------------------------------------------ API e exportacoes

@pytest.fixture
def client(db):
    return TestClient(main.app)


def test_api_dashboard_aplica_filtros(client):
    _portfolio()
    r = client.get("/api/dashboard", params={"country": "US", "period": "12M"})
    assert r.status_code == 200
    j = r.json()
    assert j["filters"] == {"period": "12M", "country": "US", "currency": "ALL", "asset_class": "ALL"}
    assert [h["code"] for h in j["holdings"]] == ["AAPL"]


def test_api_dashboard_registra_snapshot_no_uso_normal(client):
    _portfolio()
    client.get("/api/dashboard")
    conn = database.get_conn()
    n = conn.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0]
    conn.close()
    assert n == 1


def test_export_csv_totais_e_filtros(client):
    _portfolio()
    r = client.get("/api/dashboard/export-csv", params={"country": "US"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "SIM_posicoes_" in r.headers["content-disposition"]
    text = r.content.decode("utf-8-sig")
    assert "AAPL;" in text and "ITUB4" not in text
    assert "5000,00;9100,00;4100,00" in text  # investido; atual; resultado
    assert "TOTAL" in text and "Câmbio USD/BRL" in text and FX_TS in text


def test_export_csv_neutraliza_formulas(client):
    _catalog("=CMD", "ACAO_BR", 10.0, sector="+SOMA")
    _tx("2026-01-10", "=CMD", "ACAO_BR", "BUY", 1, 10.0)
    text = client.get("/api/dashboard/export-csv").content.decode("utf-8-sig")
    assert "'=CMD" in text and "'+SOMA" in text


def test_export_xlsx_da_carteira_funciona_com_posicoes(client):
    # regressao: o export usava a chave inexistente 'current_total_brl' (KeyError)
    import openpyxl
    _portfolio()
    r = client.get("/api/b3/export-xlsx")
    assert r.status_code == 200
    wb = openpyxl.load_workbook(BytesIO(r.content))
    ws = wb["Acoes"]
    rows = list(ws.iter_rows(values_only=True))
    itub = next(x for x in rows if x[2] == "ITUB4")
    assert itub[7] == pytest.approx(400.0)  # valor atualizado = qtd x cotacao
