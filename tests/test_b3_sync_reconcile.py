"""
Testes de reconciliação de custódia (Modo REPLACE seletivo e detecção de ativos vendidos no MERGE).
"""
import pytest
from app import database
from app.b3_sync_service import apply_b3_sync, ensure_b3_sync_tables


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    database.init_db()
    ensure_b3_sync_tables()
    monkeypatch.setattr("app.b3_sync_service.fetch_macro_indicators", lambda *a, **k: {"usd_brl": 5.0})
    monkeypatch.setattr("app.market_service.sync_yfinance_quotes_background", lambda: None)
    return tmp_path


def test_replace_mode_preserves_crypto_and_us_stocks(temp_db):
    conn = database.get_conn()
    # Adiciona ativo US e cripto pré-existentes
    conn.execute("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, currency, broker)
        VALUES ('2024-01-01', 'NVDA', 'STOCK_US', 'BUY', 10, 120.0, 'USD', 'Avenue'),
               ('2024-01-01', 'BTC', 'CRIPTO', 'BUY', 0.1, 50000.0, 'USD', 'Binance'),
               ('2024-01-01', 'PETR4', 'ACAO_BR', 'BUY', 100, 30.0, 'BRL', 'XP')
    """)
    conn.commit()
    conn.close()

    # Importa arquivo B3 contendo apenas BBAS3 em modo REPLACE
    parsed = {
        "positions": [
            {"ticker": "BBAS3", "name": "Banco do Brasil", "asset_class": "ACAO_BR", "currency": "BRL", "quantity": 50, "unit_price": 28.0, "broker": "B3"}
        ],
        "transactions": [],
        "fixed_income": [],
        "dividends": [],
    }
    apply_b3_sync(parsed, "REPLACE")

    conn = database.get_conn()
    rows = conn.execute("SELECT ticker, asset_class FROM transactions").fetchall()
    conn.close()

    tickers = {r["ticker"] for r in rows}
    # PETR4 (ACAO_BR) foi limpo e substituído por BBAS3, mas NVDA e BTC foram PRESERVADOS!
    assert "NVDA" in tickers
    assert "BTC" in tickers
    assert "BBAS3" in tickers
    assert "PETR4" not in tickers


def test_merge_mode_zeros_sold_b3_assets(temp_db):
    conn = database.get_conn()
    # Usuário possuía WEGE3 e ITUB4
    conn.execute("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, currency, broker)
        VALUES ('2024-01-01', 'WEGE3', 'ACAO_BR', 'BUY', 20, 40.0, 'BRL', 'XP'),
               ('2024-01-01', 'ITUB4', 'ACAO_BR', 'BUY', 30, 35.0, 'BRL', 'XP')
    """)
    conn.commit()
    conn.close()

    # Novo relatório de posição B3 só tem ITUB4 (WEGE3 foi vendido)
    parsed = {
        "positions": [
            {"ticker": "ITUB4", "name": "Itaú", "asset_class": "ACAO_BR", "currency": "BRL", "quantity": 30, "unit_price": 35.0, "broker": "XP"}
        ],
        "transactions": [],
        "fixed_income": [],
        "dividends": [],
    }
    apply_b3_sync(parsed, "MERGE")

    conn = database.get_conn()
    txs = conn.execute("SELECT ticker, tx_type, quantity FROM transactions WHERE ticker = 'WEGE3'").fetchall()
    conn.close()

    # WEGE3 deve ter a compra original de 20 e uma VENDA de ajuste de 20
    qty_net = sum(r["quantity"] if r["tx_type"] == "BUY" else -r["quantity"] for r in txs)
    assert qty_net == pytest.approx(0.0)


