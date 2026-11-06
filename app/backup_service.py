"""
Serviço de Backup, Verificação de Integridade e Restauração Segura do SIM (Etapa 5).

Usa a API nativa `sqlite3.Connection.backup` para garantir consistência mesmo com o banco em modo WAL
e valida `PRAGMA integrity_check` + tabelas essenciais antes de qualquer restauração.
"""

import json
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime
from typing import Any, Dict, List

from . import database

REQUIRED_TABLES = {"assets_catalog", "transactions", "fixed_income", "dividends_received"}


def get_backups_dir() -> str:
    base_dir = os.path.dirname(os.path.abspath(database.DB_PATH))
    bdir = os.path.join(base_dir, "backups")
    os.makedirs(bdir, exist_ok=True)
    return bdir


def _sanitize_label(label: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_\-]", "_", (label or "manual").strip())
    return clean[:32] or "manual"


def _validate_backup_id(backup_id: str) -> str:
    bid = (backup_id or "").strip()
    if not bid or ".." in bid or "/" in bid or "\\" in bid or not re.match(r"^[A-Za-z0-9_\-]+$", bid):
        raise ValueError("Identificador de backup inválido.")
    return bid


def verify_sqlite_file(db_path: str) -> Dict[str, Any]:
    """
    Verifica se `db_path` é um arquivo SQLite íntegro e contém as tabelas essenciais do SIM.
    Levanta `ValueError` com mensagem clara em português caso inválido ou corrompido.
    """
    if not db_path or not os.path.isfile(db_path):
        raise ValueError("Arquivo de backup não encontrado.")

    size = os.path.getsize(db_path)
    if size < 100:
        raise ValueError("Arquivo inválido ou vazio (tamanho insuficiente para um banco SQLite).")

    with open(db_path, "rb") as f:
        header = f.read(16)
    if header != b"SQLite format 3\x00":
        raise ValueError("O arquivo selecionado não é um banco de dados SQLite válido.")

    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or str(integrity[0]).lower() != "ok":
            raise ValueError(f"Falha na verificação de integridade do SQLite: {integrity[0] if integrity else 'erro'}")

        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        missing = REQUIRED_TABLES - tables
        if missing:
            raise ValueError(
                f"O banco SQLite não contém as tabelas obrigatórias do SIM (faltando: {', '.join(sorted(missing))})."
            )

        counts: Dict[str, int] = {}
        for tbl in ("transactions", "fixed_income", "dividends_received", "assets_catalog", "portfolio_snapshots", "ai_analysis_history"):
            if tbl in tables:
                counts[tbl] = int(conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0])
            else:
                counts[tbl] = 0
    except sqlite3.DatabaseError as exc:
        raise ValueError(f"Arquivo de banco de dados corrompido ou ilegível: {exc}") from exc
    finally:
        if conn is not None:
            conn.close()

    return {
        "integrity": "ok",
        "size_bytes": size,
        "tables_counts": counts,
    }


