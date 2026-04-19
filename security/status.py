"""Read-only aggregated view over the security system state.

This is the "safe system status" surface called for by the hardening spec.
Everything here reads existing state (audit log, PIN manager, OTP ledger,
session store) and returns a summary — it NEVER mutates, and it NEVER
returns secrets (no OTP codes, no PIN hashes, no session tokens).

Used by:
    - ``/api/security/status`` endpoint (operator dashboard)
    - ``brain.runtime_core`` diagnostics
    - Hardening regression tests

Public API:
    recent_blocked_actions(limit=25)
    recent_approvals(limit=25)
    recent_otp_events(limit=25)
    pin_lockout_summary()
    suspicious_events_summary(limit=10)
    security_status_summary(limit=25)
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from security.audit_logger import tail_audit_log
from security.pin_manager import get_pin_status
from security.session_manager import list_login_sessions


_SUSPICIOUS_REASON_SUBSTRINGS = (
    "session_mismatch",
    "invalid_token",
    "too_many_attempts",
    "lockout",
    "reauth_required",
    "resource_locked",
    "otp_failed",
    "otp_incorrect",
    "pin_required",
    "authentication_required",
)


def _safe_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Strip any field that could leak secrets before surfacing an event."""

    allowed_keys = {
        "timestamp", "kind", "action_name", "allowed", "trust_level",
        "reason", "result", "username", "session_id",
    }
    clean = {key: event.get(key) for key in allowed_keys if key in event}
    meta = event.get("meta") or {}
    if isinstance(meta, dict):
        safe_meta: Dict[str, Any] = {}
        for key, value in meta.items():
            if key in {"layer", "agent", "tool_name", "event", "category",
                       "stage", "ttl_seconds", "delivery", "attempts",
                       "failed_attempts", "remaining_seconds",
                       "locked_until", "session_age_seconds"}:
                safe_meta[key] = value
        if safe_meta:
            clean["meta"] = safe_meta
    return clean


def recent_blocked_actions(limit: int = 25) -> List[Dict[str, Any]]:
    """Return the most recent permission denials / blocks."""

    events = tail_audit_log(limit=limit * 8)
    blocked = []
    for event in events:
        result = str(event.get("result") or "").lower()
        allowed = event.get("allowed")
        if result in {"blocked", "auth_required", "session_invalid",
                      "otp_required", "otp_failed", "pin_required",
                      "reauth_required"} or allowed is False:
            blocked.append(_safe_event(event))
    return blocked[-limit:]


def recent_approvals(limit: int = 25) -> List[Dict[str, Any]]:
    """Return the most recent successful permission grants / executions."""

    events = tail_audit_log(limit=limit * 8)
    approvals = []
    for event in events:
        result = str(event.get("result") or "").lower()
        allowed = event.get("allowed")
        if result in {"allowed", "success"} or allowed is True:
            approvals.append(_safe_event(event))
    return approvals[-limit:]


def recent_otp_events(limit: int = 25) -> List[Dict[str, Any]]:
    """OTP request / verify lifecycle events from the audit log."""

    events = tail_audit_log(limit=limit * 8)
    otp_events = [
        _safe_event(event)
        for event in events
        if (event.get("meta") or {}).get("layer") == "otp_manager"
    ]
    return otp_events[-limit:]


def pin_lockout_summary() -> Dict[str, Any]:
    """Surface PIN configuration + current lockout state."""

    status = get_pin_status()
    # Never surface failure history timestamps — counts only.
    recent_failure_count = len(status.get("recent_failures") or [])
    return {
        "configured": bool(status.get("configured")),
        "locked": bool(status.get("locked")),
        "locked_until": status.get("locked_until"),
        "failed_attempts": int(status.get("failed_attempts") or 0),
        "recent_failure_count": recent_failure_count,
    }


def suspicious_events_summary(limit: int = 10) -> Dict[str, Any]:
    """Summarize recent events that look like bypass attempts or brute-force.

    Returns a top-N histogram (action_name + reason) so operators can spot
    an uptick quickly.
    """

    events = tail_audit_log(limit=max(limit * 10, 100))
    suspicious: List[Dict[str, Any]] = []
    for event in events:
        reason = str(event.get("reason") or "").lower()
        if any(snippet in reason for snippet in _SUSPICIOUS_REASON_SUBSTRINGS):
            suspicious.append(_safe_event(event))
    counter: Counter = Counter(
        (event.get("action_name"), event.get("reason"))
        for event in suspicious
    )
    top: List[Dict[str, Any]] = [
        {"action_name": key[0], "reason": key[1], "count": count}
        for key, count in counter.most_common(limit)
    ]
    return {
        "total_matches": len(suspicious),
        "top": top,
        "recent": suspicious[-limit:],
    }


def active_login_session_count() -> int:
    try:
        return len(list_login_sessions() or [])
    except Exception:
        return 0


def security_status_summary(limit: int = 25) -> Dict[str, Any]:
    """Single call that returns everything a status dashboard needs."""

    return {
        "active_login_sessions": active_login_session_count(),
        "pin": pin_lockout_summary(),
        "recent_blocked_actions": recent_blocked_actions(limit=limit),
        "recent_approvals": recent_approvals(limit=limit),
        "recent_otp_events": recent_otp_events(limit=limit),
        "suspicious": suspicious_events_summary(limit=min(limit, 10)),
    }