def test_replace_mode_with_fixed_income_only_does_not_wipe_transactions(temp_db):
    conn = database.get_conn()
    conn.execute("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, currency, broker)
        VALUES ('2024-01-01', 'PETR4', 'ACAO_BR', 'BUY', 100, 30.0, 'BRL', 'XP'),
               ('2024-01-01', 'HGLG11', 'FII', 'BUY', 10, 160.0, 'BRL', 'XP'),
               ('2024-01-01', 'NVDA', 'STOCK_US', 'BUY', 5, 120.0, 'USD', 'Avenue'),
               ('2024-01-01', 'BTC', 'CRIPTO', 'BUY', 0.05, 60000.0, 'USD', 'Binance')
    """)
    conn.execute("""
        INSERT INTO fixed_income (title_name, issuer, asset_class, indexer, rate_value, invested_amount, start_date, maturity_date)
        VALUES ('Caixinha Nubank Reserva', 'Nubank', 'CAIXINHA', 'CDI', 100.0, 5000.0, '2024-01-01', '2026-01-01'),
               ('Tesouro Selic Antigo', 'Tesouro Nacional', 'TESOURO', 'SELIC', 100.0, 3000.0, '2024-01-01', '2029-01-01')
    """)
    conn.commit()
    conn.close()

    # Importa arquivo B3 que só contém Tesouro Direto
    parsed = {
        "positions": [],
        "transactions": [],
        "fixed_income": [
            {
                "title_name": "Tesouro IPCA+ 2035",
                "issuer": "Tesouro Nacional",
                "asset_class": "TESOURO",
                "indexer": "IPCA",
                "rate_value": 6.5,
                "invested_amount": 4000.0,
                "start_date": "2024-06-01",
                "maturity_date": "2035-05-15",
                "daily_liquidity": 1,
                "tax_exempt": 0,
                "broker": "Tesouro Direto",
                "market_value": 4100.0,
            }
        ],
        "dividends": [],
    }
    apply_b3_sync(parsed, "REPLACE")

    conn = database.get_conn()
    tx_tickers = {r["ticker"] for r in conn.execute("SELECT ticker FROM transactions").fetchall()}
    fi_titles = {r["title_name"] for r in conn.execute("SELECT title_name FROM fixed_income").fetchall()}
    conn.close()

    # Nenhuma transação de renda variável foi apagada!
    assert "PETR4" in tx_tickers
    assert "HGLG11" in tx_tickers
    assert "NVDA" in tx_tickers
    assert "BTC" in tx_tickers

    # Tesouro antigo foi substituído, mas CAIXINHA manual foi 100% PRESERVADA!
    assert "Caixinha Nubank Reserva" in fi_titles
    assert "Tesouro IPCA+ 2035" in fi_titles
    assert "Tesouro Selic Antigo" not in fi_titles


def test_replace_mode_ignores_foreign_or_crypto_classes_in_parsed_data(temp_db):
    conn = database.get_conn()
    conn.execute("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, currency, broker)
        VALUES ('2024-01-01', 'NVDA', 'STOCK_US', 'BUY', 10, 120.0, 'USD', 'Avenue'),
               ('2024-01-01', 'BTC', 'CRIPTO', 'BUY', 0.1, 50000.0, 'USD', 'Binance'),
               ('2024-01-01', 'PETR4', 'ACAO_BR', 'BUY', 100, 30.0, 'BRL', 'XP')
    """)
    conn.commit()
    conn.close()

    # Arquivo B3 corrompido ou mal-inferido contendo STOCK_US e CRIPTO
    parsed = {
        "positions": [
            {"ticker": "VALE3", "name": "Vale", "asset_class": "ACAO_BR", "currency": "BRL", "quantity": 50, "unit_price": 60.0, "broker": "B3"},
            {"ticker": "NVDA", "name": "Nvidia", "asset_class": "STOCK_US", "currency": "USD", "quantity": 10, "unit_price": 120.0, "broker": "B3"},
            {"ticker": "BTC", "name": "Bitcoin", "asset_class": "CRIPTO", "currency": "USD", "quantity": 0.1, "unit_price": 50000.0, "broker": "B3"},
        ],
        "transactions": [],
        "fixed_income": [],
        "dividends": [],
    }
    apply_b3_sync(parsed, "REPLACE")

    conn = database.get_conn()
    rows = conn.execute("SELECT ticker, asset_class FROM transactions").fetchall()
    conn.close()

    tickers = {r["ticker"] for r in rows}
    # STOCK_US e CRIPTO jamais são apagados em massa por serem classes fora da B3
    assert "NVDA" in tickers
    assert "BTC" in tickers
    assert "VALE3" in tickers
    # PETR4 (ACAO_BR) foi limpo e substituído por VALE3
    assert "PETR4" not in tickers


