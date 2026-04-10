import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import re

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = PROJECT_ROOT / "interface" / "web"
APP_HTML = WEB_DIR / "aura.html"
LOGIN_HTML = WEB_DIR / "login.html"
SETUP_HTML = WEB_DIR / "setup.html"
ADMIN_HTML = WEB_DIR / "admin.html"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.registry import get_agent_summary, list_agents
from agents.agent_fabric import list_generated_agent_cards, run_generated_agent
from brain.capability_registry import list_capabilities, summarize_capabilities
from brain.understanding_engine import clean_user_input
from brain.intent_engine import detect_intent_with_confidence
from brain.decision_engine import build_decision_summary
from brain.core_ai import AGENT_ROUTER, process_command_detailed
from brain.response_engine import (
    FALLBACK_USER_MESSAGE,
    clean_response,
    generate_response,
)
from brain.provider_hub import summarize_provider_statuses
from config.master_spec import CAPABILITY_LABELS, HYBRID_IMPLEMENTATION_ORDER
from config.system_modes import list_system_modes
from config.settings import MODEL_NAME
from memory import vector_memory
from memory.chat_history import clear_history, get_all_sessions, get_history, save_message
from memory.memory_stats import get_memory_stats
from security.access_control import AccessController
from security.auth_manager import (
    authenticate_user,
    clear_session_cookie,
    create_owner_account,
    get_auth_state,
    get_request_user,
    get_user as get_auth_user,
    is_admin_user,
    logout_request,
    register_user as register_auth_user,
    requires_first_run_setup,
    set_session_cookie,
)
from security.confirmation_system import ConfirmationSystem
from security.lock_manager import is_locked, lock_resource, unlock_resource
from security.pin_manager import get_pin_status
from security.session_manager import approve_action, is_action_approved
from security.trust_engine import build_permission_response
from api.auth import get_user
from voice.voice_controller import (
    get_voice_status,
    speak_response,
    stop_voice_output,
    transcribe_microphone_request,
    update_voice_preferences,
)
from voice.voice_pipeline import process_voice_text
from voice.voice_manager import load_user_profile, save_user_profile


app = FastAPI()

app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


class Command(BaseModel):
    text: str
    username: str = "guest"


class ChatApiRequest(BaseModel):
    message: str
    mode: str = "hybrid"
    confirmation_code: Optional[str] = None


class LoginData(BaseModel):
    username: str
    password: str


class RegisterData(BaseModel):
    username: str
    password: str
    name: str
    email: str
    title: Optional[str] = "sir"
    preferred_name: Optional[str] = ""


class SetupData(BaseModel):
    username: str
    password: str
    name: str
    email: str
    master_pin: str
    title: Optional[str] = "sir"
    preferred_name: Optional[str] = ""


class TaskCreate(BaseModel):
    text: str
    priority: str = "medium"
    due_date: Optional[str] = None


class TaskUpdate(BaseModel):
    text: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    done: Optional[bool] = None


class ReminderCreate(BaseModel):
    text: str
    date: Optional[str] = None
    time: Optional[str] = None


class ReminderUpdate(BaseModel):
    text: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    status: Optional[str] = None


class AgentRunRequest(BaseModel):
    text: str
    username: str = "guest"
    session_id: str = "default"
    confirmed: bool = False
    pin: Optional[str] = None
    save_artifact: Optional[bool] = None


class VoiceTextRequest(BaseModel):
    text: str


class VoiceCaptureRequest(BaseModel):
    timeout: int = 5
    phrase_time_limit: Optional[int] = None


class VoiceSettingsUpdate(BaseModel):
    persona: Optional[str] = None
    voice_profile: Optional[str] = None
    language: Optional[str] = None
    voice_gender: Optional[str] = None
    rate: Optional[float] = None
    pitch: Optional[float] = None
    volume: Optional[float] = None
    enabled: Optional[bool] = None


class SecurityActionRequest(BaseModel):
    action_name: str
    session_id: str = "default"


class LockRequest(BaseModel):
    resource_id: str
    owner: Optional[str] = None


class InviteRequest(BaseModel):
    email: str


class RevokeAccessRequest(BaseModel):
    email: str


class UnblockIpRequest(BaseModel):
    ip_address: str


class ConfirmationCodeSetRequest(BaseModel):
    code: str
    confirm_code: str


class ConfirmationCodeChangeRequest(BaseModel):
    old_code: str
    new_code: str
    confirm_code: str


class UserProfileUpdateRequest(BaseModel):
    preferred_name: Optional[str] = None
    title: Optional[str] = None
    language: Optional[str] = None
    voice_profile: Optional[str] = None
    voice_gender: Optional[str] = None
    voice_rate: Optional[float] = None
    voice_pitch: Optional[float] = None
    voice_volume: Optional[float] = None
    auto_speak: Optional[bool] = None
    proactive_suggestions: Optional[bool] = None


TASKS_FILE = PROJECT_ROOT / "memory" / "tasks.json"
REMINDERS_FILE = PROJECT_ROOT / "memory" / "reminders.json"
USER_MEMORY_FILE = PROJECT_ROOT / "memory" / "user_memory.json"
LEARNING_FILE = PROJECT_ROOT / "memory" / "aura_learning.json"
IMPROVEMENT_FILE = PROJECT_ROOT / "memory" / "aura_improvement_log.json"
PERMISSIONS_FILE = PROJECT_ROOT / "memory" / "permissions.json"
VOICE_SETTINGS_FILE = PROJECT_ROOT / "memory" / "voice_settings.json"
access_controller = AccessController()
confirmation_system = ConfirmationSystem()


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _normalize_session_id(session_id: Optional[str]) -> str:
    value = str(session_id or "").strip()
    if not value:
        return "default"
    value = re.sub(r"[^A-Za-z0-9._:-]+", "-", value)
    return value[:120] or "default"