def create_backup(label: str = "manual") -> Dict[str, Any]:
    """
    Cria um backup consistente do banco SQLite atual em `backups/<timestamp>_<label>/sim_database.db`
    usando a API online `sqlite3.Connection.backup` e valida sua integridade.
    """
    src_path = os.path.abspath(database.DB_PATH)
    if not os.path.isfile(src_path):
        database.init_db()

    now = datetime.now()
    safe_label = _sanitize_label(label)
    backup_id = f"{now.strftime('%Y%m%d_%H%M%S_%f')[:19]}_{safe_label}"
    bdir = os.path.join(get_backups_dir(), backup_id)
    os.makedirs(bdir, exist_ok=True)
    dst_db_path = os.path.join(bdir, "sim_database.db")

    src_conn = sqlite3.connect(src_path, timeout=30.0)
    dst_conn = sqlite3.connect(dst_db_path, timeout=30.0)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    # Copia também a chave local de criptografia se existir na mesma pasta
    key_src = os.path.join(os.path.dirname(src_path), ".sim_secret.key")
    if os.path.isfile(key_src):
        try:
            shutil.copy2(key_src, os.path.join(bdir, ".sim_secret.key"))
        except Exception:
            pass

    ver = verify_sqlite_file(dst_db_path)
    manifest = {
        "backup_id": backup_id,
        "label": safe_label,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "backup_dir": bdir,
        "size_bytes": ver["size_bytes"],
        "file_size_bytes": ver["size_bytes"],
        "integrity": ver["integrity"],
        "integrity_check": ver["integrity"],
        "tables_counts": ver["tables_counts"],
        "table_counts": ver["tables_counts"],
    }
    with open(os.path.join(bdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest


def list_backups() -> List[Dict[str, Any]]:
    """Lista todos os backups locais disponíveis no diretório `backups/`, ordenados do mais recente ao mais antigo."""
    root = get_backups_dir()
    items: List[Dict[str, Any]] = []
    if not os.path.isdir(root):
        return items

    for entry in sorted(os.listdir(root), reverse=True):
        sub = os.path.join(root, entry)
        if not os.path.isdir(sub):
            continue
        db_file = os.path.join(sub, "sim_database.db")
        manifest_file = os.path.join(sub, "manifest.json")
        if not os.path.isfile(db_file):
            continue
        if os.path.isfile(manifest_file):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    mf = json.load(f)
                mf.setdefault("file_size_bytes", mf.get("size_bytes", 0))
                mf.setdefault("integrity_check", mf.get("integrity", "ok"))
                mf.setdefault("table_counts", mf.get("tables_counts", {}))
                items.append(mf)
                continue
            except Exception:
                pass
        try:
            ver = verify_sqlite_file(db_file)
            mtime = datetime.fromtimestamp(os.path.getmtime(db_file)).strftime("%Y-%m-%d %H:%M:%S")
            items.append({
                "backup_id": entry,
                "label": "local",
                "created_at": mtime,
                "backup_dir": sub,
                "size_bytes": ver["size_bytes"],
                "file_size_bytes": ver["size_bytes"],
                "integrity": ver["integrity"],
                "integrity_check": ver["integrity"],
                "tables_counts": ver["tables_counts"],
                "table_counts": ver["tables_counts"],
            })
        except Exception:
            continue

    items.sort(key=lambda x: (x.get("created_at", ""), x.get("backup_id", "")), reverse=True)
    return items


def get_backup_file_path(backup_id: str) -> str:
    bid = _validate_backup_id(backup_id)
    db_file = os.path.join(get_backups_dir(), bid, "sim_database.db")
    if not os.path.isfile(db_file):
        raise ValueError(f"Backup '{bid}' não encontrado.")
    return db_file


def _restore_verified_file_into_active_db(source_db_path: str) -> Dict[str, Any]:
    """
    Valida `source_db_path`, cria um backup automático de segurança do banco atual
    e restaura os dados usando a API `sqlite3.Connection.backup` seguida de `database.init_db()`.
    """
    ver = verify_sqlite_file(source_db_path)
    safety_backup = create_backup(label="pre_restore_auto")

    target_db_path = os.path.abspath(database.DB_PATH)
    src_conn = sqlite3.connect(source_db_path, timeout=30.0)
    dst_conn = sqlite3.connect(target_db_path, timeout=30.0)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    # Executa migrações aditivas para garantir que bancos de versões anteriores tenham todas as colunas/tabelas
    database.init_db()
    post_ver = verify_sqlite_file(target_db_path)
    return {
        "status": "restored",
        "restored_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "safety_backup_id": safety_backup["backup_id"],
        "pre_restore_backup": safety_backup,
        "integrity": post_ver["integrity"],
        "integrity_check": post_ver["integrity"],
        "tables_counts": post_ver["tables_counts"],
        "table_counts": post_ver["tables_counts"],
        "restored_source_counts": ver["tables_counts"],
    }


def restore_backup(backup_id: str) -> Dict[str, Any]:
    """Restaura um backup existente identificado por `backup_id`."""
    src_db = get_backup_file_path(backup_id)
    res = _restore_verified_file_into_active_db(src_db)
    res["restored_from"] = backup_id
    return res


def restore_from_uploaded_bytes(raw_bytes: bytes, filename: str = "upload.db") -> Dict[str, Any]:
    """Valida e restaura um arquivo `.db` enviado pelo usuário (ex.: via interface)."""
    if not raw_bytes or len(raw_bytes) < 100:
        raise ValueError("O arquivo enviado está vazio ou não é um banco SQLite válido.")

    fd, tmp_path = tempfile.mkstemp(suffix=".db", prefix="sim_restore_")
    os.close(fd)
    try:
        with open(tmp_path, "wb") as f:
            f.write(raw_bytes)
        res = _restore_verified_file_into_active_db(tmp_path)
        res["restored_from"] = filename
        return res
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
