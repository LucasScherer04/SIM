"""
Testes de regressão da importação B3 e do cálculo de Renda Fixa.

Usam um banco SQLite temporário (nunca tocam no sim_database.db real) e uma planilha
sintética com a mesma estrutura do "Relatório de Posição" da Área do Investidor B3.

Executar:  python -m pytest -q
"""
from datetime import date, timedelta

import pytest

from app import database
from app.b3_sync_service import parse_b3_spreadsheet, apply_b3_sync, ensure_b3_sync_tables
from app.market_service import calculate_fixed_income_position

MACRO = {"cdi": 10.65, "selic": 10.75, "ipca_12m": 4.42}

# CSV com 4 tabelas empilhadas (Ações, FIIs, Renda Fixa, Tesouro), igual ao export da B3.
B3_MULTI_SECTION_CSV = """Produto;Instituição;Conta;Código de Negociação;CNPJ da Empresa;Tipo;Quantidade;Preço de Fechamento;Valor Atualizado
BBAS3 - BCO BRASIL S.A.;BANCO COOPERATIVO SICREDI S/A;1;BBAS3;00000000000191;ON;1;16,79;16,79
ITUB4 - ITAU UNIBANCO HOLDING S.A.;NU INVESTIMENTOS S.A. - CTVM;2;ITUB4;60872504000123;PN;4;39,78;159,12
Total
319,31

Produto;Instituição;Conta;Código de Negociação;CNPJ do Fundo;Tipo;Quantidade;Preço de Fechamento;Valor Atualizado
MXRF11 - MAXI RENDA FDO INV IMOB RESP LIM;NU INVESTIMENTOS S.A. - CTVM;2;MXRF11;97521225000125;Cotas;109;8,98;978,82
Total
978,82

Produto;Instituição;Emissor;Código;Indexador;Data de Emissão;Vencimento;Quantidade;Valor Atualizado MTM;Valor Atualizado CURVA
CDB - BANCO C6 CONSIGNADO S.A;NU INVESTIMENTOS S.A. - CTVM;BANCO C6 CONSIGNADO S.A;CDBA243CBA9;DI;07/10/2024;07/10/2027;100;-;133,16
Total
133,16

Produto;Instituição;Código ISIN;Indexador;Vencimento;Quantidade;Valor Aplicado;Valor bruto;Valor líquido;Valor Atualizado
Tesouro IPCA+ 2029;NU INVESTIMENTOS S.A. - CTVM;BRSTNCNTB6A3;IPCA;15/05/2029;0,18;576,65;708,12;685,06;708,12
Tesouro Selic 2029;NU INVESTIMENTOS S.A. - CTVM;BRSTNCLF1RL5;SELIC;01/03/2029;0,04;605,98;806,45;776,39;806,45
Total
1514,57
"""
EXPECTED_TOTAL = round(16.79 + 159.12 + 978.82 + 133.16 + 708.12 + 806.45, 2)


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    database.init_db()
    ensure_b3_sync_tables()
    # Evita chamadas de rede durante os testes
    monkeypatch.setattr("app.b3_sync_service.fetch_macro_indicators", lambda *a, **k: {"usd_brl": 5.0})
    monkeypatch.setattr("app.market_service.sync_yfinance_quotes_background", lambda: None)
    return tmp_path


def _parsed():
    return parse_b3_spreadsheet(B3_MULTI_SECTION_CSV.encode("utf-8"), "posicao.csv")


def test_parser_reads_all_stacked_sections():
    res = _parsed()
    assert res["counts"]["positions"] == 3
    assert res["counts"]["fixed_income"] == 3
    assert res["estimated_value_brl"] == pytest.approx(EXPECTED_TOTAL, abs=0.01)


def test_parser_separates_cost_market_and_net_values():
    fi = {f["title_name"]: f for f in _parsed()["fixed_income"]}

    ipca = fi["Tesouro IPCA+ 2029"]
    assert ipca["invested_amount"] == pytest.approx(576.65)  # custo (Valor Aplicado)
    assert ipca["market_value"] == pytest.approx(708.12)     # âncora (Valor Atualizado)
    assert ipca["market_net_value"] == pytest.approx(685.06)  # líquido oficial

    cdb = fi["CDB - BANCO C6 CONSIGNADO S.A"]
    assert cdb["market_value"] == pytest.approx(133.16)      # vem da coluna CURVA (MTM é "-")
    assert cdb["start_date"] == "2024-10-07"                 # data de emissão real


def test_anchor_same_day_matches_b3_exactly():
    row = {
        "id": 1, "title_name": "Tesouro IPCA+ 2029", "issuer": "Tesouro Nacional",
        "indexer": "IPCA", "rate_value": 6.25, "tax_exempt": 0,
        "invested_amount": 576.65, "start_date": date.today().isoformat(),
        "market_value": 708.12, "market_net_value": 685.06,
        "market_value_date": date.today().isoformat(),
    }
    calc = calculate_fixed_income_position(row, MACRO)
    assert calc["gross_amount"] == pytest.approx(708.12)
    assert calc["net_amount"] == pytest.approx(685.06)
    assert calc["value_source"] == "MARKET_ANCHOR"