def _resolve_session_id(request: Optional[Request], explicit: Optional[str] = None) -> str:
    if explicit:
        return _normalize_session_id(explicit)
    if request is not None:
        return _normalize_session_id(request.headers.get("X-AURA-Session-Id"))
    return "default"


def _normalize_chat_mode(requested_mode: Optional[str], execution_mode: Optional[str], permission: Optional[dict[str, Any]] = None) -> str:
    normalized_requested = (requested_mode or "hybrid").strip().lower() or "hybrid"
    if permission and not permission.get("success", True):
        return "real"

    execution = (execution_mode or "").strip().lower()
    if execution in {"greeting", "memory", "special_intent", "single_agent", "generated_agent", "permission_blocked"}:
        return "real"

    if "agent" in execution and "fallback" not in execution:
        return "real"

    if normalized_requested == "real" and execution not in {"fallback_llm", "multi_command", "empty"}:
        return "real"

    return "hybrid"


def _derive_agent_used(core_result: Optional[dict[str, Any]], detected_intent: str, decision: dict[str, Any]) -> str:
    if core_result:
        capability_cards = core_result.get("agent_capabilities") or []
        if capability_cards and capability_cards[0].get("name"):
            return str(capability_cards[0]["name"])

        used_agents = core_result.get("used_agents") or []
        if used_agents:
            return str(used_agents[0])

    if decision.get("use_agent") and detected_intent:
        return detected_intent

    return decision.get("final_route") or detected_intent or "general"


def _permission_reply(permission: dict[str, Any]) -> str:
    permission_info = permission.get("permission", {})
    approval_type = permission_info.get("approval_type")
    reason = permission_info.get("reason") or "Approval is required before execution."

    if approval_type == "pin":
        pin_status = get_pin_status()
        if not pin_status.get("configured"):
            return "Critical action requires PIN. PIN verification is not configured yet."

    return str(reason)


def _confirmation_reply(context: dict[str, Any]) -> str:
    user = context.get("user") or {}
    user_id = str(user.get("id", "")).strip()
    if not user_id or not confirmation_system.code_exists(user_id):
        return "Please set a confirmation code in Settings first."
    return "AURA requires your confirmation to proceed."


def _build_chat_success_payload(*, reply: str, intent: str, agent_used: str, mode: str) -> dict[str, Any]:
    return {
        "reply": reply,
        "intent": intent,
        "agent_used": agent_used,
        "agent": agent_used,
        "mode": mode,
        "status": "ok",
    }


def _persist_chat_turn(context: dict[str, Any], reply: str, intent: str, agent_used: Optional[str], mode: Optional[str]) -> None:
    save_message(
        context["session_id"],
        "user",
        context["raw_message"],
        intent=intent,
        agent_used=None,
        mode=context["requested_mode"],
    )
    save_message(
        context["session_id"],
        "assistant",
        reply,
        intent=intent,
        agent_used=agent_used,
        mode=mode or context["requested_mode"],
    )


def _attempt_persist_chat_turn(context: dict[str, Any], reply: str, intent: str, agent_used: Optional[str], mode: Optional[str]) -> dict[str, Any]:
    try:
        _persist_chat_turn(context, reply, intent, agent_used, mode)
        return {"saved": True, "backend": "sqlite"}
    except Exception as error:
        return {"saved": False, "backend": "sqlite", "error": str(error)}


def _prepare_chat_context(
    raw_message: str,
    requested_mode: Optional[str],
    session_id: Optional[str] = None,
    *,
    user: Optional[dict[str, Any]] = None,
    confirmation_code: Optional[str] = None,
) -> dict[str, Any]:
    message = (raw_message or "").strip()
    mode = (requested_mode or "hybrid").strip().lower() or "hybrid"
    if not message:
        raise ValueError("message is required")

    cleaned_message = clean_user_input(message)
    if not cleaned_message:
        raise ValueError("message is required")

    detected_intent, confidence = detect_intent_with_confidence(cleaned_message)
    decision = build_decision_summary(detected_intent, confidence, AGENT_ROUTER)
    normalized_session_id = _normalize_session_id(session_id)
    permission = build_permission_response(
        detected_intent,
        confirmed=False,
        session_approved=is_action_approved(normalized_session_id, detected_intent),
        pin_verified=False,
    )
    confirmation_required = permission.get("permission", {}).get("approval_type") == "pin"
    confirmation_ok = False
    if confirmation_required and user:
        user_id = str(user.get("id", "")).strip()
        if user_id and confirmation_code:
            confirmation_ok = confirmation_system.verify_code(user_id, confirmation_code)
        if confirmation_ok:
            permission = {
                "success": True,
                "status": "approved",
                "mode": "real",
                "permission": {
                    "action_name": detected_intent,
                    "approval_type": "confirmation_code",
                    "reason": "Critical action approved by confirmation code.",
                },
            }
        else:
            permission = {
                "success": False,
                "status": "confirmation_required",
                "mode": "real",
                "permission": {
                    "action_name": detected_intent,
                    "approval_type": "confirmation_code",
                    "reason": "AURA requires your confirmation to proceed.",
                },
            }
    return {
        "raw_message": message,
        "requested_mode": mode,
        "session_id": normalized_session_id,
        "cleaned_message": cleaned_message,
        "detected_intent": detected_intent,
        "confidence": confidence,
        "decision": decision,
        "permission": permission,
        "user": user,
        "user_profile": load_user_profile(),
        "confirmation_required": confirmation_required,
        "confirmation_ok": confirmation_ok,
    }


