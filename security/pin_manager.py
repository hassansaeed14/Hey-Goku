from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from security.audit_logger import log_action
from security.encryption_utils import hash_secret, verify_secret
from security.security_config import PIN_LOCKOUT_DELTA, PIN_RETRY_LIMIT


PIN_STATE_FILE = Path("memory/pin_state.json")


def _default_state() -> Dict[str, object]:
    return {
        "pin_hash": None,
        "failed_attempts": 0,
        "locked_until": None,
        "updated_at": None,
        "last_failure_at": None,
        "failure_history": [],  # rolling list of recent failure timestamps
    }


def _load_state() -> Dict[str, object]:
    if not PIN_STATE_FILE.exists():
        return _default_state()
    try:
        payload = json.loads(PIN_STATE_FILE.read_text(encoding="utf-8"))
        return {**_default_state(), **payload}
    except Exception:
        return _default_state()


def _save_state(payload: Dict[str, object]) -> None:
    PIN_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    PIN_STATE_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _audit(event: str, *, success: bool, reason: str,
           username: Optional[str] = None,
           session_id: Optional[str] = None,
           meta: Optional[Dict[str, object]] = None) -> None:
    try:
        log_action(
            action_name="pin_verify" if event == "verify" else f"pin_{event}",
            session_id=str(session_id or "pin"),
            result="success" if success else "failure",
            trust_level="critical",
            username=username,
            reason=reason,
            meta={"layer": "pin_manager", "event": event, **dict(meta or {})},
        )
    except Exception:
        pass


def has_pin() -> bool:
    return bool(_load_state().get("pin_hash"))


def set_pin(pin: str, *, username: Optional[str] = None) -> Dict[str, object]:
    normalized = str(pin or "").strip()
    if not normalized.isdigit() or len(normalized) < 4:
        _audit("set", success=False, reason="too_short_or_non_numeric", username=username)
        return {"success": False, "reason": "PIN must be at least 4 digits."}

    payload = _default_state()
    payload["pin_hash"] = hash_secret(normalized)
    _save_state(payload)
    _audit("set", success=True, reason="pin_saved", username=username)
    return {"success": True, "reason": "PIN saved."}


def verify_pin(pin: str, *, username: Optional[str] = None,
               session_id: Optional[str] = None) -> Dict[str, object]:
    payload = _load_state()
    if not payload.get("pin_hash"):
        _audit("verify", success=False, reason="pin_not_configured",
               username=username, session_id=session_id)
        return {"success": False, "reason": "PIN is not configured.", "status": "not_configured"}

    locked_until = payload.get("locked_until")
    if locked_until:
        try:
            locked_dt = datetime.fromisoformat(str(locked_until))
            if datetime.now() < locked_dt:
                remaining = int((locked_dt - datetime.now()).total_seconds())
                _audit("verify", success=False, reason="locked",
                       username=username, session_id=session_id,
                       meta={"remaining_seconds": remaining})
                return {
                    "success": False,
                    "reason": "PIN entry is temporarily locked.",
                    "status": "locked",
                    "locked_until": str(locked_until),
                    "remaining_seconds": remaining,
                }
        except Exception:
            payload["locked_until"] = None

    if verify_secret(str(pin or "").strip(), str(payload["pin_hash"])):
        payload["failed_attempts"] = 0
        payload["locked_until"] = None
        _save_state(payload)
        _audit("verify", success=True, reason="pin_verified",
               username=username, session_id=session_id)
        return {"success": True, "reason": "PIN verified.", "status": "verified"}

    payload["failed_attempts"] = int(payload.get("failed_attempts", 0)) + 1
    payload["last_failure_at"] = datetime.now().isoformat()
    history = list(payload.get("failure_history") or [])
    history.append(payload["last_failure_at"])
    payload["failure_history"] = history[-20:]  # cap rolling window
    if payload["failed_attempts"] >= PIN_RETRY_LIMIT:
        payload["locked_until"] = (datetime.now() + PIN_LOCKOUT_DELTA).isoformat()
        _save_state(payload)
        _audit("verify", success=False, reason="lockout_triggered",
               username=username, session_id=session_id,
               meta={
                   "failed_attempts": payload["failed_attempts"],
                   "locked_until": payload["locked_until"],
               })
        return {
            "success": False,
            "reason": "Incorrect PIN. Too many failed attempts — locked.",
            "status": "locked",
            "failed_attempts": payload["failed_attempts"],
            "locked_until": payload["locked_until"],
        }
    _save_state(payload)
    _audit("verify", success=False, reason="incorrect_pin",
           username=username, session_id=session_id,
           meta={"failed_attempts": payload["failed_attempts"]})
    return {
        "success": False,
        "reason": "Incorrect PIN.",
        "status": "denied",
        "failed_attempts": payload["failed_attempts"],
        "attempts_remaining": max(PIN_RETRY_LIMIT - int(payload["failed_attempts"]), 0),
    }


def get_pin_status() -> Dict[str, object]:
    payload = _load_state()
    locked = False
    locked_until = payload.get("locked_until")
    if locked_until:
        try:
            locked = datetime.now() < datetime.fromisoformat(str(locked_until))
        except Exception:
            locked = False
    return {
        "configured": bool(payload.get("pin_hash")),
        "failed_attempts": int(payload.get("failed_attempts", 0)),
        "locked": locked,
        "locked_until": payload.get("locked_until"),
        "last_failure_at": payload.get("last_failure_at"),
        "recent_failures": list(payload.get("failure_history") or [])[-5:],
    }


def reset_pin_lockout(*, username: Optional[str] = None) -> Dict[str, object]:
    """Administrative helper — clears failed_attempts + locked_until.

    This is intentionally NOT a user-facing path; callers must ensure the
    operator has already re-authenticated.
    """

    payload = _load_state()
    payload["failed_attempts"] = 0
    payload["locked_until"] = None
    _save_state(payload)
    _audit("reset_lockout", success=True, reason="lockout_cleared",
           username=username)
    return {"success": True, "reason": "PIN lockout cleared."}
