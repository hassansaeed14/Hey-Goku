from __future__ import annotations

from typing import Any, Dict, Optional

from security.audit_logger import log_action, record_audit_event
from security.lock_manager import is_locked
from security.otp_manager import verify_otp
from security.pin_manager import verify_pin
from security.session_manager import get_login_session, is_action_approved
from security.trust_engine import ApprovalType, TrustLevel, evaluate_action


CRITICAL_ACTIONS_REQUIRING_OTP = {
    "password_change",
    "payment",
    "purchase",
    "external_integration",
    "account_delete",
    "owner_transfer",
    "locked_chat_unlock",
}


def _validate_session(
    session_token: Optional[str],
) -> Dict[str, Any]:
    if not session_token:
        return {"valid": False, "reason": "no_session_token", "session": None}
    session = get_login_session(session_token, touch=True)
    if not session:
        return {"valid": False, "reason": "expired_or_missing", "session": None}
    return {"valid": True, "reason": "active", "session": session}


def _requires_otp(action_name: str, trust_level: TrustLevel) -> bool:
    normalized = str(action_name or "").strip().lower()
    if normalized in CRITICAL_ACTIONS_REQUIRING_OTP:
        return True
    return False


def enforce_action(
    action_name: str,
    *,
    username: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: str = "default",
    session_token: Optional[str] = None,
    confirmed: bool = False,
    pin: Optional[str] = None,
    otp: Optional[str] = None,
    otp_token: Optional[str] = None,
    resource_id: Optional[str] = None,
    require_auth: bool = True,
    trust_level_override: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Single centralized guard for every privileged action in AURA.

    Runtime, agents, and tools must route through this before executing a
    sensitive or critical action. Returns a dict with ``allowed`` and the
    reason so callers can uniformly respond.
    """

    action_key = str(action_name or "").strip().lower() or "unknown"
    meta = dict(meta or {})

    if resource_id and is_locked(resource_id):
        event = record_audit_event(
            action_name=action_key,
            allowed=False,
            trust_level="critical",
            reason="resource_locked",
            username=username,
            session_id=session_id,
        )
        log_action(
            action_name=action_key,
            session_id=session_id,
            result="blocked",
            trust_level="critical",
            username=username,
            reason="resource_locked",
            meta=meta,
        )
        return {
            "allowed": False,
            "status": "locked",
            "reason": "Resource is locked.",
            "trust_level": "critical",
            "action_name": action_key,
            "audit": event,
        }

    session_check = _validate_session(session_token) if session_token else {"valid": True, "reason": "not_required", "session": None}
    active_session = session_check.get("session")
    if session_token and not session_check["valid"]:
        event = record_audit_event(
            action_name=action_key,
            allowed=False,
            trust_level="session",
            reason=f"session_{session_check['reason']}",
            username=username,
            session_id=session_id,
        )
        log_action(
            action_name=action_key,
            session_id=session_id,
            result="session_invalid",
            username=username,
            reason=session_check["reason"],
            meta=meta,
        )
        return {
            "allowed": False,
            "status": "session_expired",
            "reason": "Your session has expired. Sign in again to continue.",
            "trust_level": "session",
            "action_name": action_key,
            "audit": event,
        }

    if active_session:
        username = username or active_session.get("username")
        user_id = user_id or active_session.get("user_id")

    pin_verified = bool(verify_pin(pin).get("success")) if pin else False
    session_approved = is_action_approved(session_id, action_key)
    decision = evaluate_action(
        action_key,
        confirmed=confirmed,
        session_approved=session_approved,
        pin_verified=pin_verified,
        trust_level_override=trust_level_override,
    )

    auth_state = {"authenticated": bool(active_session), "session": active_session}
    if require_auth and decision.approval_type != ApprovalType.NONE and not auth_state.get("authenticated"):
        event = record_audit_event(
            action_name=action_key,
            allowed=False,
            trust_level=decision.trust_level.value,
            reason="authentication_required",
            username=username,
            session_id=session_id,
        )
        log_action(
            action_name=action_key,
            session_id=session_id,
            result="auth_required",
            trust_level=decision.trust_level.value,
            username=username,
            reason="authentication_required",
            meta=meta,
        )
        return {
            "allowed": False,
            "status": "auth_required",
            "reason": "Authentication required for this action.",
            "trust_level": decision.trust_level.value,
            "approval_type": decision.approval_type.value,
            "action_name": action_key,
            "audit": event,
        }

    needs_otp = decision.trust_level == TrustLevel.CRITICAL and _requires_otp(action_key, decision.trust_level)
    otp_ok = False
    if needs_otp and otp:
        otp_result = verify_otp(
            str(user_id or username or "anonymous"),
            action_key,
            otp,
            token=otp_token,
        )
        otp_ok = bool(otp_result.get("success"))
        if not otp_ok:
            event = record_audit_event(
                action_name=action_key,
                allowed=False,
                trust_level="critical",
                reason=f"otp_{otp_result.get('status', 'failed')}",
                username=username,
                session_id=session_id,
            )
            log_action(
                action_name=action_key,
                session_id=session_id,
                result="otp_failed",
                trust_level="critical",
                username=username,
                reason=str(otp_result.get("reason") or "OTP verification failed."),
                meta=meta,
            )
            return {
                "allowed": False,
                "status": "otp_required",
                "reason": otp_result.get("reason") or "OTP verification failed.",
                "trust_level": "critical",
                "approval_type": "otp",
                "action_name": action_key,
                "otp": otp_result,
                "audit": event,
            }

    if needs_otp and not otp and not otp_ok:
        event = record_audit_event(
            action_name=action_key,
            allowed=False,
            trust_level="critical",
            reason="otp_required",
            username=username,
            session_id=session_id,
        )
        log_action(
            action_name=action_key,
            session_id=session_id,
            result="otp_required",
            trust_level="critical",
            username=username,
            reason="otp_required",
            meta=meta,
        )
        return {
            "allowed": False,
            "status": "otp_required",
            "reason": "This action requires an OTP sent to your registered phone.",
            "trust_level": "critical",
            "approval_type": "otp",
            "action_name": action_key,
            "audit": event,
        }

    final_allowed = decision.allowed or (needs_otp and otp_ok)
    status = "approved" if final_allowed else decision.approval_type.value
    reason = decision.reason
    if needs_otp and otp_ok:
        reason = "Critical action approved by OTP."

    event = record_audit_event(
        action_name=action_key,
        allowed=final_allowed,
        trust_level=decision.trust_level.value,
        reason=decision.reason_code if not (needs_otp and otp_ok) else "OTP_OK",
        username=username,
        session_id=session_id,
    )
    log_action(
        action_name=action_key,
        session_id=session_id,
        result="allowed" if final_allowed else "blocked",
        trust_level=decision.trust_level.value,
        username=username,
        reason=reason,
        meta=meta,
    )

    return {
        "allowed": final_allowed,
        "status": status,
        "reason": reason,
        "trust_level": decision.trust_level.value,
        "approval_type": decision.approval_type.value if not (needs_otp and otp_ok) else "otp",
        "action_name": action_key,
        "session_approved": session_approved,
        "pin_verified": pin_verified,
        "otp_verified": bool(needs_otp and otp_ok),
        "audit": event,
        "decision": decision.to_dict(),
    }


def record_execution_result(
    action_name: str,
    *,
    session_id: str = "default",
    username: Optional[str] = None,
    success: bool,
    reason: Optional[str] = None,
    trust_level: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Called after an allowed action finishes so the audit trail has the full
    lifecycle: request -> allow -> execute -> success/fail."""

    return log_action(
        action_name=action_name,
        session_id=session_id,
        result="success" if success else "failure",
        trust_level=trust_level,
        username=username,
        reason=reason,
        meta=meta or {},
    )
