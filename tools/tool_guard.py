from __future__ import annotations

from typing import Any, Dict, Optional

from security.enforcement import enforce_action, record_execution_result
from tools.tool_registry import get_tool


def guard_and_execute(
    tool_name: str,
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
    **kwargs: Any,
) -> Dict[str, object]:
    record = get_tool(tool_name)
    if record is None:
        return {
            "success": False,
            "status": "missing_tool",
            "reason": f"Unknown tool: {tool_name}",
        }

    access = enforce_action(
        record.action_name,
        username=username,
        user_id=user_id,
        session_id=session_id,
        session_token=session_token,
        confirmed=confirmed,
        pin=pin,
        otp=otp,
        otp_token=otp_token,
        resource_id=resource_id,
        require_auth=record.trust_level != "safe",
        meta={"tool_name": tool_name},
    )
    if not access["allowed"]:
        return {
            "success": False,
            "status": access["status"],
            "reason": access["reason"],
            "access": access,
        }

    missing_inputs = [name for name in record.required_inputs if name not in kwargs]
    if missing_inputs:
        return {
            "success": False,
            "status": "missing_inputs",
            "reason": f"Missing required inputs: {', '.join(missing_inputs)}",
            "access": access,
        }

    try:
        result = record.handler(**kwargs)
    except Exception as error:
        record_execution_result(
            record.action_name,
            session_id=session_id,
            username=username,
            success=False,
            reason=str(error),
            trust_level=record.trust_level,
            meta={"tool_name": tool_name},
        )
        return {"success": False, "status": "execution_error", "reason": str(error), "access": access}

    record_execution_result(
        record.action_name,
        session_id=session_id,
        username=username,
        success=True,
        trust_level=record.trust_level,
        meta={"tool_name": tool_name},
    )
    return {"success": True, "status": "executed", "result": result, "access": access}