def test_anchor_does_not_double_compound_from_old_start_date():
    """Bug original: valor atualizado + start_date antiga => juros aplicados em dobro."""
    old_start = (date.today() - timedelta(days=720)).isoformat()
    anchor = (date.today() - timedelta(days=30)).isoformat()
    row = {
        "id": 1, "title_name": "CDB", "issuer": "Banco", "indexer": "CDI", "rate_value": 100.0,
        "tax_exempt": 0, "invested_amount": 100.0, "start_date": old_start,
        "market_value": 120.0, "market_net_value": None, "market_value_date": anchor,
    }
    calc = calculate_fixed_income_position(row, MACRO)
    # ~30 dias corridos a 100% CDI => crescimento < 1,5%. Sem a âncora daria ~+22% sobre 120.
    assert 120.0 < calc["gross_amount"] < 120.0 * 1.015


def test_manual_entry_without_anchor_keeps_projection():
    row = {
        "id": 1, "title_name": "CDB manual", "issuer": "Banco", "indexer": "CDI", "rate_value": 100.0,
        "tax_exempt": 0, "invested_amount": 1000.0,
        "start_date": (date.today() - timedelta(days=365)).isoformat(),
    }
    calc = calculate_fixed_income_position(row, MACRO)
    assert calc["value_source"] == "PROJECTED"
    assert calc["gross_amount"] > 1000.0


def test_resync_updates_anchor_without_duplicating(temp_db):
    apply_b3_sync(_parsed(), "MERGE")

    # Simula que a 1ª importação foi há 60 dias com a data de início antiga
    conn = database.get_conn()
    old = (date.today() - timedelta(days=60)).isoformat()
    conn.execute("UPDATE fixed_income SET market_value_date = ?, start_date = ?", (old, "2020-01-01"))
    conn.commit()
    conn.close()

    apply_b3_sync(_parsed(), "MERGE")

    conn = database.get_conn()
    rows = [dict(r) for r in conn.execute("SELECT * FROM fixed_income").fetchall()]
    conn.close()
    assert len(rows) == 3  # não duplicou
    today = date.today().isoformat()
    for r in rows:
        assert r["market_value_date"] == today  # âncora renovada
    ipca = next(r for r in rows if r["title_name"] == "Tesouro IPCA+ 2029")
    assert ipca["start_date"] == "2020-01-01"  # Data de início original preservada!
    assert ipca["invested_amount"] == pytest.approx(576.65)  # Valor aplicado preservado!
    assert ipca["market_value"] == pytest.approx(708.12)     # Valor atualizado renovado!
    assert ipca["market_net_value"] == pytest.approx(685.06) # Valor líquido renovado!
    calc = calculate_fixed_income_position(ipca, MACRO)
    assert calc["gross_amount"] == pytest.approx(708.12)
    assert calc["net_amount"] == pytest.approx(685.06)
    assert calc["ir_rate"] == 15.0  # Alíquota de IR mantida na faixa mínima (2020 > 720 dias)


def test_adjust_fixed_income_endpoint(temp_db):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    apply_b3_sync(_parsed(), "MERGE")
    conn = database.get_conn()
    cdb = conn.execute("SELECT * FROM fixed_income WHERE title_name LIKE '%CDB%'").fetchone()
    conn.close()

    cdb_id = cdb["id"]
    # Ajusta o custo aplicado de 133.16 para 100.00 e o valor atualizado para 140.00
    res = client.post(f"/api/fixed-income/{cdb_id}/adjust", json={
        "invested_amount": 100.0,
        "market_value": 140.0,
        "start_date": "2024-01-15",
    })
    assert res.status_code == 200

    conn = database.get_conn()
    updated = dict(conn.execute("SELECT * FROM fixed_income WHERE id = ?", (cdb_id,)).fetchone())
    conn.close()

    assert updated["invested_amount"] == pytest.approx(100.0)
    assert updated["market_value"] == pytest.approx(140.0)
    assert updated["start_date"] == "2024-01-15"

    calc = calculate_fixed_income_position(updated, MACRO)
    assert calc["gross_amount"] == pytest.approx(140.0)
    assert calc["gross_profit"] == pytest.approx(40.0)
    assert calc["net_profit"] > 0


def test_add_fixed_income_with_optional_market_value(temp_db):
    from fastapi.testclient import TestClient
    from app.main import app
    client = TestClient(app)

    res = client.post("/api/fixed-income", json={
        "title_name": "CDB Banco ABC 115% CDI",
        "issuer": "Banco ABC",
        "asset_class": "RENDA_FIXA",
        "indexer": "CDI",
        "rate_value": 115.0,
        "invested_amount": 1000.0,
        "start_date": "2024-05-10",
        "maturity_date": "2027-05-10",
        "daily_liquidity": 0,
        "tax_exempt": 0,
        "broker": "Banco ABC",
        "market_value": 1120.50,
        "market_net_value": 1098.20,
    })
    assert res.status_code == 200

    conn = database.get_conn()
    row = dict(conn.execute("SELECT * FROM fixed_income WHERE title_name = 'CDB Banco ABC 115% CDI'").fetchone())
    conn.close()

    assert row["invested_amount"] == pytest.approx(1000.0)
    assert row["market_value"] == pytest.approx(1120.50)
    assert row["market_net_value"] == pytest.approx(1098.20)
    assert row["market_value_date"] == date.today().isoformat()

    calc = calculate_fixed_income_position(row, MACRO)
    assert calc["value_source"] == "MARKET_ANCHOR"
    assert calc["gross_amount"] == pytest.approx(1120.50)
    assert calc["net_amount"] == pytest.approx(1098.20)
    assert calc["gross_profit"] == pytest.approx(120.50)
    assert calc["net_profit"] == pytest.approx(98.20)
