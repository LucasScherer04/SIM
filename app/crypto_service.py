import os
import base64
from typing import Optional
from cryptography.fernet import Fernet

KEY_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".sim_secret.key")


def _get_or_create_key() -> bytes:
    """
    Obtém ou gera a chave mestra de criptografia do SIM.
    A chave é salva com permissões restritas.
    """
    if os.path.exists(KEY_FILE_PATH):
        try:
            with open(KEY_FILE_PATH, "rb") as f:
                key = f.read().strip()
                if key:
                    return key
        except Exception:
            pass

    key = Fernet.generate_key()
    try:
        with open(KEY_FILE_PATH, "wb") as f:
            f.write(key)
        # Tenta restringir permissão no sistema de arquivos se aplicável
        try:
            os.chmod(KEY_FILE_PATH, 0o600)
        except Exception:
            pass
    except Exception:
        pass
    return key


_FERNET_INSTANCE: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _FERNET_INSTANCE
    if _FERNET_INSTANCE is None:
        _FERNET_INSTANCE = Fernet(_get_or_create_key())
    return _FERNET_INSTANCE


def encrypt_secret(plaintext: str) -> str:
    """
    Criptografa uma string sensível (ex: chave de API) usando Fernet (AES-128-CBC + HMAC-SHA256).
    Retorna com o prefixo 'ENC:' para identificação.
    """
    if not plaintext or not plaintext.strip():
        return ""
    clean = plaintext.strip()
    if clean.startswith("ENC:"):
        return clean  # Já está criptografado
    try:
        f = _get_fernet()
        token = f.encrypt(clean.encode("utf-8")).decode("utf-8")
        return f"ENC:{token}"
    except Exception as exc:
        # Fallback defensivo se houver erro inesperado
        return clean


def decrypt_secret(ciphertext: str) -> str:
    """
    Descriptografa um segredo previamente criptografado.
    Se não começar com 'ENC:', retorna o valor como está (compatibilidade com texto legado).
    """
    if not ciphertext or not ciphertext.strip():
        return ""
    clean = ciphertext.strip()
    if not clean.startswith("ENC:"):
        return clean  # Legado em texto puro

    raw_token = clean[4:]
    try:
        f = _get_fernet()
        return f.decrypt(raw_token.encode("utf-8")).decode("utf-8")
    except Exception:
        # Falha na descriptografia (ex: chave rotacionada ou token corrompido)
        return ""
