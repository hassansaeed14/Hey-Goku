from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

import brain.response_engine as response_engine_module
from agents.agent_bus import agent_bus
from agents.agent_registry import AgentRegistry
from agents.context import AURAContext
from brain import runtime_core as runtime_core_module
from brain.provider_hub import Groq
from brain.response_engine import clean_response, generate_response
from config.settings import MODEL_NAME
from memory.knowledge_base import get_user_age, get_user_city, get_user_name
from memory.working_memory import load_working_memory

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

if GROQ_API_KEY:
    print(f"[BRAIN] Groq key loaded: {GROQ_API_KEY[:10]}...")
else:
    print("[CRITICAL] GROQ_API_KEY not found in .env")


AGENT_ROUTER = runtime_core_module.AGENT_ROUTER
SESSION_CONTEXT_HISTORY: dict[str, list[dict[str, str]]] = {}
MAX_SESSION_EXCHANGES = 10

JARVIS_SYSTEM_PROMPT = (
    "You are AURA - Autonomous Universal Responsive Assistant. "
    "You are a real AI assistant modeled after JARVIS from Iron Man.\n\n"
    "Your personality:\n"
    "- Professional, calm, and highly intelligent\n"
    "- Respectful but not robotic; you have subtle personality\n"
    "- You call the user sir or ma'am based on profile, or by preferred name if set\n"
    "- You are confident but never arrogant\n"
    "- You are honest about your limitations\n"
    "- You never say 'As an AI language model...'\n"
    "- You complete tasks when the connected system supports them\n"
    "- You never claim a system action succeeded unless it actually ran\n\n"
    "Your speech style:\n"
    "- Formal but warm\n"
    "- Structured and clear\n"
    "- Efficient and polished\n"
    "- Begin with action, not disclaimers\n\n"
    "You are always AURA. You are always online."
)

UNUSABLE_RESPONSE_MARKERS = (
    "i couldn't generate a useful response right now.",
    "i ran into a problem while generating a response. please try again.",
)


def _normalize_session_id(session_id: Optional[str]) -> str:
    value = str(session_id or "default").strip()
    return value or "default"


def _get_session_history(session_id: str) -> list[dict[str, str]]:
    return SESSION_CONTEXT_HISTORY.setdefault(session_id, [])


def _sync_context_into_response_engine(session_id: str) -> None:
    response_engine_module.clear_history()
    for item in _get_session_history(session_id)[-MAX_SESSION_EXCHANGES * 2 :]:
        response_engine_module.add_to_history(item.get("role", "user"), item.get("content", ""))


def _record_exchange(session_id: str, user_message: str, assistant_message: str) -> None:
    history = _get_session_history(session_id)
    if user_message.strip():
        history.append({"role": "user", "content": user_message.strip()})
    if assistant_message.strip():
        history.append({"role": "assistant", "content": assistant_message.strip()})
    max_messages = MAX_SESSION_EXCHANGES * 2
    if len(history) > max_messages:
        del history[:-max_messages]


def _build_user_reference(user_profile: Optional[dict[str, Any]]) -> str:
    profile = dict(user_profile or {})
    preferred_name = str(profile.get("preferred_name") or "").strip()
    if preferred_name:
        return preferred_name
    title = str(profile.get("title") or "sir").strip()
    return title or "sir"


def _knowledge_base_reply(command: str, user_profile: Optional[dict[str, Any]] = None) -> Optional[str]:
    text = str(command or "").strip().lower()
    user_reference = _build_user_reference(user_profile)
    if "what is my name" in text:
        value = get_user_name()
        return f"Certainly {user_reference}. Your name is {value}." if value else None
    if "what is my age" in text or "how old am i" in text:
        value = get_user_age()
        return f"Certainly {user_reference}. Your age is {value}." if value else None
    if "what is my city" in text or "where do i live" in text:
        value = get_user_city()
        return f"Certainly {user_reference}. You previously said you are in {value}." if value else None
    return None


def _infer_proactive_suggestion(intent: str, command: str) -> Optional[str]:
    normalized_intent = str(intent or "general").strip().lower()
    text = str(command or "").strip().lower()
    if normalized_intent == "research":
        return "turn the research into a brief summary or task list"
    if normalized_intent == "study":
        return "generate revision questions or flashcards"
    if normalized_intent in {"task", "reminder"}:
        return "schedule a reminder or break the plan into smaller steps"
    if normalized_intent == "code" or "code" in text:
        return "review the implementation risks or test plan"
    if normalized_intent == "file":
        return "summarize the file findings or extract action items"
    return None