def test_infer_asset_class_never_infers_us_stock_or_crypto_in_b3_service():
    from app.b3_sync_service import _infer_asset_class
    # Tickers sem dígitos em arquivos B3 não podem virar STOCK_US
    cls, cur = _infer_asset_class("VALE")
    assert cls == "ACAO_BR"
    assert cur == "BRL"

    cls, cur = _infer_asset_class("BOVA")
    assert cls == "ACAO_BR"
    assert cur == "BRL"

    cls, cur = _infer_asset_class("TOTAL")
    assert cls == "ACAO_BR"
    assert cur == "BRL"

    # FIIs e ETFs continuam identificados corretamente
    cls, cur = _infer_asset_class("MXRF11")
    assert cls == "FII"
    assert cur == "BRL"

    cls, cur = _infer_asset_class("BOVA11")
    assert cls == "ETF_BR"
    assert cur == "BRL"


def test_merge_mode_zeros_sold_stock_when_only_fii_remains(temp_db):
    conn = database.get_conn()
    conn.execute("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, currency, broker)
        VALUES ('2024-01-01', 'VALE3', 'ACAO_BR', 'BUY', 50, 60.0, 'BRL', 'XP'),
               ('2024-01-01', 'HGLG11', 'FII', 'BUY', 10, 160.0, 'BRL', 'XP')
    """)
    conn.commit()
    conn.close()

    # Planilha nova só contém HGLG11 (VALE3 foi vendida)
    parsed = {
        "filename": "posicao.xlsx",
        "positions": [
            {"ticker": "HGLG11", "name": "CSHG Logística", "asset_class": "FII", "currency": "BRL", "quantity": 10, "unit_price": 160.0, "broker": "XP"}
        ],
        "transactions": [],
        "fixed_income": [],
        "dividends": [],
    }
    res = apply_b3_sync(parsed, "MERGE")
    assert "VALE3" in res["zeroed_positions"]

    conn = database.get_conn()
    vale_txs = conn.execute("SELECT tx_type, quantity FROM transactions WHERE ticker = 'VALE3'").fetchall()
    conn.close()

    net_qty = sum(r["quantity"] if r["tx_type"] == "BUY" else -r["quantity"] for r in vale_txs)
    assert net_qty == pytest.approx(0.0)


def test_merge_mode_zeros_sold_fii_when_only_stock_remains(temp_db):
    conn = database.get_conn()
    conn.execute("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, currency, broker)
        VALUES ('2024-01-01', 'PETR4', 'ACAO_BR', 'BUY', 100, 35.0, 'BRL', 'XP'),
               ('2024-01-01', 'MXRF11', 'FII', 'BUY', 200, 10.0, 'BRL', 'XP')
    """)
    conn.commit()
    conn.close()

    # Planilha nova só contém PETR4 (MXRF11 foi vendido)
    parsed = {
        "filename": "posicao.xlsx",
        "positions": [
            {"ticker": "PETR4", "name": "Petrobras", "asset_class": "ACAO_BR", "currency": "BRL", "quantity": 100, "unit_price": 35.0, "broker": "XP"}
        ],
        "transactions": [],
        "fixed_income": [],
        "dividends": [],
    }
    res = apply_b3_sync(parsed, "MERGE")
    assert "MXRF11" in res["zeroed_positions"]

    conn = database.get_conn()
    mxrf_txs = conn.execute("SELECT tx_type, quantity FROM transactions WHERE ticker = 'MXRF11'").fetchall()
    conn.close()

    net_qty = sum(r["quantity"] if r["tx_type"] == "BUY" else -r["quantity"] for r in mxrf_txs)
    assert net_qty == pytest.approx(0.0)