def _build_blocked_chat_payload(context: dict[str, Any], permission: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    active_permission = permission or context["permission"]
    if context.get("confirmation_required") and not context.get("confirmation_ok"):
        blocked_reply = _confirmation_reply(context)
    else:
        blocked_reply = _permission_reply(active_permission)
    agent_used = _derive_agent_used(None, context["detected_intent"], context["decision"])
    payload = _build_chat_success_payload(
        reply=blocked_reply,
        intent=context["detected_intent"] or "permission",
        agent_used=agent_used,
        mode=_normalize_chat_mode(context["requested_mode"], "permission_blocked", active_permission),
    )
    payload["permission"] = active_permission
    payload["decision"] = context["decision"]
    payload["confidence"] = context["confidence"]
    payload["session_id"] = context["session_id"]
    payload["confirmation_required"] = bool(context.get("confirmation_required"))
    return payload


def _is_unusable_reply_text(text: Optional[str]) -> bool:
    normalized = clean_response(text).strip().lower()
    if not normalized:
        return True
    if normalized == FALLBACK_USER_MESSAGE.strip().lower():
        return True
    return "couldn't generate a useful response" in normalized


def _execute_chat_pipeline(context: dict[str, Any]) -> dict[str, Any]:
    result = process_command_detailed(
        context["cleaned_message"],
        session_id=context["session_id"],
        user_profile={**(context.get("user_profile") or {}), **(context.get("user") or {})},
        current_mode=context["requested_mode"],
    )
    execution_mode = result.get("execution_mode")
    if result.get("intent") == "error" or execution_mode == "error":
        raise RuntimeError(str(result.get("response") or "Brain execution failed."))

    runtime_permission = result.get("permission")
    if runtime_permission and not runtime_permission.get("success", True):
        payload = _build_blocked_chat_payload(context, runtime_permission)
        payload["decision"] = result.get("decision") or context["decision"]
        return payload

    reply_text = clean_response(result.get("response"))
    if _is_unusable_reply_text(reply_text):
        fallback_reply = clean_response(generate_response(context["cleaned_message"]))
        if _is_unusable_reply_text(fallback_reply):
            raise RuntimeError("Response pipeline returned no usable reply.")
        reply_text = fallback_reply

    if _is_unusable_reply_text(reply_text):
        raise RuntimeError(reply_text)

    agent_used = _derive_agent_used(result, context["detected_intent"], context["decision"])
    response_mode = _normalize_chat_mode(context["requested_mode"], execution_mode, runtime_permission)

    payload = _build_chat_success_payload(
        reply=reply_text,
        intent=str(result.get("detected_intent") or result.get("intent") or context["detected_intent"] or "general"),
        agent_used=agent_used,
        mode=response_mode,
    )
    payload["decision"] = result.get("decision") or context["decision"]
    payload["permission"] = runtime_permission or context["permission"]
    payload["execution_mode"] = execution_mode
    payload["used_agents"] = result.get("used_agents", [])
    payload["plan"] = result.get("plan", [])
    payload["orchestration"] = result.get("orchestration", {})
    payload["confidence"] = result.get("confidence", context["confidence"])
    payload["session_id"] = context["session_id"]
    return payload


def _now_string() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_json_list(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(items, file, indent=2, ensure_ascii=False)


def _next_id(items: list[dict[str, Any]]) -> int:
    return max((int(item.get("id", 0)) for item in items), default=0) + 1


def _task_summary(tasks: list[dict[str, Any]]) -> dict[str, int]:
    pending = sum(1 for task in tasks if task.get("status") != "completed")
    completed = sum(1 for task in tasks if task.get("status") == "completed")
    return {
        "total": len(tasks),
        "pending": pending,
        "completed": completed,
    }


def _reminder_summary(reminders: list[dict[str, Any]]) -> dict[str, int]:
    active = sum(1 for reminder in reminders if reminder.get("status", "active") == "active")
    completed = sum(1 for reminder in reminders if reminder.get("status") == "completed")
    return {
        "total": len(reminders),
        "active": active,
        "completed": completed,
    }


def _build_personalized_greeting(user_name: str | None) -> str:
    if user_name:
        return f"Welcome back, {user_name}. AURA is ready."
    return "Hello. AURA is ready."


def _normalize_name(*values: Any) -> Optional[str]:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text.title()
    return None


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_secure_request(request: Request) -> bool:
    return str(request.url.scheme).lower() == "https"


def _read_html(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _current_user(request: Request) -> Optional[dict[str, Any]]:
    return get_request_user(request)


def _require_authenticated_user(request: Request) -> dict[str, Any]:
    user = _current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def _require_admin_user(request: Request) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


PUBLIC_PATHS = {
    "/login",
    "/setup",
    "/api/login",
    "/api/register",
    "/api/setup",
    "/api/auth/session",
}


@app.middleware("http")
async def aura_private_access_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/static") or path in PUBLIC_PATHS:
        return await call_next(request)

    setup_required = requires_first_run_setup()
    user = _current_user(request)

    if setup_required:
        if path.startswith("/api/"):
            return JSONResponse(status_code=503, content={"error": "AURA setup is required.", "status": "setup_required"})
        if path != "/setup":
            return RedirectResponse("/setup", status_code=302)
        return await call_next(request)

    if user:
        return await call_next(request)

    if path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"error": "Authentication required.", "status": "error"})

    if path != "/login":
        return RedirectResponse("/login", status_code=302)
    return await call_next(request)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if requires_first_run_setup():
        return RedirectResponse("/setup", status_code=302)
    if not _current_user(request):
        return RedirectResponse("/login", status_code=302)
    return HTMLResponse(_read_html(APP_HTML))


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if requires_first_run_setup():
        return RedirectResponse("/setup", status_code=302)
    if _current_user(request):
        return RedirectResponse("/", status_code=302)
    return HTMLResponse(_read_html(LOGIN_HTML))


@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    if not requires_first_run_setup() and _current_user(request):
        return RedirectResponse("/", status_code=302)
    if not requires_first_run_setup() and not _current_user(request):
        return RedirectResponse("/login", status_code=302)
    return HTMLResponse(_read_html(SETUP_HTML))


@app.get("/register", response_class=HTMLResponse)
async def register_page():
    return RedirectResponse("/login", status_code=302)


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    _require_admin_user(request)
    return HTMLResponse(_read_html(ADMIN_HTML))


@app.post("/api/login")
async def login(data: LoginData, request: Request):
    success, result, session_token = authenticate_user(
        data.username,
        data.password,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent", ""),
    )
    if not success or not session_token:
        raise HTTPException(status_code=401, detail=result)

    response = JSONResponse(
        {
            "success": True,
            "user": result,
            "message": f"Welcome back, {result.get('preferred_name') or result.get('name') or result.get('username')}. How may I assist you?",
        }
    )
    set_session_cookie(response, session_token, secure=_is_secure_request(request))
    return response


@app.post("/api/register")
async def register(data: RegisterData):
    success, result = register_auth_user(
        data.username,
        data.password,
        data.name,
        data.email,
        title=data.title or "sir",
        preferred_name=data.preferred_name or "",
    )
    if success:
        return {"success": True, "user": result, "message": "Registration complete. You may now sign in."}
    raise HTTPException(status_code=400, detail=result)


@app.post("/api/setup")
async def setup_owner(data: SetupData):
    success, result = create_owner_account(
        username=data.username,
        password=data.password,
        name=data.name,
        email=data.email,
        master_pin=data.master_pin,
        title=data.title or "sir",
        preferred_name=data.preferred_name or "",
    )
    if success:
        return {"success": True, "user": result, "message": "AURA online. Owner account created."}
    raise HTTPException(status_code=400, detail=result)


@app.post("/api/logout")
async def logout_endpoint(request: Request):
    logout_request(request)
    response = JSONResponse({"success": True, "message": "Session secured."})
    clear_session_cookie(response, secure=_is_secure_request(request))
    return response


@app.get("/api/auth/session")
async def auth_session_status(request: Request):
    user = _current_user(request)
    return {
        "authenticated": bool(user),
        "setup_required": requires_first_run_setup(),
        "user": user,
        "status": "ok",
    }


@app.post("/chat")
async def chat(command: Command):
    try:
        result = process_command_detailed(command.text)
        response = result["response"]

        legacy_context = {
            "session_id": _normalize_session_id(command.username or "default"),
            "raw_message": command.text,
            "requested_mode": "hybrid",
        }
        history_status = _attempt_persist_chat_turn(
            legacy_context,
            response,
            result.get("detected_intent") or result.get("intent") or "general",
            (result.get("used_agents") or [None])[0],
            result.get("execution_mode") or "hybrid",
        )

        return {
            "intent": result["intent"],
            "detected_intent": result["detected_intent"],
            "confidence": round(result["confidence"], 2),
            "response": response,
            "username": command.username,
            "plan": result.get("plan", []),
            "used_agents": result.get("used_agents", []),
            "agent_capabilities": result.get("agent_capabilities", []),
            "execution_mode": result.get("execution_mode"),
            "decision": result.get("decision", {}),
            "orchestration": result.get("orchestration", {}),
            "permission_action": result.get("permission_action"),
            "permission": result.get("permission", {}),
            "history_status": history_status,
        }

    except Exception as e:
        return {
            "intent": "error",
            "detected_intent": "error",
            "confidence": 0.0,
            "response": f"Sorry, I encountered an error: {str(e)}",
            "username": command.username,
            "plan": [],
            "used_agents": [],
            "agent_capabilities": [],
            "execution_mode": "error",
            "decision": {},
            "orchestration": {},
            "permission_action": None,
            "permission": {},
        }


@app.post("/api/chat")
async def api_chat(payload: ChatApiRequest, request: Request):
    try:
        if not str(payload.message or "").strip():
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": "No message provided",
                },
                headers=_cors_headers(),
            )
        user = _require_authenticated_user(request)
        session_id = _resolve_session_id(request)
        context = _prepare_chat_context(
            payload.message,
            payload.mode,
            session_id,
            user=user,
            confirmation_code=payload.confirmation_code,
        )
        if not context["permission"].get("success", False):
            blocked_payload = _build_blocked_chat_payload(context)
            blocked_payload["history_status"] = _attempt_persist_chat_turn(
                context,
                blocked_payload["reply"],
                blocked_payload["intent"],
                blocked_payload.get("agent_used"),
                blocked_payload.get("mode"),
            )
            return JSONResponse(content=blocked_payload, headers=_cors_headers())

        response_payload = _execute_chat_pipeline(context)
        response_payload["history_status"] = _attempt_persist_chat_turn(
            context,
            response_payload["reply"],
            response_payload["intent"],
            response_payload.get("agent_used"),
            response_payload.get("mode"),
        )

        return JSONResponse(
            content=response_payload,
            headers=_cors_headers(),
        )
    except ValueError as error:
        return JSONResponse(
            status_code=400,
            content={
                "error": str(error),
                "status": "error",
            },
            headers=_cors_headers(),
        )
    except Exception as error:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(error),
                "status": "error",
            },
            headers=_cors_headers(),
        )


