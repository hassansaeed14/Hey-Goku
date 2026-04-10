from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from security.security_config import SECURITY_KEY_FILE


PBKDF2_ROUNDS = 120_000


def hash_secret(value: str, *, salt: str | None = None) -> str:
    raw_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), raw_salt.encode("utf-8"), PBKDF2_ROUNDS)
    return f"{raw_salt}${base64.b64encode(digest).decode('utf-8')}"


def verify_secret(value: str, hashed_value: str) -> bool:
    try:
        salt, encoded = hashed_value.split("$", 1)
    except ValueError:
        return False
    expected = hash_secret(value, salt=salt)
    return hmac.compare_digest(expected, f"{salt}${encoded}")


def generate_token(length: int = 24) -> str:
    return secrets.token_urlsafe(length)


def _load_or_create_key() -> bytes:
    if SECURITY_KEY_FILE.exists():
        return SECURITY_KEY_FILE.read_bytes().strip()
    SECURITY_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    SECURITY_KEY_FILE.write_bytes(key)
    return key


def get_fernet() -> Fernet:
    return Fernet(_load_or_create_key())


def encrypt_payload(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return get_fernet().encrypt(serialized).decode("utf-8")


def decrypt_payload(payload: str, *, default: Any = None) -> Any:
    text = str(payload or "").strip()
    if not text:
        return default
    try:
        return json.loads(get_fernet().decrypt(text.encode("utf-8")).decode("utf-8"))
    except (InvalidToken, json.JSONDecodeError, ValueError):
        try:
            return json.loads(text)
        except Exception:
            return default


def save_encrypted_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encrypt_payload(payload), encoding="utf-8")


def load_encrypted_json(path: Path, *, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return decrypt_payload(path.read_text(encoding="utf-8"), default=default)
    except Exception:
        return default
