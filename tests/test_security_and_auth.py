"""
Testes abrangentes de segurança, autenticação com PIN, proteção CSRF e isolamento multiusuário do SIM.
"""
import os
import json
import pytest
from fastapi.testclient import TestClient
from app import database
from app.main import app
from app.auth_service import hash_pin, verify_pin, create_user, create_user_session
from app.ai_radar_service import update_app_settings, get_raw_settings
from app.crypto_service import encrypt_secret, decrypt_secret

client = TestClient(app)


def _setup_isolated_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test_sec.db")
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database.init_db()
    return test_db


def test_pin_hashing_and_verification():
    pin = "4819"
    hashed = hash_pin(pin)
    assert hashed != pin
    assert "$" in hashed
    assert verify_pin(pin, hashed) is True
    assert verify_pin("0000", hashed) is False
    assert verify_pin("4818", hashed) is False
    assert verify_pin("", hashed) is False


def test_secrets_encryption_at_rest():
    raw_key = "AIzaSySecretApiKey12345"
    enc = encrypt_secret(raw_key)
    assert enc.startswith("ENC:")
    assert raw_key not in enc
    dec = decrypt_secret(enc)
    assert dec == raw_key


def test_csrf_origin_blocking_on_mutations(tmp_path, monkeypatch):
    _setup_isolated_db(tmp_path, monkeypatch)

    # Requisição com Origin maliciosa (ex: site de phishing tentando chamar /api/portfolio/clear)
    headers = {
        "Origin": "https://malicious-site.com",
    }
    r = client.post("/api/portfolio/clear", json={"confirmation": "CONFIRMAR_ZERAR_CARTEIRA"}, headers=headers)
    assert r.status_code == 403
    assert "CSRF" in r.json().get("detail", "")

    # Requisição com Referer malicioso
    headers_ref = {
        "Referer": "https://evil-attacker.org/steal",
    }
    r_ref = client.post("/api/whatsapp/dispatch-daily", headers=headers_ref)
    assert r_ref.status_code == 403


def test_unauthenticated_requests_rejected(tmp_path, monkeypatch):
    _setup_isolated_db(tmp_path, monkeypatch)

    # Quando um token inválido é fornecido, a API deve rejeitar estritamente com 401
    headers = {"X-SIM-Token": "invalid_fake_token_12345"}
    r = client.get("/api/portfolio", headers=headers)
    assert r.status_code == 401
    assert "Sessão expirada ou PIN inválido" in r.json().get("detail", "")


def test_auth_status_and_pin_setup_flow(tmp_path, monkeypatch):
    _setup_isolated_db(tmp_path, monkeypatch)

    # 1. Status inicial: usuário Lucas criado sem PIN configurado ainda
    r = client.get("/api/auth/status")
    assert r.status_code == 200
    data = r.json()
    assert data["setup_required"] is True

    # 2. Configura PIN de segurança
    r_setup = client.post("/api/auth/setup", json={"username": "Lucas", "pin": "8520"})
    assert r_setup.status_code == 200
    res_setup = r_setup.json()
    assert res_setup["status"] == "ok"
    token = res_setup["token"]
    assert token

    # 3. Com o token, status confirma que está autenticado
    r_stat_auth = client.get("/api/auth/status", headers={"X-SIM-Token": token})
    assert r_stat_auth.status_code == 200
    assert r_stat_auth.json()["authenticated"] is True
    assert r_stat_auth.json()["current_user"]["username"] == "Lucas"

    # 4. Login com PIN errado deve falhar
    r_fail = client.post("/api/auth/login", json={"username": "Lucas", "pin": "0000"})
    assert r_fail.status_code == 401

    # 5. Login com PIN correto
    r_login = client.post("/api/auth/login", json={"username": "Lucas", "pin": "8520"})
    assert r_login.status_code == 200
    new_token = r_login.json()["token"]
    assert new_token