@app.get("/history")
async def history(session_id: str = "default"):
    return get_history(session_id)


@app.get("/api/history")
async def api_history(session_id: str = "default", limit: int = 50):
    try:
        normalized_session = _normalize_session_id(session_id)
        messages = get_history(normalized_session, limit=limit)
        return {
            "session_id": normalized_session,
            "messages": messages,
            "count": len(messages),
            "status": "ok",
        }
    except Exception as error:
        return JSONResponse(
            status_code=500,
            content={"error": str(error), "status": "error"},
            headers=_cors_headers(),
        )


@app.delete("/api/history")
async def api_history_delete(session_id: str = "default"):
    try:
        normalized_session = _normalize_session_id(session_id)
        deleted = clear_history(normalized_session)
        return {
            "session_id": normalized_session,
            "deleted": deleted,
            "status": "ok",
        }
    except Exception as error:
        return JSONResponse(
            status_code=500,
            content={"error": str(error), "status": "error"},
            headers=_cors_headers(),
        )


@app.get("/api/sessions")
async def api_sessions():
    try:
        return {
            "sessions": get_all_sessions(),
            "status": "ok",
        }
    except Exception as error:
        return JSONResponse(
            status_code=500,
            content={"error": str(error), "status": "error"},
            headers=_cors_headers(),
        )


