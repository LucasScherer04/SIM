"""
Teste de segurança: /api/portfolio/clear exige confirmação explícita.
"""
from fastapi.testclient import TestClient
from app import database
from app.main import app

client = TestClient(app)


def test_clear_portfolio_requires_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.db"))
    database.init_db()

    conn = database.get_conn()
    conn.execute("INSERT INTO transactions (tx_date, ticker, asset_class, tx_type, quantity, unit_price) VALUES ('2024-01-01', 'ITUB4', 'ACAO_BR', 'BUY', 10, 30.0)")
    conn.commit()
    conn.close()

    # Sem payload ou com payload vazio deve falhar por segurança (sem apagar sem confirmação explícita)
    r = client.post("/api/portfolio/clear", json={})
    assert r.status_code in (400, 422)
    # Com confirmação inválida deve retornar 400
    r2 = client.post("/api/portfolio/clear", json={"confirmation": "INVALIDO"})
    assert r2.status_code == 400

    # Com confirmação correta
    r3 = client.post("/api/portfolio/clear", json={"confirmation": "CONFIRMAR_ZERAR_CARTEIRA"})
    assert r3.status_code == 200
    assert r3.json()["status"] == "ok"

    conn = database.get_conn()
    count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()
    assert count == 0