def test_merge_mode_zeros_when_all_equities_sold_and_positions_empty(temp_db):
    conn = database.get_conn()
    conn.execute("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, currency, broker)
        VALUES ('2024-01-01', 'BBAS3', 'ACAO_BR', 'BUY', 30, 25.0, 'BRL', 'XP')
    """)
    conn.commit()
    conn.close()

    # Usuário vendeu BBAS3 e agora só tem Tesouro Direto na planilha de posição
    parsed = {
        "filename": "posicao-2026-10-30.xlsx",
        "positions": [],
        "transactions": [],
        "fixed_income": [
            {"title_name": "Tesouro Selic 2029", "issuer": "Tesouro Nacional", "asset_class": "TESOURO", "indexer": "SELIC", "rate_value": 0.1, "invested_amount": 1000.0, "start_date": "2024-01-01", "maturity_date": "2029-01-01", "daily_liquidity": 1, "tax_exempt": 0, "broker": "XP"}
        ],
        "dividends": [],
    }
    res = apply_b3_sync(parsed, "MERGE")
    assert "BBAS3" in res["zeroed_positions"]

    conn = database.get_conn()
    bbas_txs = conn.execute("SELECT tx_type, quantity FROM transactions WHERE ticker = 'BBAS3'").fetchall()
    conn.close()

    net_qty = sum(r["quantity"] if r["tx_type"] == "BUY" else -r["quantity"] for r in bbas_txs)
    assert net_qty == pytest.approx(0.0)


def test_merge_mode_zeros_asset_not_in_assets_catalog(temp_db):
    conn = database.get_conn()
    # Ativo customizado/fora do catalogo inicial
    conn.execute("DELETE FROM assets_catalog WHERE ticker = 'CUSTOM3'")
    conn.execute("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, currency, broker)
        VALUES ('2024-01-01', 'CUSTOM3', 'ACAO_BR', 'BUY', 15, 10.0, 'BRL', 'XP'),
               ('2024-01-01', 'ITUB4', 'ACAO_BR', 'BUY', 20, 30.0, 'BRL', 'XP')
    """)
    conn.commit()
    conn.close()

    parsed = {
        "filename": "posicao.xlsx",
        "positions": [
            {"ticker": "ITUB4", "name": "Itaú", "asset_class": "ACAO_BR", "currency": "BRL", "quantity": 20, "unit_price": 30.0, "broker": "XP"}
        ],
        "transactions": [],
        "fixed_income": [],
        "dividends": [],
    }
    res = apply_b3_sync(parsed, "MERGE")
    assert "CUSTOM3" in res["zeroed_positions"]

    conn = database.get_conn()
    custom_txs = conn.execute("SELECT tx_type, quantity FROM transactions WHERE ticker = 'CUSTOM3'").fetchall()
    conn.close()

    net_qty = sum(r["quantity"] if r["tx_type"] == "BUY" else -r["quantity"] for r in custom_txs)
    assert net_qty == pytest.approx(0.0)