@app.get("/api/admin/users")
async def admin_list_users(request: Request):
    _require_admin_user(request)
    whitelist_users = access_controller.list_users()
    registered_users = load_user_profile()
    return {
        "status": "ok",
        "users": whitelist_users,
        "profile_defaults": registered_users,
    }


@app.post("/api/admin/invite")
async def admin_invite_user(payload: InviteRequest, request: Request):
    admin_user = _require_admin_user(request)
    invited = access_controller.invite_user(payload.email, invited_by_admin=admin_user.get("username", "admin"))
    return {"status": "ok", "user": invited, "message": "User invited."}


@app.post("/api/admin/revoke")
async def admin_revoke_user(payload: RevokeAccessRequest, request: Request):
    _require_admin_user(request)
    revoked = access_controller.revoke_access(payload.email)
    if not revoked:
        raise HTTPException(status_code=404, detail="User not found in whitelist.")
    return {"status": "ok", "message": "Access revoked."}


@app.get("/api/admin/rate-limits")
async def admin_list_rate_limits(request: Request):
    _require_admin_user(request)
    return {"status": "ok", "items": access_controller.list_rate_limits()}


@app.post("/api/admin/unblock")
async def admin_unblock_ip(payload: UnblockIpRequest, request: Request):
    _require_admin_user(request)
    unblocked = access_controller.unblock_ip(payload.ip_address)
    if not unblocked:
        raise HTTPException(status_code=404, detail="IP address not found.")
    return {"status": "ok", "message": "IP unblocked."}


@app.get("/api/settings/profile")
async def get_user_profile_settings(request: Request):
    user = _require_authenticated_user(request)
    profile = load_user_profile()
    profile["username"] = user.get("username", "")
    return {"status": "ok", "profile": profile, "user": user}


@app.patch("/api/settings/profile")
async def update_user_profile_settings(payload: UserProfileUpdateRequest, request: Request):
    _require_authenticated_user(request)
    profile = load_user_profile()
    updates = payload.model_dump(exclude_none=True)
    profile.update(updates)
    save_user_profile(profile)
    update_voice_preferences(
        persona=profile.get("voice_profile"),
        voice_gender=profile.get("voice_gender"),
        rate=profile.get("voice_rate"),
        volume=profile.get("voice_volume"),
        language=profile.get("language"),
    )
    return {"status": "ok", "profile": load_user_profile()}


@app.get("/api/confirmation-code/status")
async def confirmation_code_status(request: Request):
    user = _require_authenticated_user(request)
    return {
        "status": "ok",
        "configured": confirmation_system.code_exists(user.get("id", "")),
        "critical_actions": [
            "Deleting files or data",
            "Sending emails or messages",
            "Making purchases",
            "Changing security settings",
            "Accessing locked chats",
            "Any critical action requested through agents",
        ],
    }


@app.post("/api/confirmation-code/set")
async def set_confirmation_code_endpoint(payload: ConfirmationCodeSetRequest, request: Request):
    user = _require_authenticated_user(request)
    if payload.code != payload.confirm_code:
        raise HTTPException(status_code=400, detail="Confirmation codes do not match.")
    if not confirmation_system.set_confirmation_code(user.get("id", ""), payload.code):
        raise HTTPException(status_code=400, detail="Confirmation code must be at least 4 characters.")
    return {"status": "ok", "message": "Confirmation code saved."}


@app.post("/api/confirmation-code/change")
async def change_confirmation_code_endpoint(payload: ConfirmationCodeChangeRequest, request: Request):
    user = _require_authenticated_user(request)
    if payload.new_code != payload.confirm_code:
        raise HTTPException(status_code=400, detail="New confirmation codes do not match.")
    if not confirmation_system.change_code(user.get("id", ""), payload.old_code, payload.new_code):
        raise HTTPException(status_code=400, detail="Confirmation code could not be changed.")
    return {"status": "ok", "message": "Confirmation code updated."}


