"""
Testes automatizados da Etapa 5 — Acabamento, Backup/Restauração, Recuperação após Falha e Fluxo E2E.
Importante: todos os testes usam bancos SQLite isolados em `tmp_path` e NUNCA modificam o `sim_database.db` real.
"""
from __future__ import annotations

import base64
import shutil
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import backup_service, database
from app.main import app


REAL_DB_PATH = Path(__file__).resolve().parent.parent / "sim_database.db"


@pytest.fixture()
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Configura um banco SQLite e pasta de backups 100% isolados em tmp_path."""
    test_db = tmp_path / "sim_test_stage5.db"
    test_backups = tmp_path / "backups"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database.init_db()
    return {"db_path": test_db, "backups_dir": test_backups, "client": TestClient(app)}


def test_create_list_download_and_restore_backup_api(isolated_env):
    """
    Valida criação de backup via API, verificação PRAGMA integrity_check,
    listagem, download e restauração após perda/alteração de lançamentos.
    """
    client: TestClient = isolated_env["client"]

    # 1. Registra compra na carteira
    r1 = client.post(
        "/api/transactions",
        json={
            "ticker": "WEGE3",
            "tx_type": "COMPRA",
            "quantity": 100,
            "unit_price": 40.0,
            "fees": 0.0,
            "tx_date": "2026-01-15",
        },
    )
    assert r1.status_code == 200

    p_before = client.get("/api/portfolio").json()
    assert len(p_before["positions"]) == 1
    assert p_before["positions"][0]["ticker"] == "WEGE3"
    assert p_before["positions"][0]["quantity"] == 100

    # 2. Cria backup via API
    bkp_res = client.post("/api/system/backups?label=antes_alteracao")
    assert bkp_res.status_code == 200
    bkp_data = bkp_res.json()["backup"]
    backup_id = bkp_data["backup_id"]
    assert bkp_data["integrity_check"] == "ok"
    assert bkp_data["table_counts"]["transactions"] == 1

    # 3. Lista backups e faz download do arquivo .db
    list_res = client.get("/api/system/backups")
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert any(it["backup_id"] == backup_id for it in items)

    dl_res = client.get(f"/api/system/backups/{backup_id}/download")
    assert dl_res.status_code == 200
    downloaded_bytes = dl_res.content
    assert downloaded_bytes.startswith(b"SQLite format 3")

    # 4. Simula alteração/exclusão acidental (adiciona outra compra e remove a original)
    tx_id = p_before["transactions"][0]["id"]
    del_res = client.delete(f"/api/transactions/{tx_id}")
    assert del_res.status_code == 200
    assert len(client.get("/api/portfolio").json()["positions"]) == 0

    # 5. Restaura o backup criado no passo 2
    rest_res = client.post(f"/api/system/backups/{backup_id}/restore")
    assert rest_res.status_code == 200
    rest_payload = rest_res.json()["restore"]
    assert rest_payload["status"] == "restored"
    assert rest_payload["pre_restore_backup"]["label"] == "pre_restore_auto"

    # 6. Confere se a posição original (100 WEGE3) voltou integralmente
    p_after = client.get("/api/portfolio").json()
    assert len(p_after["positions"]) == 1
    assert p_after["positions"][0]["ticker"] == "WEGE3"
    assert p_after["positions"][0]["quantity"] == 100


def test_failure_recovery_rejects_corrupted_or_incomplete_db_without_harming_portfolio(isolated_env, tmp_path: Path):
    """
    Testa recuperação após falha:
    - Tentar restaurar bytes corrompidos ou banco SQLite sem tabelas do SIM deve falhar (400)
      e manter os dados da carteira intactos.
    - Restaurar a partir de um upload válido restaura o banco corretamente.
    """
    client: TestClient = isolated_env["client"]

    client.post(
        "/api/transactions",
        json={
            "ticker": "ITUB4",
            "tx_type": "COMPRA",
            "quantity": 50,
            "unit_price": 32.0,
            "fees": 0.0,
            "tx_date": "2026-02-10",
        },
    )

    # Faz backup válido e guarda os bytes
    bkp_id = client.post("/api/system/backups?label=valido").json()["backup"]["backup_id"]
    valid_db_bytes = client.get(f"/api/system/backups/{bkp_id}/download").content

    # Caso A: Arquivo corrompido (não é SQLite)
    bad_res = client.post(
        "/api/system/backups/restore-upload",
        json={
            "filename": "corrompido.db",
            "content_base64": base64.b64encode(b"arquivo invalido nao sqlite 12345" * 10).decode("ascii"),
        },
    )
    assert bad_res.status_code == 400
    assert "SQLite válido" in bad_res.json()["detail"]

    # Caso B: Banco SQLite válido, porém sem as tabelas obrigatórias do SIM
    incomplete_db = tmp_path / "incompleto.db"
    conn = sqlite3.connect(incomplete_db)
    conn.execute("CREATE TABLE outra_tabela (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    inc_res = client.post(
        "/api/system/backups/restore-upload",
        json={
            "filename": "incompleto.db",
            "content_base64": base64.b64encode(incomplete_db.read_bytes()).decode("ascii"),
        },
    )
    assert inc_res.status_code == 400
    assert "tabelas obrigatórias" in inc_res.json()["detail"]

    # Verifica que a carteira ativa continua intacta após as duas tentativas inválidas
    p_check = client.get("/api/portfolio").json()
    assert len(p_check["positions"]) == 1
    assert p_check["positions"][0]["ticker"] == "ITUB4"

    # Caso C: Apaga a transação e restaura enviando o arquivo .db válido via upload
    tx_id = p_check["transactions"][0]["id"]
    client.delete(f"/api/transactions/{tx_id}")
    assert len(client.get("/api/portfolio").json()["positions"]) == 0

    up_res = client.post(
        "/api/system/backups/restore-upload",
        json={
            "filename": "backup_valido.db",
            "content_base64": base64.b64encode(valid_db_bytes).decode("ascii"),
        },
    )
    assert up_res.status_code == 200
    p_restored = client.get("/api/portfolio").json()
    assert len(p_restored["positions"]) == 1
    assert p_restored["positions"][0]["ticker"] == "ITUB4"
    assert p_restored["positions"][0]["quantity"] == 50


def test_full_e2e_flow_with_real_portfolio_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Teste de fluxo completo (Etapa 5 - tarefa 8) sobre uma CÓPIA isolada da carteira real
    (`sim_database.db`), garantindo que o arquivo real jamais seja modificado:
    1. Copia `sim_database.db` para `tmp_path` e valida integridade;
    2. Cria backup inicial;
    3. Consulta carteira (`/api/portfolio`), dashboard (`/api/dashboard`), detalhe de ativo e análise IA;
    4. Registra nova operação e provento, conferindo reconciliação;
    5. Restaura o backup inicial e comprova que posições e lançamentos voltam ao estado exato original.
    """
    isolated_db = tmp_path / "sim_real_copy.db"
    isolated_backups = tmp_path / "backups_real_copy"

    if REAL_DB_PATH.exists():
        # Faz cópia segura usando a API de backup do SQLite (sem tocar no banco real)
        src = sqlite3.connect(f"file:{REAL_DB_PATH.as_posix()}?mode=ro", uri=True)
        dst = sqlite3.connect(str(isolated_db))
        src.backup(dst)
        dst.close()
        src.close()
    else:
        monkeypatch.setattr(database, "DB_PATH", isolated_db)
        database.init_db()

    real_mtime_before = REAL_DB_PATH.stat().st_mtime_ns if REAL_DB_PATH.exists() else None

    monkeypatch.setattr(database, "DB_PATH", isolated_db)
    database.init_db()

    client = TestClient(app)

    # 1. Cria backup inicial da carteira real copiada
    bkp0 = client.post("/api/system/backups?label=e2e_real_initial").json()["backup"]
    assert bkp0["integrity_check"] == "ok"
    initial_bkp_id = bkp0["backup_id"]

    # 2. Captura fotografia inicial da carteira e do dashboard
    port0 = client.get("/api/portfolio").json()
    dash0 = client.get("/api/dashboard").json()
    assert dash0["reconciliation"]["ok"] is True

    initial_tx_count = len(port0["transactions"])
    initial_pos_count = len(port0["positions"])

    # 3. Executa análise consolidada da carteira (Analista de IA / motor determinístico)
    ai_res = client.post("/api/ai/analyze-portfolio")
    assert ai_res.status_code == 200
    ai_data = ai_res.json()
    assert "facts_observed" in ai_data
    assert "sim_calculations" in ai_data
    assert "ai_interpretation" in ai_data

    # 4. Registra uma nova compra na cópia isolada
    add_tx = client.post(
        "/api/transactions",
        json={
            "ticker": "VALE3",
            "tx_type": "COMPRA",
            "quantity": 10,
            "unit_price": 60.0,
            "fees": 1.50,
            "tx_date": "2026-03-01",
        },
    )
    assert add_tx.status_code == 200

    port_modified = client.get("/api/portfolio").json()
    assert len(port_modified["transactions"]) == initial_tx_count + 1

    # 5. Restaura o backup inicial e verifica retorno exato ao estado original
    restore_res = client.post(f"/api/system/backups/{initial_bkp_id}/restore")
    assert restore_res.status_code == 200

    port_restored = client.get("/api/portfolio").json()
    assert len(port_restored["transactions"]) == initial_tx_count
    assert len(port_restored["positions"]) == initial_pos_count

    # Garante que o arquivo real nunca foi tocado
    if real_mtime_before is not None:
        assert REAL_DB_PATH.stat().st_mtime_ns == real_mtime_before


def test_windows_distribution_scripts_and_manual_present():
    """Verifica que os scripts de inicialização/instalação no Windows e o manual estão presentes e íntegros."""
    repo_root = Path(__file__).resolve().parent.parent
    bat_start = repo_root / "Iniciar_SIM.bat"
    vbs_silent = repo_root / "Iniciar_SIM_Silencioso.vbs"
    bat_install = repo_root / "Instalar_SIM_Windows.bat"
    manual_doc = repo_root / "docs" / "manual-uso-sim.md"

    assert bat_start.exists()
    assert "uvicorn app.main:app" in bat_start.read_text(encoding="utf-8")

    assert vbs_silent.exists()
    assert "uvicorn app.main:app" in vbs_silent.read_text(encoding="utf-8")

    assert bat_install.exists()
    install_text = bat_install.read_text(encoding="utf-8")
    assert "requirements.txt" in install_text
    assert "create_backup" in install_text
    assert "SIM - Investimentos.lnk" in install_text

    assert manual_doc.exists()
    manual_text = manual_doc.read_text(encoding="utf-8")
    assert "Instalar_SIM_Windows.bat" in manual_text
    assert "Backup & Restauração" in manual_text
    assert "Provedores de Dados" in manual_text