def _jarvis_prefix(intent: str, execution_mode: str) -> str:
    normalized_intent = str(intent or "general").strip().lower()
    normalized_mode = str(execution_mode or "").strip().lower()
    if normalized_mode == "permission_blocked":
        return ""
    if normalized_mode in {"multi_agent", "generated_agent", "single_agent", "special_intent"}:
        return "Right away. "
    if normalized_intent in {"research", "reasoning", "compare", "study"}:
        return "Analysis complete. "
    if normalized_intent in {"task", "reminder"}:
        return "Certainly. "
    return "Certainly. "


def _jarvisize_response(
    response: str,
    *,
    intent: str,
    execution_mode: str,
    user_profile: Optional[dict[str, Any]],
    session_id: str,
    command: str,
) -> str:
    text = clean_response(response)
    if not text:
        return text

    prefix = _jarvis_prefix(intent, execution_mode)
    if prefix and not re.match(r"^(certainly|analysis complete|right away|welcome back|task complete|processing your request)\b", text, flags=re.IGNORECASE):
        text = f"{prefix}{text[0].lower() + text[1:] if len(text) > 1 and text[0].isupper() else text}"

    working_memory = load_working_memory(session_id)
    last_topic = str(working_memory.active_topic or "").strip()
    if last_topic and last_topic.lower() in command.lower() and "You mentioned earlier" not in text and len(text) < 650:
        user_reference = _build_user_reference(user_profile)
        text += f"\n\nYou mentioned earlier that {last_topic} matters here, {user_reference}."

    if user_profile is None or bool(user_profile.get("proactive_suggestions", True)):
        suggestion = _infer_proactive_suggestion(intent, command)
        if suggestion and "Would you also like me to" not in text:
            text += f"\n\nWould you also like me to {suggestion}?"

    return clean_response(text)


def _build_reasoning_trace(result: dict[str, Any], elapsed_ms: float) -> dict[str, Any]:
    confidence = float(result.get("confidence", 0.0) or 0.0)
    return {
        "intent_detected": result.get("detected_intent") or result.get("intent") or "general",
        "confidence_score": round(confidence, 4),
        "agents_involved": list(result.get("used_agents") or []),
        "critical_thinking_result": "clarify" if confidence < 0.45 else "ready",
        "time_taken_ms": round(elapsed_ms, 2),
    }


def _build_context(session_id: str, user_profile: Optional[dict[str, Any]] = None, current_mode: str = "hybrid") -> AURAContext:
    user_profile = dict(user_profile or {})
    return AURAContext(
        user_id=str(user_profile.get("id") or user_profile.get("username") or "guest"),
        session_id=session_id,
        current_mode=current_mode,
        language=str(user_profile.get("language") or "en"),
        memory=load_working_memory(session_id),
        trust_level="safe",
        conversation_history=list(_get_session_history(session_id)),
        metadata=dict(user_profile),
    )


def _is_unusable_response(text: Optional[str]) -> bool:
    normalized = clean_response(text).strip().lower()
    if not normalized:
        return True
    return any(marker in normalized for marker in UNUSABLE_RESPONSE_MARKERS)


def _call_groq_direct(command: str) -> str:
    if Groq is None:
        raise RuntimeError("Groq SDK is not installed.")
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not found in .env")

    messages = response_engine_module.build_messages(command, JARVIS_SYSTEM_PROMPT)

    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        response = groq_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
        )
        content = response.choices[0].message.content or ""
        return clean_response(content)
    except Exception as error:
        print(f"[BRAIN ERROR] Groq call failed: {error}")
        raise


def _knowledge_base_result(command: str, session_id: str, user_profile: Optional[dict[str, Any]], current_mode: str) -> Optional[dict[str, Any]]:
    reply = _knowledge_base_reply(command, user_profile=user_profile)
    if not reply:
        return None
    context = _build_context(session_id, user_profile=user_profile, current_mode=current_mode)
    context.activate("memory")
    reasoning_trace = {
        "intent_detected": "memory",
        "confidence_score": 1.0,
        "agents_involved": ["memory"],
        "critical_thinking_result": "local_fact_hit",
        "time_taken_ms": 0.0,
    }
    return {
        "intent": "memory",
        "detected_intent": "memory",
        "confidence": 1.0,
        "response": reply,
        "plan": [],
        "used_agents": ["memory"],
        "agent_capabilities": runtime_core_module.build_runtime_agent_cards(["memory"]),
        "execution_mode": "knowledge_base",
        "decision": runtime_core_module.build_decision_summary("memory", 1.0, AGENT_ROUTER),
        "orchestration": {
            "primary_agent": "memory",
            "execution_order": ["memory"],
            "agent_registry_connected": True,
        },
        "permission_action": "memory_read",
        "permission": runtime_core_module.build_permission_response("memory_read", confirmed=True),
        "reasoning_trace": reasoning_trace,
        "context_window": context.conversation_history[-MAX_SESSION_EXCHANGES * 2 :],
        "mode": current_mode,
    }