@app.get("/api/user/{username}")
async def get_user_info(username: str):
    user = get_user(username)
    if user:
        return {"success": True, "user": user}
    raise HTTPException(status_code=404, detail="User not found")


@app.get("/api/memory/insights")
async def get_memory_insights(username: str = "guest"):
    user = get_user(username) or {}
    explicit_memory = _read_json_object(USER_MEMORY_FILE)
    learning = _read_json_object(LEARNING_FILE)

    user_profile = learning.get("user_profile", {})
    preferences = user_profile.get("preferences") or learning.get("user_preferences") or {}
    interests = user_profile.get("interests") or []
    learned_facts = learning.get("learned_facts") or []
    topic_frequency = learning.get("topic_frequency") or learning.get("frequent_topics") or {}
    top_intents = sorted(topic_frequency.items(), key=lambda item: item[1], reverse=True)[:6]

    remembered_name = _normalize_name(
        user.get("name"),
        explicit_memory.get("user_name"),
        user_profile.get("name"),
    )
    profile_name = remembered_name or "Guest"

    return {
        "mode": "hybrid",
        "remembered_name": profile_name,
        "greeting_preview": _build_personalized_greeting(remembered_name),
        "profile": {
            "name": profile_name,
            "plan": user.get("plan", "free"),
            "created": user.get("created"),
            "city": explicit_memory.get("user_city"),
            "age": explicit_memory.get("user_age"),
        },
        "preferences": preferences,
        "interests": interests,
        "learned_facts": learned_facts,
        "top_intents": [
            {"intent": intent, "count": count}
            for intent, count in top_intents
        ],
        "insights": [
            f"Top intent right now is {top_intents[0][0]}." if top_intents else "AURA is still learning your recurring intent patterns.",
            "Stored facts come from explicit memory and interaction learning.",
            "Preferences are limited until more real UI controls are connected.",
        ],
        "sources": {
            "explicit_memory": str(USER_MEMORY_FILE.relative_to(PROJECT_ROOT)),
            "learning": str(LEARNING_FILE.relative_to(PROJECT_ROOT)),
        },
    }


@app.get("/api/intelligence/insights")
async def get_intelligence_insights():
    improvement = _read_json_object(IMPROVEMENT_FILE)
    permissions = _read_json_object(PERMISSIONS_FILE)
    voice = _read_json_object(VOICE_SETTINGS_FILE)

    failures = improvement.get("failures") or []
    low_confidence = improvement.get("low_confidence_commands") or []
    suggestions = improvement.get("improvement_suggestions") or []

    return {
        "mode": "hybrid",
        "reasoning_status": "available",
        "low_confidence_count": len(low_confidence),
        "failure_count": len(failures),
        "recent_low_confidence": low_confidence[-6:],
        "recent_failures": failures[-6:],
        "improvement_suggestions": suggestions[-6:],
        "permissions": permissions,
        "voice": voice,
        "sources": {
            "improvement_log": str(IMPROVEMENT_FILE.relative_to(PROJECT_ROOT)),
            "permissions": str(PERMISSIONS_FILE.relative_to(PROJECT_ROOT)),
            "voice": str(VOICE_SETTINGS_FILE.relative_to(PROJECT_ROOT)),
        },
    }


@app.get("/api/tasks")
async def get_tasks():
    tasks = _read_json_list(TASKS_FILE)
    tasks.sort(key=lambda item: (item.get("status") == "completed", -int(item.get("id", 0))))
    return {
        "items": tasks,
        "summary": _task_summary(tasks),
        "mode": "real",
        "source": str(TASKS_FILE.relative_to(PROJECT_ROOT)),
    }


@app.post("/api/tasks")
async def create_task(task: TaskCreate):
    text = task.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Task text is required")

    tasks = _read_json_list(TASKS_FILE)
    item = {
        "id": _next_id(tasks),
        "task": text,
        "priority": (task.priority or "medium").strip().lower() or "medium",
        "due_date": task.due_date.strip() if task.due_date else None,
        "status": "pending",
        "created": _now_string(),
    }
    tasks.append(item)
    _write_json_list(TASKS_FILE, tasks)
    return {
        "success": True,
        "item": item,
        "summary": _task_summary(tasks),
    }


