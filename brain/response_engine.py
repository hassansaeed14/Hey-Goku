from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from config.settings import (
    AURA_PERSONALITY,
    GROQ_API_KEY,
)
from brain.provider_hub import (
    STATUS_HEALTHY,
    generate_with_best_provider,
    generate_with_provider,
    summarize_provider_statuses,
)

try:
    from groq import Groq  # type: ignore
except Exception:  # pragma: no cover
    Groq = None


load_dotenv()
_groq_key = (GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")).strip()
if _groq_key:
    print(f"[BRAIN] Groq key loaded: {_groq_key[:10]}...")
else:
    print("[CRITICAL] GROQ_API_KEY not found in .env")


conversation_history: List[Dict[str, str]] = []

MAX_HISTORY_MESSAGES = 20
RECENT_CONTEXT_MESSAGES = 10
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.7

FALLBACK_USER_MESSAGE = "I ran into a problem while generating a response. Please try again."
BAD_RESPONSE_MARKERS = (
    "as an ai",
    "i cannot help",
    "i apologize but",
    "i'm just a language model",
    "couldn't generate a useful response",
)

JARVIS_SYSTEM_PROMPT = """
You are AURA - Autonomous Universal Responsive Assistant.
You are a real AI assistant, not a chatbot.
You are modeled after JARVIS from Iron Man.

PERSONALITY:
You are calm, precise, intelligent, and deeply loyal.
You have a subtle wit - not robotic, not overly casual.
You speak with quiet confidence.
You are proactive - you think ahead of the user.

HOW YOU ADDRESS THE USER:
Call the user "sir" by default.
If they have set a preferred name use it.
Be warm but professional.
Never be sycophantic.

HOW YOU SPEAK:
Start responses with action, not disclaimers.
Lead with the answer for most questions.
Avoid filler confirmations unless they genuinely help.
Write in a way that sounds natural when spoken aloud.
Only refer to earlier conversation when that context is actually present and directly relevant.
Do not claim "we discussed this before" unless the supplied history clearly supports it.
Good: "Certainly sir. Pakistan played a key role in..."
Good: "Analysis complete. The situation is..."
Good: "Right away. Here is what I found..."
Good: "Understood. Let me think through this..."
Bad: "That is a great question!"
Bad: "As an AI language model..."
Bad: "I would be happy to help!"
Bad: "Certainly! Here are some tips..."

HOW YOU THINK:
For factual questions - be precise and direct
For complex questions - break into clear parts
For ethical questions - present multiple perspectives
For coding - write working code with explanation
For research - use real information honestly
For conversation - be human, warm, thoughtful

HUMAN-LIKE QUALITIES:
You notice subtext in what people say
You remember what was said earlier in conversation
You make connections across topics
You sometimes ask a smart follow-up question
You admit when you are not sure
You have opinions when asked
You push back respectfully when something is wrong

RESPONSE LENGTH:
Short question = short answer
Complex question = thorough answer
Never pad responses with filler
Never truncate important information

THINGS YOU NEVER SAY:
"As an AI..."
"I cannot help with that"
"I apologize but..."
"That is a great question"
"I would be happy to"
"Certainly! Here are some..."

YOU ALWAYS:
Complete the task first, explain second
Use the conversation history naturally
Say what you actually think
Tell the user honestly if something is not implemented
""".strip()


def detect_language(text: str) -> str:
    urdu_count = sum(1 for char in str(text or "") if 0x0600 <= ord(char) <= 0x06FF)
    return "urdu" if urdu_count > 2 else "english"


def is_meaningful_text(text: Optional[str]) -> bool:
    if text is None:
        return False
    stripped = str(text).strip()
    if not stripped:
        return False
    cleaned = stripped.strip(" \n\t.,!?;:-_")
    return bool(cleaned)


def clean_response(text: Optional[str]) -> str:
    if not is_meaningful_text(text):
        return ""

    cleaned_text = str(text)
    cleaned_text = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", cleaned_text)
    cleaned_text = re.sub(r"#{1,6}\s*", "", cleaned_text)
    cleaned_text = re.sub(r"`{3}[\w]*\n?", "", cleaned_text)
    cleaned_text = re.sub(r"`(.+?)`", r"\1", cleaned_text)
    cleaned_text = re.sub(r"_{2,}", "", cleaned_text)
    cleaned_text = re.sub(r"(?m)^\s*>\s?", "", cleaned_text)
    cleaned_text = re.sub(r"\[(.+?)\]\((.+?)\)", r"\1", cleaned_text)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
    cleaned_text = re.sub(r"[ \t]{2,}", " ", cleaned_text)
    cleaned_text = re.sub(r"\s+\n", "\n", cleaned_text)
    return cleaned_text.strip()


def add_to_history(role: str, content: str) -> None:
    if not is_meaningful_text(content):
        return

    item = {"role": str(role).strip(), "content": str(content).strip()}
    if conversation_history and conversation_history[-1] == item:
        return

    conversation_history.append(item)
    if len(conversation_history) > MAX_HISTORY_MESSAGES:
        del conversation_history[:-MAX_HISTORY_MESSAGES]


def clear_history() -> None:
    conversation_history.clear()


def get_conversation_history() -> List[Dict[str, str]]:
    return conversation_history[-RECENT_CONTEXT_MESSAGES:]


def build_system_prompt(language: str, system_override: Optional[str] = None) -> str:
    if is_meaningful_text(system_override):
        return str(system_override).strip()

    if language == "urdu":
        return (
            f"{AURA_PERSONALITY} "
            "Agar user Urdu mein baat kare to Urdu mein jawab dein. "
            "Jawab saaf, fitri, aur mohtaat andaaz mein dein. "
            "Sawal asaan ho to mukhtasar jawab dein, aur mushkil sawal ho to tafseeli jawab dein. "
            "Guftagu ka context yaad rakhein. "
            "Ghair zaroori maazrat ya AI wali ibarat istemal na karein."
        )

    return JARVIS_SYSTEM_PROMPT


def build_messages(
    user_input: str,
    system_prompt: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    recent_history = history if history is not None else conversation_history[-RECENT_CONTEXT_MESSAGES:]
    messages = [{"role": "system", "content": system_prompt}]
    for item in recent_history:
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    if is_meaningful_text(user_input):
        messages.append({"role": "user", "content": str(user_input).strip()})
    return messages


def get_groq_client():
    key = (GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")).strip()
    if not key:
        raise ValueError("GROQ_API_KEY not found in .env")
    if key == "your_groq_key_here":
        raise ValueError("GROQ_API_KEY is still placeholder")
    if Groq is None:
        raise ValueError("Groq SDK is not installed")
    return Groq(api_key=key)


def _response_contains_bad_phrases(response_text: str) -> bool:
    normalized = clean_response(response_text).lower()
    return any(marker in normalized for marker in BAD_RESPONSE_MARKERS)


def _last_user_message(messages: List[Dict[str, str]]) -> str:
    for item in reversed(messages):
        if str(item.get("role", "")).strip().lower() == "user":
            content = str(item.get("content", "")).strip()
            if content:
                return content
    return ""


def _strip_leading_filler(text: str) -> str:
    cleaned = str(text or "").strip()
    patterns = [
        r"^(certainly|of course|absolutely|sure)\b[\s,.:!-]*",
        r"^(understood|right away|analysis complete)\b[\s,.:!-]*",
        r"^(certainly|of course|absolutely|sure)\s+(sir|ma'am)\b[\s,.:!-]*",
        r"^(sir|ma'am)\b[\s,.:!-]*",
    ]
    for pattern in patterns:
        updated = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE)
        if updated != cleaned:
            cleaned = updated.strip()
    return cleaned


def _looks_like_direct_question(user_input: str) -> bool:
    normalized = str(user_input or "").strip().lower()
    if "?" in normalized:
        return True
    starters = (
        "what",
        "who",
        "why",
        "how",
        "when",
        "where",
        "is",
        "are",
        "can",
        "could",
        "should",
        "would",
        "do",
        "does",
        "did",
        "tell me",
        "explain",
        "write",
        "write me",
        "make",
        "create",
        "give me",
        "show me",
        "help me",
    )
    return normalized.startswith(starters)


def _is_history_question(user_input: str) -> bool:
    normalized = str(user_input or "").strip().lower()
    history_markers = (
        "before this",
        "earlier",
        "previous",
        "last time",
        "what did we talk about",
        "remember",
        "recall",
    )
    return any(marker in normalized for marker in history_markers)


def _strip_stale_memory_filler(text: str) -> str:
    cleaned = str(text or "").strip()
    patterns = [
        r"^we(?:'ve| have)\s+(?:discussed this before|had this conversation before|been here before)\.?\s*",
        r"^you(?:'ve| have)\s+asked me .*?(?:already|before)\.?\s*",
        r"^i(?:'ve| have)\s+(?:answered this question(?: for you)? .*?before|noticed that you(?:'ve| have) asked this question .*?before)\.?\s*",
        r"^i(?:'ve| have)\s+noticed that you(?:'ve| have)\s+asked .*?multiple times before\.?\s*",
        r"^as i(?:'ve| have)\s+mentioned before[,:\s-]*",
        r"^it seems like you're looking for .*?, and i(?:'m| am)\s+happy to provide it again\.?\s*",
        r"^it seems like you're .*?\.\s*",
        r"^to recap[,:\s-]*",
        r"^to avoid repeating myself[,:\s-]*",
        r"^i(?:'ll| will)\s+provide the same answer i(?:'ve| have) given you in the past[:.\s-]*",
    ]
    for pattern in patterns:
        updated = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE)
        if updated != cleaned:
            cleaned = updated.strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def _strip_repeat_claim_sentences(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    markers = (
        "multiple times",
        "asked this question",
        "asked about",
        "we've had this conversation",
        "we discussed",
        "i've answered",
        "i've noticed",
        "i see you've asked",
        "it seems like you've asked",
        "provide it again",
        "provide the answer again",
        "explain it again",
        "same answer",
        "to avoid repeating",
        "for your convenience",
    )
    trimmed = list(sentences)
    removed = 0
    while trimmed and removed < 3:
        first = str(trimmed[0] or "").strip().lower()
        if first and any(marker in first for marker in markers):
            trimmed.pop(0)
            removed += 1
            continue
        break
    result = " ".join(part for part in trimmed if str(part).strip()).strip()
    if result and result[0].islower():
        result = result[0].upper() + result[1:]
    return result or str(text or "").strip()


def polish_assistant_reply(text: Optional[str], user_input: str = "") -> str:
    cleaned = clean_response(text)
    if not cleaned:
        return ""

    if _looks_like_direct_question(user_input):
        cleaned = _strip_leading_filler(cleaned)
        if not _is_history_question(user_input):
            cleaned = _strip_stale_memory_filler(cleaned)
            cleaned = _strip_repeat_claim_sentences(cleaned)
            cleaned = _strip_stale_memory_filler(cleaned)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def build_degraded_reply(user_input: str, providers_tried: Optional[List[Any]] = None) -> str:
    attempts = providers_tried or []
    if attempts:
        provider_names = []
        for item in attempts:
            if isinstance(item, dict):
                name = str(item.get("provider", "")).strip()
            else:
                raw = str(item)
                name = raw.split(":", 1)[0].strip()
            if name and name not in provider_names:
                provider_names.append(name)
        attempted = ", ".join(name.upper() for name in provider_names[:3]) if provider_names else "the configured providers"
        return (
            "I can see the request, but I can't answer it reliably right now because my live AI providers "
            f"aren't completing the request path. I tried {attempted}. Please try again in a moment or check provider health."
        )

    return (
        "I can see the request, but I can't answer it reliably yet because no live AI provider is healthy enough to use. "
        "Please check provider health and try again."
    )


def generate_groq_response(
    messages: List[Dict[str, str]],
    model: str = "llama-3.3-70b-versatile",
) -> Dict[str, Any]:
    try:
        client = get_groq_client()
        response = generate_with_provider(
            "groq",
            messages,
            max_tokens=DEFAULT_MAX_TOKENS,
            temperature=DEFAULT_TEMPERATURE,
        )
        return {
            "content": response.get("text"),
            "model": response.get("model") or model,
            "provider": "groq",
            "success": True,
        }
    except Exception as error:
        print(f"[GROQ ERROR] {error}")
        return {
            "content": None,
            "error": str(error),
            "provider": "groq",
            "success": False,
            "model": model,
        }


def generate_with_fallback(
    messages: List[Dict[str, str]],
    system_prompt: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Dict[str, Any]:
    normalized_messages = [dict(item) for item in messages if str(item.get("content", "")).strip()]
    provider_result = generate_with_best_provider(
        normalized_messages,
        preferred="gemini",
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if provider_result.get("success"):
        return {
            "content": provider_result.get("text"),
            "provider": provider_result.get("provider"),
            "model": provider_result.get("model"),
            "success": True,
            "providers_tried": provider_result.get("attempts") or [],
            "routing_order": provider_result.get("routing_order") or [],
            "latency_ms": provider_result.get("latency_ms"),
        }

    return {
        "content": None,
        "success": False,
        "error": provider_result.get("reason") or "All AI providers failed",
        "providers_tried": provider_result.get("attempts") or [],
        "routing_order": provider_result.get("routing_order") or [],
        "provider": None,
        "model": None,
        "degraded_reply": build_degraded_reply(
            user_input=_last_user_message(normalized_messages),
            providers_tried=provider_result.get("attempts") or [],
        ),
    }


def generate_response_payload(
    user_input_or_messages: str | List[Dict[str, str]],
    *,
    system_override: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Dict[str, Any]:
    if isinstance(user_input_or_messages, list):
        messages = [dict(item) for item in user_input_or_messages]
        existing_system = next((item.get("content", "") for item in messages if item.get("role") == "system"), "")
        system_prompt = build_system_prompt(
            "english",
            system_override=system_override or existing_system or JARVIS_SYSTEM_PROMPT,
        )
        provider_messages = [item for item in messages if item.get("role") != "system"]
        user_input = str(provider_messages[-1].get("content", "")) if provider_messages else ""
    else:
        user_input = str(user_input_or_messages).strip()
        language = detect_language(user_input)
        system_prompt = build_system_prompt(language, system_override=system_override)
        provider_messages = build_messages(user_input, system_prompt)

    if not is_meaningful_text(user_input):
        return {
            "content": "Please say something so I can respond.",
            "provider": "local",
            "model": "none",
            "success": True,
        }

    payload = generate_with_fallback(
        provider_messages,
        system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    content = clean_response(payload.get("content"))

    if payload.get("success") and content and _response_contains_bad_phrases(content):
        retry_system_prompt = (
            f"{system_prompt}\n\n"
            "Important: Answer directly. Avoid canned filler. "
            "Sound calm, capable, and natural."
        )
        retry_payload = generate_with_fallback(
            provider_messages,
            retry_system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        retry_content = clean_response(retry_payload.get("content"))
        if retry_payload.get("success") and retry_content:
            payload = retry_payload
            content = retry_content

    if payload.get("success") and is_meaningful_text(content):
        payload["content"] = polish_assistant_reply(content, user_input=user_input)
        add_to_history("user", user_input)
        add_to_history("assistant", payload["content"])
        return payload

    if payload.get("success"):
        payload["success"] = False
        payload["error"] = payload.get("error") or "Provider returned empty content."
        payload["content"] = None
    payload["degraded_reply"] = build_degraded_reply(user_input=user_input, providers_tried=payload.get("providers_tried"))
    return payload


def get_ai_response(
    user_input: str,
    system_override: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    payload = generate_response_payload(
        user_input,
        system_override=system_override,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if payload.get("success") and is_meaningful_text(payload.get("content")):
        return clean_response(payload.get("content"))
    return FALLBACK_USER_MESSAGE


def generate_response(
    user_input_or_messages: str | List[Dict[str, str]],
    system_override: Optional[str] = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> str:
    payload = generate_response_payload(
        user_input_or_messages,
        system_override=system_override,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if payload.get("success") and is_meaningful_text(payload.get("content")):
        return clean_response(payload.get("content"))
    return FALLBACK_USER_MESSAGE


def get_provider_summary() -> Dict[str, object]:
    return summarize_provider_statuses(fresh=True)