def test_multiuser_isolation_between_accounts(tmp_path, monkeypatch):
    _setup_isolated_db(tmp_path, monkeypatch)

    # Configura Usuário 1 (Lucas)
    r1 = client.post("/api/auth/setup", json={"username": "Lucas", "pin": "1111"})
    token1 = r1.json()["token"]
    headers1 = {"X-SIM-Token": token1}

    # Cadastra Usuário 2 (Amigo Matheus)
    r2 = client.post("/api/auth/register", json={"username": "Matheus", "pin": "2222"})
    assert r2.status_code == 200
    token2 = r2.json()["token"]
    headers2 = {"X-SIM-Token": token2}

    # 1. Usuário 1 adiciona ações de PETR4
    r_add1 = client.post("/api/transactions", json={
        "tx_date": "2026-01-10",
        "ticker": "PETR4",
        "asset_class": "ACAO_BR",
        "tx_type": "BUY",
        "quantity": 100,
        "unit_price": 35.0,
    }, headers=headers1)
    assert r_add1.status_code == 200

    # 2. Usuário 2 adiciona ações de VALE3
    r_add2 = client.post("/api/transactions", json={
        "tx_date": "2026-01-12",
        "ticker": "VALE3",
        "asset_class": "ACAO_BR",
        "tx_type": "BUY",
        "quantity": 50,
        "unit_price": 60.0,
    }, headers=headers2)
    assert r_add2.status_code == 200

    # 3. Verifica carteira do Usuário 1: DEVE conter PETR4 e NÃO VALE3
    port1 = client.get("/api/portfolio", headers=headers1).json()
    tickers1 = [p["ticker"] for p in port1.get("positions", [])]
    assert "PETR4" in tickers1
    assert "VALE3" not in tickers1

    # 4. Verifica carteira do Usuário 2: DEVE conter VALE3 e NÃO PETR4
    port2 = client.get("/api/portfolio", headers=headers2).json()
    tickers2 = [p["ticker"] for p in port2.get("positions", [])]
    assert "VALE3" in tickers2
    assert "PETR4" not in tickers2

    # 5. Configurações isoladas: Usuário 1 define um telefone, Usuário 2 define outro
    client.post("/api/settings", json={"whatsapp_phone": "5511999991111"}, headers=headers1)
    client.post("/api/settings", json={"whatsapp_phone": "5547999992222"}, headers=headers2)

    s1 = client.get("/api/settings", headers=headers1).json()
    s2 = client.get("/api/settings", headers=headers2).json()
    assert s1["whatsapp_phone"] == "5511999991111"
    assert s2["whatsapp_phone"] == "5547999992222"

    # 6. Usuário 2 zera a sua própria carteira: NÃO PODE AFETAR O USUÁRIO 1!
    r_clear2 = client.post("/api/portfolio/clear", json={"confirmation": "CONFIRMAR_ZERAR_CARTEIRA"}, headers=headers2)
    assert r_clear2.status_code == 200

    # Carteira do Usuário 2 agora está vazia
    port2_after = client.get("/api/portfolio", headers=headers2).json()
    assert len(port2_after.get("positions", [])) == 0

    # Carteira do Usuário 1 continua com PETR4 intacta!
    port1_after = client.get("/api/portfolio", headers=headers1).json()
    tickers1_after = [p["ticker"] for p in port1_after.get("positions", [])]
    assert "PETR4" in tickers1_after


def test_api_keys_encrypted_in_database(tmp_path, monkeypatch):
    _setup_isolated_db(tmp_path, monkeypatch)

    r_setup = client.post("/api/auth/setup", json={"username": "Lucas", "pin": "9999"})
    token = r_setup.json()["token"]
    headers = {"X-SIM-Token": token}

    plain_key = "AIzaSySuperSecretGeminiKey123"
    client.post("/api/settings", json={"ai_api_key": plain_key}, headers=headers)

    # Verifica no banco de dados SQLite diretamente se o texto puro NÃO está armazenado
    conn = database.get_conn()
    row = conn.execute("SELECT value FROM app_settings WHERE user_id = 1 AND key = 'ai_api_key'").fetchone()
    conn.close()

    db_value = row["value"]
    assert db_value.startswith("ENC:")
    assert plain_key not in db_value

    # Ao consultar via backend, a chave deve ser descriptografada em memória para chamadas de IA
    raw = get_raw_settings(user_id=1)
    assert raw["ai_api_key"] == plain_key
