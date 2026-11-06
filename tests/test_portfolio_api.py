"""
Testes de API da Etapa 1: validacao de vendas (P1) e cambio informado/estimado (P3, P4).
Banco temporario; rede mockada.
"""
import pytest
from fastapi.testclient import TestClient

from app import database, main, market_service

client = TestClient(main.app)


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(main, "fetch_macro_indicators", lambda force=False: {"usd_brl": 6.0})
    monkeypatch.setattr(main, "lookup_ticker_live", lambda t, c="ACAO_BR": {"name": t, "last_price": 0})
    monkeypatch.setattr(market_service, "fetch_macro_indicators", lambda force=False: {"usd_brl": 6.0, "cdi": 10.0})
    monkeypatch.setattr(market_service, "sync_yfinance_quotes_background", lambda: None)
    database.init_db()
    return client


def _tx(**kw):
    base = {"tx_date": "2024-01-10", "ticker": "ITUB4", "asset_class": "ACAO_BR", "tx_type": "BUY",
            "quantity": 10, "unit_price": 30.0}
    base.update(kw)
    return base


def _rows(sql="SELECT * FROM transactions"):
    conn = database.get_conn()
    r = [dict(x) for x in conn.execute(sql).fetchall()]
    conn.close()
    return r


def test_p1_venda_acima_da_custodia_e_rejeitada(api):
    assert api.post("/api/transactions", json=_tx()).status_code == 200
    r = api.post("/api/transactions", json=_tx(tx_type="SELL", quantity=11, tx_date="2024-02-01"))
    assert r.status_code == 400
    assert "custódia" in r.json()["detail"]
    assert len(_rows()) == 1  # nada foi gravado


def test_p1_venda_ate_a_custodia_e_aceita(api):
    api.post("/api/transactions", json=_tx())
    assert api.post("/api/transactions", json=_tx(tx_type="SELL", quantity=10, tx_date="2024-02-01")).status_code == 200


def test_p1_venda_sem_ativo_e_rejeitada(api):
    r = api.post("/api/transactions", json=_tx(tx_type="SELL", quantity=1))
    assert r.status_code == 400


def test_p1_venda_antes_da_compra_e_rejeitada(api):
    api.post("/api/transactions", json=_tx(tx_date="2024-03-01"))
    r = api.post("/api/transactions", json=_tx(tx_type="SELL", quantity=5, tx_date="2024-01-01"))
    assert r.status_code == 400


def test_p1_venda_que_deixaria_venda_posterior_descoberta_e_rejeitada(api):
    api.post("/api/transactions", json=_tx(tx_date="2024-01-01"))
    api.post("/api/transactions", json=_tx(tx_type="SELL", quantity=8, tx_date="2024-03-01"))
    r = api.post("/api/transactions", json=_tx(tx_type="SELL", quantity=5, tx_date="2024-02-01"))
    assert r.status_code == 400  # sobrariam 2 no total


def test_validacoes_basicas_de_quantidade_e_cambio(api):
    assert api.post("/api/transactions", json=_tx(quantity=0)).status_code == 400
    assert api.post("/api/transactions", json=_tx(unit_price=-1)).status_code == 400
    assert api.post("/api/transactions", json=_tx(currency="USD", fx_rate=0)).status_code == 400


def test_p3_cambio_informado_e_gravado_como_nao_estimado(api):
    r = api.post("/api/transactions", json=_tx(ticker="AAPL", asset_class="STOCK_US", currency="USD", fx_rate=5.1))
    assert r.status_code == 200
    row = _rows()[0]
    assert row["fx_rate"] == 5.1 and row["fx_estimated"] == 0


def test_p3_sem_cambio_usa_cambio_atual_e_marca_estimado(api):
    api.post("/api/transactions", json=_tx(ticker="AAPL", asset_class="STOCK_US", currency="USD"))
    row = _rows()[0]
    assert row["fx_rate"] == 6.0 and row["fx_estimated"] == 1


def test_p3_operacao_em_brl_tem_cambio_1_e_nao_estimado(api):
    api.post("/api/transactions", json=_tx())
    row = _rows()[0]
    assert row["fx_rate"] == 1.0 and row["fx_estimated"] == 0


def test_p4_api_de_proventos_grava_cambio_informado(api):
    payload = {"pay_date": "2024-05-10", "ticker": "aapl", "amount_per_share": 0.5, "shares_qty": 10,
               "currency": "usd", "fx_rate": 5.2}
    assert api.post("/api/dividends", json=payload).status_code == 200
    row = _rows("SELECT * FROM dividends_received")[0]
    assert row["total_amount"] == 5.0 and row["currency"] == "USD" and row["fx_rate"] == 5.2
    assert api.post("/api/dividends", json={**payload, "fx_rate": -1}).status_code == 400


def test_migracao_de_colunas_de_cambio_e_idempotente(api):
    database.init_db()
    database.init_db()
    conn = database.get_conn()
    tx_cols = {r[1] for r in conn.execute("PRAGMA table_info(transactions)")}
    div_cols = {r[1] for r in conn.execute("PRAGMA table_info(dividends_received)")}
    conn.close()
    assert "fx_estimated" in tx_cols and "fx_rate" in div_cols
