import base64
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


KEY_FILE = Path(__file__).resolve().parent.parent / "data" / "model_config.key"


def _fernet_key() -> bytes:
    configured = os.getenv("MODEL_CONFIG_SECRET")
    if configured:
        return base64.urlsafe_b64encode(hashlib.sha256(configured.encode("utf-8")).digest())
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes().strip()
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    KEY_FILE.write_bytes(key)
    return key


def encrypt_secret(value: str) -> str:
    return Fernet(_fernet_key()).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str) -> str:
    try:
        return Fernet(_fernet_key()).decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("模型 API Key 无法解密，请在模型管理中重新设置") from exc
