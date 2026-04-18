# security/trust_engine.py

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class TrustLevel(str, Enum):
    SAFE = "safe"
    PRIVATE = "private"
    SENSITIVE = "sensitive"
    CRITICAL = "critical"


class ApprovalType(str, Enum):
    NONE = "none"
    CONFIRM = "confirm"
    SESSION_APPROVAL = "session_approval"
    PIN = "pin"


@dataclass(frozen=True)
class TrustDecision:
    action_name: str
    trust_level: TrustLevel
    approval_type: ApprovalType
    allowed: bool
    reason: str
    reason_code: str
    policy_source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_name": self.action_name,
            "trust_level": self.trust_level.value,
            "approval_type": self.approval_type.value,
            "allowed": self.allowed,
            "reason": self.reason,
            "reason_code": self.reason_code,
            "policy_source": self.policy_source,
            "requires_approval": self.approval_type != ApprovalType.NONE,
            "requires_pin": self.approval_type == ApprovalType.PIN,
        }


ACTION_TRUST_MAP: Dict[str, TrustLevel] = {
    # SAFE
    "general": TrustLevel.SAFE,
    "greeting": TrustLevel.SAFE,
    "identity": TrustLevel.SAFE,
    "time": TrustLevel.SAFE,
    "date": TrustLevel.SAFE,
    "weather": TrustLevel.SAFE,
    "news": TrustLevel.SAFE,
    "math": TrustLevel.SAFE,
    "dictionary": TrustLevel.SAFE,
    "quote": TrustLevel.SAFE,
    "joke": TrustLevel.SAFE,
    "translation": TrustLevel.SAFE,
    "grammar": TrustLevel.SAFE,
    "quiz": TrustLevel.SAFE,
    "summarize": TrustLevel.SAFE,
    "study": TrustLevel.SAFE,
    "research": TrustLevel.SAFE,
    "coding": TrustLevel.SAFE,
    "reasoning": TrustLevel.SAFE,
    "compare": TrustLevel.SAFE,
    "web_search": TrustLevel.SAFE,
    "youtube": TrustLevel.SAFE,
    "currency": TrustLevel.SAFE,
    "crypto": TrustLevel.SAFE,
    "synonyms": TrustLevel.SAFE,
    "permission": TrustLevel.SAFE,
    "task": TrustLevel.SAFE,
    "task_read": TrustLevel.SAFE,
    "task_add": TrustLevel.SAFE,
    "task_complete": TrustLevel.SAFE,
    "task_delete": TrustLevel.SAFE,
    "task_plan": TrustLevel.SAFE,
    "reminder": TrustLevel.SAFE,
    "reminder_read": TrustLevel.SAFE,
    "reminder_add": TrustLevel.SAFE,
    "reminder_complete": TrustLevel.SAFE,
    "reminder_delete": TrustLevel.SAFE,
    "password": TrustLevel.SAFE,
    "planner_agent": TrustLevel.SAFE,
    "tool_selector": TrustLevel.SAFE,
    "debug_agent": TrustLevel.SAFE,
    "document": TrustLevel.SAFE,
    "document_generation": TrustLevel.SAFE,
    "document_generator": TrustLevel.SAFE,
    "document_export": TrustLevel.SAFE,
    "content_transformation": TrustLevel.SAFE,
    "content_transform": TrustLevel.SAFE,
    "media_transform": TrustLevel.SAFE,
    "diagram_generation": TrustLevel.SAFE,
    "slides": TrustLevel.SAFE,
    "notes": TrustLevel.SAFE,
    "assignment": TrustLevel.SAFE,

    # PRIVATE
    "memory_read": TrustLevel.PRIVATE,
    "history": TrustLevel.PRIVATE,
    "insights": TrustLevel.PRIVATE,
    "file": TrustLevel.PRIVATE,
    "file_read": TrustLevel.PRIVATE,
    "list_files": TrustLevel.PRIVATE,
    "file_list": TrustLevel.PRIVATE,
    "profile_read": TrustLevel.PRIVATE,
    "system_read": TrustLevel.PRIVATE,

    # SENSITIVE
    "auth_login": TrustLevel.SENSITIVE,
    "auth_register": TrustLevel.SENSITIVE,
    "memory_write": TrustLevel.SENSITIVE,
    "settings_update": TrustLevel.SENSITIVE,
    "screenshot": TrustLevel.SENSITIVE,
    "file_write": TrustLevel.SENSITIVE,
    "file_upload": TrustLevel.SENSITIVE,
    "executor": TrustLevel.SENSITIVE,

    # CRITICAL
    "payment": TrustLevel.CRITICAL,
    "purchase": TrustLevel.CRITICAL,
    "system_control": TrustLevel.CRITICAL,
    "pc_control": TrustLevel.CRITICAL,
    "file_delete": TrustLevel.CRITICAL,
    "account_delete": TrustLevel.CRITICAL,
    "locked_chat_unlock": TrustLevel.CRITICAL,
    "password_change": TrustLevel.CRITICAL,
    "external_integration": TrustLevel.CRITICAL,
    "owner_transfer": TrustLevel.CRITICAL,
    "phone_register": TrustLevel.CRITICAL,
}