@app.patch("/api/tasks/{task_id}")
async def update_task(task_id: int, task: TaskUpdate):
    tasks = _read_json_list(TASKS_FILE)
    item = next((entry for entry in tasks if int(entry.get("id", 0)) == task_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.text is not None:
        text = task.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Task text is required")
        item["task"] = text

    if task.priority is not None:
        item["priority"] = task.priority.strip().lower() or "medium"

    if task.due_date is not None:
        item["due_date"] = task.due_date.strip() or None

    if task.done is not None:
        if task.done:
            item["status"] = "completed"
            item["completed_at"] = _now_string()
        else:
            item["status"] = "pending"
            item.pop("completed_at", None)

    _write_json_list(TASKS_FILE, tasks)
    return {
        "success": True,
        "item": item,
        "summary": _task_summary(tasks),
    }


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    tasks = _read_json_list(TASKS_FILE)
    updated = [entry for entry in tasks if int(entry.get("id", 0)) != task_id]
    if len(updated) == len(tasks):
        raise HTTPException(status_code=404, detail="Task not found")
    _write_json_list(TASKS_FILE, updated)
    return {
        "success": True,
        "summary": _task_summary(updated),
    }


@app.get("/api/reminders")
async def get_reminders():
    reminders = _read_json_list(REMINDERS_FILE)
    reminders.sort(key=lambda item: (item.get("status") == "completed", -int(item.get("id", 0))))
    return {
        "items": reminders,
        "summary": _reminder_summary(reminders),
        "mode": "real",
        "source": str(REMINDERS_FILE.relative_to(PROJECT_ROOT)),
    }


@app.post("/api/reminders")
async def create_reminder(reminder: ReminderCreate):
    text = reminder.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Reminder text is required")

    reminders = _read_json_list(REMINDERS_FILE)
    item = {
        "id": _next_id(reminders),
        "text": text,
        "time": reminder.time.strip() if reminder.time else None,
        "date": reminder.date.strip() if reminder.date else None,
        "created": _now_string(),
        "status": "active",
        "completed_at": None,
    }
    reminders.append(item)
    _write_json_list(REMINDERS_FILE, reminders)
    return {
        "success": True,
        "item": item,
        "summary": _reminder_summary(reminders),
    }


@app.patch("/api/reminders/{reminder_id}")
async def update_reminder(reminder_id: int, reminder: ReminderUpdate):
    reminders = _read_json_list(REMINDERS_FILE)
    item = next((entry for entry in reminders if int(entry.get("id", 0)) == reminder_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Reminder not found")

    if reminder.text is not None:
        text = reminder.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="Reminder text is required")
        item["text"] = text

    if reminder.date is not None:
        item["date"] = reminder.date.strip() or None

    if reminder.time is not None:
        item["time"] = reminder.time.strip() or None

    if reminder.status is not None:
        status = reminder.status.strip().lower()
        if status not in {"active", "completed"}:
            raise HTTPException(status_code=400, detail="Reminder status must be active or completed")
        item["status"] = status
        item["completed_at"] = _now_string() if status == "completed" else None

    _write_json_list(REMINDERS_FILE, reminders)
    return {
        "success": True,
        "item": item,
        "summary": _reminder_summary(reminders),
    }


@app.delete("/api/reminders/{reminder_id}")
async def delete_reminder(reminder_id: int):
    reminders = _read_json_list(REMINDERS_FILE)
    updated = [entry for entry in reminders if int(entry.get("id", 0)) != reminder_id]
    if len(updated) == len(reminders):
        raise HTTPException(status_code=404, detail="Reminder not found")
    _write_json_list(REMINDERS_FILE, updated)
    return {
        "success": True,
        "summary": _reminder_summary(updated),
    }


@app.get("/api/system/status")
async def system_status(request: Request):
    user = _require_authenticated_user(request)
    summary = get_agent_summary()
    memory_status = vector_memory.get_status()
    memory_connected = memory_status["vector_store_ready"]
    memory_health = "connected" if memory_connected else "degraded"
    memory_mode = "real" if memory_connected else "fallback"
    provider_summary = summarize_provider_statuses()
    profile = load_user_profile()
    return {
        "status": "online",
        "version": "1.0.0",
        "model": MODEL_NAME,
        "orchestrator": "rule_based_available",
        "reasoning": "hybrid_available",
        "memory": memory_health,
        "planner": "hybrid_available",
        "agents": summary,
        "capability_summary": summary.get("capability_modes", {}),
        "brain_capabilities": summarize_capabilities(),
        "memory_stats": get_memory_stats(),
        "memory_backend": memory_status,
        "providers": provider_summary,
        "security": {
            "pin": get_pin_status(),
            "auth": {"authenticated": True, "user": user},
            "confirmation_code": confirmation_system.code_exists(user.get("id", "")),
            "whitelist_count": len(access_controller.list_users()),
        },
        "profile": profile,
        "subsystems": {
            "orchestrator": {"status": "available", "mode": "real", "source": "rule_based"},
            "reasoning": {"status": "available", "mode": "hybrid"},
            "planner": {"status": "available", "mode": "hybrid"},
            "voice": {"status": "available" if get_voice_status()["settings"]["enabled"] else "standby", "mode": "hybrid"},
            "providers": {
                "status": "available" if provider_summary["available"] else "degraded",
                "mode": "hybrid",
                "available": provider_summary["available"],
            },
            "memory": {
                "status": memory_health,
                "mode": memory_mode,
                "vector_store_ready": memory_connected,
                "backend": memory_status["backend"],
                "last_error": memory_status["last_error"],
            },
        },
        "implementation_doctrine": {
            "capability_labels": list(CAPABILITY_LABELS),
            "hybrid_order": list(HYBRID_IMPLEMENTATION_ORDER),
            "implementation_priority": list(CAPABILITY_LABELS),
        },
    }


@app.get("/api/agents")
async def get_agents():
    return {
        "agents": list_agents(),
        "generated_agents": list_generated_agent_cards(),
        "providers": summarize_provider_statuses(),
        "summary": get_agent_summary(),
        "doctrine": {
            "capability_labels": list(CAPABILITY_LABELS),
            "hybrid_order": list(HYBRID_IMPLEMENTATION_ORDER),
            "implementation_priority": list(CAPABILITY_LABELS),
        },
    }


@app.get("/api/capabilities")
async def get_capabilities():
    return {
        "items": list_capabilities(),
        "summary": summarize_capabilities(),
    }


@app.get("/api/providers")
async def get_provider_status():
    return summarize_provider_statuses()


@app.get("/api/memory/stats")
async def get_memory_status():
    return get_memory_stats()


@app.get("/api/security/status")
async def get_security_status(request: Request, session_id: str = "default", resource_id: Optional[str] = None):
    user = _require_authenticated_user(request)
    return {
        "pin": get_pin_status(),
        "auth": {"authenticated": True, "user": user},
        "session_id": session_id,
        "resource_locked": is_locked(resource_id) if resource_id else False,
        "confirmation_code": confirmation_system.code_exists(user.get("id", "")),
        "rate_limits": access_controller.list_rate_limits() if is_admin_user(user) else [],
    }


@app.get("/api/admin/system-status")
async def admin_system_status(request: Request):
    _require_admin_user(request)
    return await system_status(request)


@app.get("/api/system/modes")
async def get_modes():
    return {
        "items": list_system_modes(),
    }

    if False:  # Legacy static catalog kept only as migration reference.
        return {
        "agents": [
            {"id": "general", "name": "General AURA", "icon": "🤖", "description": "General AI assistant"},
            {"id": "study", "name": "Study Agent", "icon": "📚", "description": "Learn any topic"},
            {"id": "research", "name": "Research Agent", "icon": "🔍", "description": "Deep research"},
            {"id": "code", "name": "Coding Agent", "icon": "💻", "description": "Programming help"},
            {"id": "weather", "name": "Weather Agent", "icon": "🌤️", "description": "Weather info"},
            {"id": "news", "name": "News Agent", "icon": "📰", "description": "Latest news"},
            {"id": "math", "name": "Math Agent", "icon": "🧮", "description": "Math solver"},
            {"id": "translation", "name": "Translation Agent", "icon": "🌍", "description": "Translate languages"},
            {"id": "email", "name": "Email Writer", "icon": "📧", "description": "Write emails"},
            {"id": "content", "name": "Content Writer", "icon": "✍️", "description": "Write content"},
            {"id": "summarize", "name": "Summarizer", "icon": "📝", "description": "Summarize text"},
            {"id": "grammar", "name": "Grammar Check", "icon": "✅", "description": "Fix grammar"},
            {"id": "quiz", "name": "Quiz Agent", "icon": "🎯", "description": "Generate quizzes"},
            {"id": "joke", "name": "Joke Agent", "icon": "😄", "description": "Tell jokes"},
            {"id": "quote", "name": "Quote Agent", "icon": "💭", "description": "Inspiring quotes"},
            {"id": "password", "name": "Password Agent", "icon": "🔐", "description": "Generate passwords"},
            {"id": "task", "name": "Task Manager", "icon": "📋", "description": "Manage tasks"},
            {"id": "reminder", "name": "Reminder Agent", "icon": "⏰", "description": "Set reminders"},
            {"id": "resume", "name": "Resume Builder", "icon": "📄", "description": "Build resume"},
            {"id": "currency", "name": "Currency Agent", "icon": "💱", "description": "Convert currency"},
            {"id": "dictionary", "name": "Dictionary", "icon": "📖", "description": "Define words"},
            {"id": "youtube", "name": "YouTube Agent", "icon": "▶️", "description": "YouTube search"},
            {"id": "web_search", "name": "Web Search", "icon": "🌐", "description": "Search web"},
            {"id": "file", "name": "File Agent", "icon": "📁", "description": "Read files"},
            {"id": "screenshot", "name": "Screenshot", "icon": "📸", "description": "Take screenshots"},
            {"id": "fitness", "name": "Fitness Agent", "icon": "💪", "description": "Workout and fitness plans"}
        ]
    }


@app.post("/api/agents/run/{agent_id}")
async def run_agent_endpoint(agent_id: str, request: AgentRunRequest):
    generated_ids = {item["id"] for item in list_generated_agent_cards()}
    if agent_id in generated_ids:
        result = run_generated_agent(
            agent_id,
            request.text,
            username=request.username,
            session_id=request.session_id,
            confirmed=request.confirmed,
            pin=request.pin,
            save_artifact=request.save_artifact,
        )
        return {
            "success": bool(result.get("success")),
            "dispatch_mode": "generated_agent",
            "agent_id": agent_id,
            "result": result,
        }

    runtime_result = process_command_detailed(request.text)
    matched_target = (
        agent_id == runtime_result.get("intent")
        or agent_id == runtime_result.get("detected_intent")
        or agent_id in runtime_result.get("used_agents", [])
    )
    return {
        "success": True,
        "dispatch_mode": "runtime_route",
        "agent_id": agent_id,
        "matched_target": matched_target,
        "result": runtime_result,
    }


@app.get("/api/voice/status")
async def get_voice_runtime_status():
    return get_voice_status()


@app.patch("/api/voice/settings")
async def update_voice_settings_endpoint(settings: VoiceSettingsUpdate):
    return update_voice_preferences(**settings.model_dump(exclude_none=True))


@app.post("/api/voice/text")
async def process_voice_text_endpoint(request: VoiceTextRequest):
    return process_voice_text(request.text)


@app.post("/api/voice/speak")
async def speak_voice_text_endpoint(request: VoiceTextRequest):
    return speak_response(request.text)


@app.post("/api/voice/stop")
async def stop_voice_text_endpoint():
    return stop_voice_output()


@app.post("/api/voice/microphone")
async def transcribe_voice_microphone_endpoint(request: VoiceCaptureRequest):
    return transcribe_microphone_request(timeout=request.timeout, phrase_time_limit=request.phrase_time_limit)


@app.post("/api/security/session-approve")
async def approve_security_action(request: SecurityActionRequest):
    return approve_action(request.session_id, request.action_name)


@app.post("/api/security/lock")
async def lock_resource_endpoint(request: LockRequest):
    return lock_resource(request.resource_id, owner=request.owner)


@app.post("/api/security/unlock")
async def unlock_resource_endpoint(request: LockRequest):
    return unlock_resource(request.resource_id)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