def test_merge_mode_never_zeros_us_stocks_or_crypto(temp_db):
    conn = database.get_conn()
    conn.execute("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, currency, broker)
        VALUES ('2024-01-01', 'NVDA', 'STOCK_US', 'BUY', 10, 120.0, 'USD', 'Avenue'),
               ('2024-01-01', 'BTC', 'CRIPTO', 'BUY', 0.1, 60000.0, 'USD', 'Binance'),
               ('2024-01-01', 'PETR4', 'ACAO_BR', 'BUY', 50, 35.0, 'BRL', 'XP')
    """)
    conn.commit()
    conn.close()

    # Planilha B3 com novo ativo VALE3 (PETR4 foi vendido, mas NVDA e BTC jamais devem ser tocados)
    parsed = {
        "filename": "posicao.xlsx",
        "positions": [
            {"ticker": "VALE3", "name": "Vale", "asset_class": "ACAO_BR", "currency": "BRL", "quantity": 100, "unit_price": 60.0, "broker": "XP"}
        ],
        "transactions": [],
        "fixed_income": [],
        "dividends": [],
    }
    res = apply_b3_sync(parsed, "MERGE")
    assert "PETR4" in res["zeroed_positions"]
    assert "NVDA" not in res["zeroed_positions"]
    assert "BTC" not in res["zeroed_positions"]

    conn = database.get_conn()
    nvda_qty = sum(r["quantity"] if r["tx_type"] == "BUY" else -r["quantity"] for r in conn.execute("SELECT tx_type, quantity FROM transactions WHERE ticker = 'NVDA'").fetchall())
    btc_qty = sum(r["quantity"] if r["tx_type"] == "BUY" else -r["quantity"] for r in conn.execute("SELECT tx_type, quantity FROM transactions WHERE ticker = 'BTC'").fetchall())
    petr_qty = sum(r["quantity"] if r["tx_type"] == "BUY" else -r["quantity"] for r in conn.execute("SELECT tx_type, quantity FROM transactions WHERE ticker = 'PETR4'").fetchall())
    conn.close()

    assert nvda_qty == pytest.approx(10.0)
    assert btc_qty == pytest.approx(0.1)
    assert petr_qty == pytest.approx(0.0)


def test_merge_mode_fixed_income_only_file_does_not_zero_equities(temp_db):
    conn = database.get_conn()
    conn.execute("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, currency, broker)
        VALUES ('2024-01-01', 'PETR4', 'ACAO_BR', 'BUY', 50, 35.0, 'BRL', 'XP')
    """)
    conn.commit()
    conn.close()

    # Arquivo exclusivo de Tesouro Direto (não é relatório de posição de renda variável)
    parsed = {
        "filename": "tesouro_direto.xlsx",
        "sheets_detected": [{"sheet": "Tesouro Direto", "kind": "TESOURO_DIRETO", "items": 1}],
        "positions": [],
        "transactions": [],
        "fixed_income": [
            {"title_name": "Tesouro IPCA+ 2029", "issuer": "Tesouro Nacional", "asset_class": "TESOURO", "indexer": "IPCA", "rate_value": 6.2, "invested_amount": 500.0, "start_date": "2024-01-01", "maturity_date": "2029-05-15", "daily_liquidity": 1, "tax_exempt": 0, "broker": "XP"}
        ],
        "dividends": [],
    }
    res = apply_b3_sync(parsed, "MERGE")
    assert len(res.get("zeroed_positions", [])) == 0

    conn = database.get_conn()
    petr_qty = sum(r["quantity"] if r["tx_type"] == "BUY" else -r["quantity"] for r in conn.execute("SELECT tx_type, quantity FROM transactions WHERE ticker = 'PETR4'").fetchall())
    conn.close()

    assert petr_qty == pytest.approx(50.0)


def test_parse_b3_spreadsheet_annotates_sold_positions_for_preview(temp_db):
    conn = database.get_conn()
    conn.execute("""
        INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price, currency, broker)
        VALUES ('2024-01-01', 'BBAS3', 'ACAO_BR', 'BUY', 10, 25.0, 'BRL', 'XP'),
               ('2024-01-01', 'ITUB4', 'ACAO_BR', 'BUY', 20, 30.0, 'BRL', 'XP')
    """)
    conn.commit()
    conn.close()

    # Cria CSV de posição contendo apenas ITUB4 (BBAS3 não consta mais)
    csv_content = (
        "Produto;Código de Negociação;Quantidade;Preço de Fechamento;Valor Atualizado\n"
        "ITUB4 - ITAU UNIBANCO;ITUB4;20;30.00;600.00\n"
    ).encode("utf-8")

    from app.b3_sync_service import parse_b3_spreadsheet
    parsed = parse_b3_spreadsheet(csv_content, "posicao_b3.csv")

    assert "sold_positions" in parsed
    sold_tickers = [s["ticker"] for s in parsed["sold_positions"]]
    assert "BBAS3" in sold_tickers
    assert "ITUB4" not in sold_tickers