LEVEL_TO_APPROVAL: Dict[TrustLevel, ApprovalType] = {
    TrustLevel.SAFE: ApprovalType.NONE,
    TrustLevel.PRIVATE: ApprovalType.CONFIRM,
    TrustLevel.SENSITIVE: ApprovalType.SESSION_APPROVAL,
    TrustLevel.CRITICAL: ApprovalType.PIN,
}


def normalize_action_name(action_name: Optional[str]) -> str:
    if not action_name:
        return "general"
    return action_name.strip().lower().replace(" ", "_")


def get_trust_level(action_name: Optional[str]) -> TrustLevel:
    normalized = normalize_action_name(action_name)
    return ACTION_TRUST_MAP.get(normalized, TrustLevel.SENSITIVE)


def coerce_trust_level(value: Optional[str]) -> Optional[TrustLevel]:
    if value is None:
        return None
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    try:
        return TrustLevel(normalized)
    except ValueError:
        return None


def get_approval_type(trust_level: TrustLevel) -> ApprovalType:
    return LEVEL_TO_APPROVAL[trust_level]


def get_policy_source(action_name: Optional[str]) -> str:
    normalized = normalize_action_name(action_name)
    if normalized in ACTION_TRUST_MAP:
        return "action_trust_map"
    return "default_sensitive_fallback"


def evaluate_action(
    action_name: Optional[str],
    *,
    confirmed: bool = False,
    session_approved: bool = False,
    pin_verified: bool = False,
    trust_level_override: Optional[str] = None,
) -> TrustDecision:
    normalized = normalize_action_name(action_name)
    override_level = coerce_trust_level(trust_level_override)
    trust_level = override_level or get_trust_level(normalized)
    approval_type = get_approval_type(trust_level)
    policy_source = "trust_level_override" if override_level else get_policy_source(normalized)

    if trust_level == TrustLevel.SAFE:
        return TrustDecision(
            action_name=normalized,
            trust_level=trust_level,
            approval_type=approval_type,
            allowed=True,
            reason="Safe action. No approval required.",
            reason_code="SAFE_ACTION",
            policy_source=policy_source,
        )

    if trust_level == TrustLevel.PRIVATE:
        if confirmed:
            return TrustDecision(
                action_name=normalized,
                trust_level=trust_level,
                approval_type=approval_type,
                allowed=True,
                reason="Private action approved.",
                reason_code="PRIVATE_CONFIRMED",
                policy_source=policy_source,
            )
        return TrustDecision(
            action_name=normalized,
            trust_level=trust_level,
            approval_type=approval_type,
            allowed=False,
            reason="Private action requires confirmation.",
            reason_code="CONFIRM_REQUIRED",
            policy_source=policy_source,
        )

    if trust_level == TrustLevel.SENSITIVE:
        if session_approved:
            return TrustDecision(
                action_name=normalized,
                trust_level=trust_level,
                approval_type=approval_type,
                allowed=True,
                reason="Sensitive action approved.",
                reason_code="SESSION_APPROVED",
                policy_source=policy_source,
            )
        return TrustDecision(
            action_name=normalized,
            trust_level=trust_level,
            approval_type=approval_type,
            allowed=False,
            reason="Sensitive action requires session approval.",
            reason_code="SESSION_REQUIRED",
            policy_source=policy_source,
        )

    if pin_verified:
        return TrustDecision(
            action_name=normalized,
            trust_level=trust_level,
            approval_type=approval_type,
            allowed=True,
            reason="Critical action approved by PIN.",
            reason_code="PIN_OK",
            policy_source=policy_source,
        )

    return TrustDecision(
        action_name=normalized,
        trust_level=trust_level,
        approval_type=approval_type,
        allowed=False,
        reason="Critical action requires PIN.",
        reason_code="PIN_REQUIRED",
        policy_source=policy_source,
    )


def build_permission_response(
    action_name: Optional[str],
    *,
    confirmed: bool = False,
    session_approved: bool = False,
    pin_verified: bool = False,
    trust_level_override: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    decision = evaluate_action(
        action_name,
        confirmed=confirmed,
        session_approved=session_approved,
        pin_verified=pin_verified,
        trust_level_override=trust_level_override,
    )

    if decision.allowed:
        return {
            "success": True,
            "status": "approved",
            "mode": "real",
            "trace_id": trace_id,
            "permission": decision.to_dict(),
        }

    status_map = {
        ApprovalType.CONFIRM: "needs_confirmation",
        ApprovalType.SESSION_APPROVAL: "needs_session_approval",
        ApprovalType.PIN: "needs_pin",
        ApprovalType.NONE: "approved",
    }

    return {
        "success": False,
        "status": status_map[decision.approval_type],
        "mode": "real",
        "trace_id": trace_id,
        "permission": decision.to_dict(),
    }