def _enrich_result(
    command: str,
    result: dict[str, Any],
    *,
    session_id: str,
    user_profile: Optional[dict[str, Any]],
    current_mode: str,
    elapsed_ms: float,
) -> dict[str, Any]:
    enriched = dict(result)
    enriched["response"] = _jarvisize_response(
        str(result.get("response") or ""),
        intent=str(result.get("detected_intent") or result.get("intent") or "general"),
        execution_mode=str(result.get("execution_mode") or "chat"),
        user_profile=user_profile,
        session_id=session_id,
        command=command,
    )
    enriched["mode"] = current_mode
    enriched["reasoning_trace"] = _build_reasoning_trace(enriched, elapsed_ms)
    orchestration = dict(enriched.get("orchestration") or {})
    orchestration["agent_registry_connected"] = True
    orchestration["agent_bus_connected"] = True
    orchestration["active_agents"] = list(enriched.get("used_agents") or [])
    enriched["orchestration"] = orchestration
    enriched["context_window"] = list(_get_session_history(session_id))
    agent_bus.publish(
        "brain.response.completed",
        {
            "intent": enriched.get("detected_intent") or enriched.get("intent") or "general",
            "session_id": session_id,
            "used_agents": list(enriched.get("used_agents") or []),
        },
    )
    return enriched


def process_single_command_detailed(
    command: str,
    *,
    session_id: str = "default",
    user_profile: Optional[dict[str, Any]] = None,
    current_mode: str = "hybrid",
) -> dict[str, Any]:
    normalized_session = _normalize_session_id(session_id)
    kb_result = _knowledge_base_result(command, normalized_session, user_profile, current_mode)
    if kb_result is not None:
        _record_exchange(normalized_session, command, kb_result["response"])
        return kb_result

    _sync_context_into_response_engine(normalized_session)
    started = time.perf_counter()
    try:
        result = runtime_core_module.process_single_command_detailed(command)
    except Exception as error:
        print(f"[BRAIN ERROR] Runtime pipeline failed: {error}")
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    enriched = _enrich_result(
        command,
        result,
        session_id=normalized_session,
        user_profile=user_profile,
        current_mode=current_mode,
        elapsed_ms=elapsed_ms,
    )
    if _is_unusable_response(enriched.get("response")):
        print("[BRAIN ERROR] Runtime pipeline produced an unusable response. Attempting direct Groq fallback.")
        enriched["response"] = _call_groq_direct(command)
    _record_exchange(normalized_session, command, enriched["response"])
    return enriched


def process_command_detailed(
    command: str,
    *,
    session_id: str = "default",
    user_profile: Optional[dict[str, Any]] = None,
    current_mode: str = "hybrid",
) -> dict[str, Any]:
    normalized_session = _normalize_session_id(session_id)
    kb_result = _knowledge_base_result(command, normalized_session, user_profile, current_mode)
    if kb_result is not None:
        _record_exchange(normalized_session, command, kb_result["response"])
        return kb_result

    _sync_context_into_response_engine(normalized_session)
    started = time.perf_counter()
    try:
        result = runtime_core_module.process_command_detailed(command)
    except Exception as error:
        print(f"[BRAIN ERROR] Runtime pipeline failed: {error}")
        raise
    elapsed_ms = (time.perf_counter() - started) * 1000
    enriched = _enrich_result(
        command,
        result,
        session_id=normalized_session,
        user_profile=user_profile,
        current_mode=current_mode,
        elapsed_ms=elapsed_ms,
    )
    if _is_unusable_response(enriched.get("response")):
        print("[BRAIN ERROR] Runtime pipeline produced an unusable response. Attempting direct Groq fallback.")
        fallback = _call_groq_direct(command)
        if not _is_unusable_response(fallback):
            enriched["response"] = fallback
        else:
            fallback = clean_response(generate_response(command, system_override=JARVIS_SYSTEM_PROMPT))
            if _is_unusable_response(fallback):
                raise RuntimeError("Groq fallback returned no usable reply.")
            enriched["response"] = fallback
    _record_exchange(normalized_session, command, enriched["response"])
    return enriched


def process_single_command(command: str, **kwargs: Any) -> tuple[str, str]:
    result = process_single_command_detailed(command, **kwargs)
    return str(result.get("intent") or "general"), str(result.get("response") or "")


def process_command(command: str, **kwargs: Any) -> tuple[str, str]:
    result = process_command_detailed(command, **kwargs)
    return str(result.get("intent") or "general"), str(result.get("response") or "")
