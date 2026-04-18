from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from security.encryption_utils import hash_secret, verify_secret
from security.phone_registry import get_phone


OTP_STATE_FILE = Path("memory/otp_state.json")
OTP_EXPIRY_SECONDS = 120
OTP_MAX_ATTEMPTS = 5
OTP_CODE_LENGTH = 6


def _now() -> datetime:
    return datetime.utcnow()


def _load_state() -> Dict[str, Dict[str, object]]:
    if not OTP_STATE_FILE.exists():
        return {}
    try:
        payload = json.loads(OTP_STATE_FILE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_state(payload: Dict[str, Dict[str, object]]) -> None:
    OTP_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    OTP_STATE_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _generate_code() -> str:
    return f"{secrets.randbelow(10 ** OTP_CODE_LENGTH):0{OTP_CODE_LENGTH}d}"


def _key(user_id: str, action_name: str) -> str:
    return f"{str(user_id or '').strip()}::{str(action_name or '').strip().lower()}"


def request_otp(
    user_id: str,
    action_name: str,
    *,
    purpose: Optional[str] = None,
    ttl_seconds: int = OTP_EXPIRY_SECONDS,
) -> Dict[str, object]:
    user_key = str(user_id or "").strip()
    if not user_key:
        return {"success": False, "reason": "user_id is required.", "status": "missing_user"}
    if not action_name:
        return {"success": False, "reason": "action_name is required.", "status": "missing_action"}

    phone_entry = get_phone(user_key)
    phone_number = None
    if phone_entry:
        phone_number = str(phone_entry.get("phone") or "")

    code = _generate_code()
    token = secrets.token_urlsafe(18)
    expires_at = (_now() + timedelta(seconds=int(ttl_seconds))).isoformat()

    payload = _load_state()
    payload[_key(user_key, action_name)] = {
        "token": token,
        "code_hash": hash_secret(code),
        "action_name": str(action_name).strip().lower(),
        "user_id": user_key,
        "purpose": purpose or "",
        "issued_at": _now().isoformat(),
        "expires_at": expires_at,
        "attempts": 0,
        "consumed": False,
        "phone_recipient": phone_number or None,
    }
    _save_state(payload)

    return {
        "success": True,
        "status": "issued",
        "token": token,
        "code": code,
        "action_name": str(action_name).strip().lower(),
        "expires_at": expires_at,
        "expires_in_seconds": int(ttl_seconds),
        "phone_recipient": phone_number,
        "delivery": "phone" if phone_number else "local",
    }


def verify_otp(
    user_id: str,
    action_name: str,
    code: str,
    *,
    token: Optional[str] = None,
) -> Dict[str, object]:
    user_key = str(user_id or "").strip()
    action_key = str(action_name or "").strip().lower()
    entry_key = _key(user_key, action_key)

    payload = _load_state()
    entry = payload.get(entry_key)
    if not entry:
        return {"success": False, "status": "not_found", "reason": "No OTP has been issued for this action."}

    try:
        expires_at = datetime.fromisoformat(str(entry.get("expires_at")))
    except Exception:
        payload.pop(entry_key, None)
        _save_state(payload)
        return {"success": False, "status": "expired", "reason": "OTP expired."}

    if entry.get("consumed"):
        return {"success": False, "status": "consumed", "reason": "OTP already used."}

    if _now() > expires_at:
        payload.pop(entry_key, None)
        _save_state(payload)
        return {"success": False, "status": "expired", "reason": "OTP expired."}

    if token and str(token) != str(entry.get("token")):
        return {"success": False, "status": "invalid_token", "reason": "OTP token mismatch."}

    attempts = int(entry.get("attempts", 0))
    if attempts >= OTP_MAX_ATTEMPTS:
        payload.pop(entry_key, None)
        _save_state(payload)
        return {"success": False, "status": "too_many_attempts", "reason": "Too many failed attempts. Request a new OTP."}

    if not verify_secret(str(code or "").strip(), str(entry.get("code_hash") or "")):
        entry["attempts"] = attempts + 1
        payload[entry_key] = entry
        _save_state(payload)
        return {
            "success": False,
            "status": "incorrect",
            "reason": "Incorrect OTP.",
            "attempts_remaining": max(OTP_MAX_ATTEMPTS - entry["attempts"], 0),
        }

    entry["consumed"] = True
    entry["verified_at"] = _now().isoformat()
    payload[entry_key] = entry
    _save_state(payload)
    return {"success": True, "status": "verified", "reason": "OTP verified.", "action_name": action_key}


def invalidate_otp(user_id: str, action_name: str) -> bool:
    payload = _load_state()
    key = _key(user_id, action_name)
    if key in payload:
        payload.pop(key, None)
        _save_state(payload)
        return True
    return False


def get_otp_status(user_id: str, action_name: str) -> Dict[str, object]:
    payload = _load_state()
    entry = payload.get(_key(user_id, action_name))
    if not entry:
        return {"exists": False}
    try:
        expires_at = datetime.fromisoformat(str(entry.get("expires_at")))
        expired = _now() > expires_at
    except Exception:
        expired = True
    return {
        "exists": True,
        "issued_at": entry.get("issued_at"),
        "expires_at": entry.get("expires_at"),
        "consumed": bool(entry.get("consumed")),
        "expired": expired,
        "attempts": int(entry.get("attempts", 0)),
    }


def cleanup_expired() -> int:
    payload = _load_state()
    removed = 0
    for key, entry in list(payload.items()):
        try:
            expires_at = datetime.fromisoformat(str(entry.get("expires_at")))
        except Exception:
            payload.pop(key, None)
            removed += 1
            continue
        if _now() > expires_at or entry.get("consumed"):
            payload.pop(key, None)
            removed += 1
    if removed:
        _save_state(payload)
    return removed
