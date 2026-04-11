from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional

import requests

from config.settings import (
    ANTHROPIC_API_KEY,
    DEFAULT_REASONING_PROVIDER,
    GEMINI_API_KEY,
    GROQ_API_KEY,
    OLLAMA_BASE_URL,
    OPENAI_API_KEY,
    OPENROUTER_API_KEY,
    PROVIDER_MODEL_MAP,
    PROVIDER_PRIORITY,
)

try:
    from groq import Groq  # type: ignore
except Exception:  # pragma: no cover
    Groq = None

try:
    from openai import OpenAI  # type: ignore
except Exception:  # pragma: no cover
    OpenAI = None

try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None


STATUS_NOT_CONFIGURED = "not_configured"
STATUS_CONFIGURED_UNVERIFIED = "configured_unverified"
STATUS_HEALTHY = "healthy"
STATUS_DEGRADED = "degraded"
STATUS_AUTH_FAILED = "auth_failed"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_UNAVAILABLE = "unavailable"

HEALTHY_STATES = {STATUS_HEALTHY}
NON_RETRYABLE_STATES = {STATUS_AUTH_FAILED, STATUS_RATE_LIMITED}
SUPPORTED_PROVIDERS = ("gemini", "openai", "groq", "openrouter", "claude", "ollama")
DEFAULT_TIMEOUT = 30
HEALTH_TTL_SECONDS = 60


@dataclass(slots=True)
class ProviderStatus:
    provider: str
    model: str
    mode: str
    configured: bool
    available: bool
    installed: bool
    reason: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None
    status: str = STATUS_NOT_CONFIGURED
    verified: bool = False
    last_checked_at: Optional[float] = None
    last_success_at: Optional[float] = None
    last_failure_at: Optional[float] = None
    last_used_at: Optional[float] = None
    routing_order: int = 0
    source: str = "config"

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["response_time_ms"] = self.latency_ms
        return payload


class ProviderError(Exception):
    """Base provider error."""


class ProviderExecutionError(ProviderError):
    """Provider call failure with a classified health status."""

    def __init__(
        self,
        provider: str,
        *,
        status: str,
        error: str,
        latency_ms: Optional[float] = None,
        model: Optional[str] = None,
    ) -> None:
        super().__init__(error)
        self.provider = provider
        self.status = status
        self.error = error
        self.latency_ms = latency_ms
        self.model = model


def _provider_model(provider: str) -> str:
    return PROVIDER_MODEL_MAP.get(str(provider or "").strip().lower(), "unknown")


def _message_text(messages: Iterable[Dict[str, str]], role: str) -> str:
    return "\n".join(
        str(item.get("content", "")).strip()
        for item in messages
        if str(item.get("role", "")).strip().lower() == role and str(item.get("content", "")).strip()
    ).strip()


def _messages_to_prompt(messages: List[Dict[str, str]]) -> str:
    parts = []
    for item in messages:
        role = str(item.get("role", "user")).strip().title()
        content = str(item.get("content", "")).strip()
        if content:
            parts.append(f"{role}: {content}")
    return "\n\n".join(parts).strip()


def _normalize_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    normalized = []
    for item in messages:
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if role in {"system", "user", "assistant"} and content:
            normalized.append({"role": role, "content": content})
    return normalized


def _build_gemini_history(messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    for msg in messages[:-1]:
        role = str(msg.get("role", "")).strip().lower()
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        if role == "user":
            history.append({"role": "user", "parts": [content]})
        elif role == "assistant":
            history.append({"role": "model", "parts": [content]})
    return history


def _extract_gemini_text(response: Any) -> str:
    try:
        quick_text = str(getattr(response, "text", "") or "").strip()
        if quick_text:
            return quick_text
    except Exception:
        pass

    candidates = list(getattr(response, "candidates", []) or [])
    text_parts: List[str] = []

    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = list(getattr(content, "parts", []) or []) if content is not None else []
        for part in parts:
            text = getattr(part, "text", None)
            if text is None and isinstance(part, dict):
                text = part.get("text")
            cleaned = str(text or "").strip()
            if cleaned:
                text_parts.append(cleaned)

    if text_parts:
        return "\n".join(text_parts).strip()

    finish_reason = None
    if candidates:
        finish_reason = getattr(candidates[0], "finish_reason", None)
    prompt_feedback = getattr(response, "prompt_feedback", None)
    raise ValueError(
        "Gemini returned no text content."
        f" finish_reason={finish_reason!r}"
        f" prompt_feedback={prompt_feedback!r}"
    )


def _error_status(error: str) -> tuple[str, str]:
    normalized = str(error or "").strip().lower()
    if any(token in normalized for token in ("401", "unauthorized", "invalid api key", "invalid_api_key", "authentication", "api key not valid")):
        return STATUS_AUTH_FAILED, "Authentication failed."
    if any(token in normalized for token in ("429", "rate limit", "too many requests", "quota", "insufficient_quota", "resource_exhausted", "quota exceeded", "free_tier_requests")):
        return STATUS_RATE_LIMITED, "Provider is rate limited."
    if any(token in normalized for token in ("timed out", "timeout", "connection", "max retries exceeded", "refused", "service unavailable", "502", "503", "504", "404", "no endpoints found")):
        return STATUS_UNAVAILABLE, "Provider is unavailable."
    return STATUS_DEGRADED, "Provider call failed."


class ProviderHub:
    """Shared provider routing and health source of truth for AURA."""

    def __init__(self) -> None:
        self._status_cache: dict[str, ProviderStatus] = {}

    def _routing_order(self, preferred: Optional[str] = None) -> List[str]:
        desired = str(preferred or DEFAULT_REASONING_PROVIDER or "").strip().lower()
        ordered: List[str] = []
        if desired and desired not in {"router", "auto"} and desired in SUPPORTED_PROVIDERS:
            ordered.append(desired)
        for provider in PROVIDER_PRIORITY:
            if provider in SUPPORTED_PROVIDERS and provider not in ordered:
                ordered.append(provider)
        for provider in SUPPORTED_PROVIDERS:
            if provider not in ordered:
                ordered.append(provider)
        return ordered

    def _routing_index(self, provider: str) -> int:
        ordered = self._routing_order()
        try:
            return ordered.index(provider)
        except ValueError:
            return len(ordered)

    def _is_installed(self, provider: str) -> bool:
        normalized = str(provider or "").strip().lower()
        if normalized in {"openai", "openrouter"}:
            return OpenAI is not None
        if normalized == "groq":
            return Groq is not None
        if normalized == "gemini":
            return genai is not None
        if normalized in {"claude", "ollama"}:
            return True
        return False

    def _is_configured(self, provider: str) -> bool:
        normalized = str(provider or "").strip().lower()
        if normalized == "groq":
            return bool(GROQ_API_KEY)
        if normalized == "gemini":
            return bool(GEMINI_API_KEY)
        if normalized == "openai":
            return bool(OPENAI_API_KEY)
        if normalized == "openrouter":
            return bool(OPENROUTER_API_KEY)
        if normalized == "claude":
            return bool(ANTHROPIC_API_KEY)
        if normalized == "ollama":
            return bool(OLLAMA_BASE_URL)
        return False

    def _base_status(self, provider: str) -> ProviderStatus:
        normalized = str(provider or "").strip().lower()
        configured = self._is_configured(normalized)
        installed = self._is_installed(normalized)
        if not configured:
            status = STATUS_NOT_CONFIGURED
            reason = "Provider is not configured."
        elif not installed:
            status = STATUS_UNAVAILABLE
            reason = "Provider SDK is not installed."
        else:
            status = STATUS_CONFIGURED_UNVERIFIED
            reason = "Provider is configured but has not passed a live check yet."
        return ProviderStatus(
            provider=normalized,
            model=_provider_model(normalized),
            mode="real" if status in {STATUS_CONFIGURED_UNVERIFIED, STATUS_HEALTHY} else "hybrid",
            configured=configured,
            available=status == STATUS_HEALTHY,
            installed=installed,
            reason=reason,
            status=status,
            verified=False,
            routing_order=self._routing_index(normalized),
            source="config",
        )

    def _cache_valid(self, status: ProviderStatus) -> bool:
        if not status.last_checked_at:
            return False
        return (time.time() - float(status.last_checked_at)) < HEALTH_TTL_SECONDS

    def _get_cached(self, provider: str, *, include_stale: bool = False) -> Optional[ProviderStatus]:
        status = self._status_cache.get(provider)
        if not status:
            return None
        if include_stale or self._cache_valid(status):
            return status
        return None

    def _store_status(
        self,
        provider: str,
        *,
        status: str,
        reason: str,
        error: Optional[str] = None,
        latency_ms: Optional[float] = None,
        source: str = "runtime",
        model: Optional[str] = None,
        used: bool = False,
    ) -> ProviderStatus:
        previous = self._status_cache.get(provider)
        now = time.time()
        record = ProviderStatus(
            provider=provider,
            model=model or _provider_model(provider),
            mode="real" if status in {STATUS_CONFIGURED_UNVERIFIED, STATUS_HEALTHY} else "hybrid",
            configured=self._is_configured(provider),
            available=status == STATUS_HEALTHY,
            installed=self._is_installed(provider),
            reason=reason,
            latency_ms=round(float(latency_ms), 2) if latency_ms is not None else None,
            error=error,
            status=status,
            verified=status != STATUS_CONFIGURED_UNVERIFIED,
            last_checked_at=now,
            last_success_at=now if status == STATUS_HEALTHY else getattr(previous, "last_success_at", None),
            last_failure_at=now if status != STATUS_HEALTHY else getattr(previous, "last_failure_at", None),
            last_used_at=now if used else getattr(previous, "last_used_at", None),
            routing_order=self._routing_index(provider),
            source=source,
        )
        self._status_cache[provider] = record
        return record

    def _should_skip_for_runtime(self, status: ProviderStatus) -> bool:
        if not status.configured or not status.installed:
            return True
        if status.status in NON_RETRYABLE_STATES and (status.last_checked_at is None or self._cache_valid(status)):
            return True
        return False

    def _call_groq(self, messages: List[Dict[str, str]], *, max_tokens: int, temperature: float) -> str:
        if Groq is None or not GROQ_API_KEY:
            raise ProviderExecutionError("groq", status=STATUS_NOT_CONFIGURED, error="Groq provider is not configured.", model=_provider_model("groq"))
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=_provider_model("groq"),
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return str(response.choices[0].message.content or "").strip()

    def _call_openai(self, messages: List[Dict[str, str]], *, max_tokens: int, temperature: float) -> str:
        if OpenAI is None or not OPENAI_API_KEY:
            raise ProviderExecutionError("openai", status=STATUS_NOT_CONFIGURED, error="OpenAI provider is not configured.", model=_provider_model("openai"))
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=_provider_model("openai"),
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return str(response.choices[0].message.content or "").strip()

    def _call_openrouter(self, messages: List[Dict[str, str]], *, max_tokens: int, temperature: float) -> str:
        if OpenAI is None or not OPENROUTER_API_KEY:
            raise ProviderExecutionError("openrouter", status=STATUS_NOT_CONFIGURED, error="OpenRouter provider is not configured.", model=_provider_model("openrouter"))
        client = OpenAI(api_key=OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1")
        response = client.chat.completions.create(
            model=_provider_model("openrouter"),
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return str(response.choices[0].message.content or "").strip()

    def _call_gemini(self, messages: List[Dict[str, str]], *, max_tokens: int, temperature: float) -> str:
        if genai is None or not GEMINI_API_KEY:
            raise ProviderExecutionError("gemini", status=STATUS_NOT_CONFIGURED, error="Gemini provider is not configured.", model=_provider_model("gemini"))
        genai.configure(api_key=GEMINI_API_KEY)
        normalized_messages = _normalize_messages(messages)
        system_prompt = _message_text(normalized_messages, "system")
        conversation = [item for item in normalized_messages if item.get("role") != "system"]
        latest_user = next(
            (item.get("content", "") for item in reversed(conversation) if item.get("role") == "user"),
            "",
        )
        if not latest_user:
            latest_user = _messages_to_prompt(conversation) or "ping"

        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        model_name = _provider_model("gemini")
        model = genai.GenerativeModel(model_name, system_instruction=system_prompt or None)
        history = _build_gemini_history(conversation)
        chat = model.start_chat(history=history)
        response = chat.send_message(latest_user, generation_config=generation_config)
        return _extract_gemini_text(response)

    def _call_claude(self, messages: List[Dict[str, str]], *, max_tokens: int, temperature: float) -> str:
        if not ANTHROPIC_API_KEY:
            raise ProviderExecutionError("claude", status=STATUS_NOT_CONFIGURED, error="Claude provider is not configured.", model=_provider_model("claude"))
        normalized_messages = _normalize_messages(messages)
        system_prompt = _message_text(normalized_messages, "system")
        non_system = [item for item in normalized_messages if item.get("role") != "system"]
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            timeout=DEFAULT_TIMEOUT,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": _provider_model("claude"),
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_prompt,
                "messages": non_system,
            },
        )
        response.raise_for_status()
        payload = response.json()
        text_parts = []
        for item in payload.get("content", []):
            if item.get("type") == "text":
                text_parts.append(str(item.get("text", "")).strip())
        return "\n".join(part for part in text_parts if part).strip()

    def _call_ollama(self, messages: List[Dict[str, str]], *, max_tokens: int, temperature: float) -> str:
        if not OLLAMA_BASE_URL:
            raise ProviderExecutionError("ollama", status=STATUS_NOT_CONFIGURED, error="Ollama base URL is not configured.", model=_provider_model("ollama"))
        normalized_messages = _normalize_messages(messages)
        system_prompt = _message_text(normalized_messages, "system")
        prompt = _messages_to_prompt([item for item in normalized_messages if item.get("role") != "system"])
        response = requests.post(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate",
            timeout=DEFAULT_TIMEOUT,
            headers={"content-type": "application/json"},
            json={
                "model": _provider_model("ollama"),
                "system": system_prompt,
                "prompt": prompt or "ping",
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("response", "")).strip()

    def _call_provider(
        self,
        provider: str,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> str:
        normalized = str(provider or "").strip().lower()
        if normalized == "gemini":
            return self._call_gemini(messages, max_tokens=max_tokens, temperature=temperature)
        if normalized == "openai":
            return self._call_openai(messages, max_tokens=max_tokens, temperature=temperature)
        if normalized == "groq":
            return self._call_groq(messages, max_tokens=max_tokens, temperature=temperature)
        if normalized == "openrouter":
            return self._call_openrouter(messages, max_tokens=max_tokens, temperature=temperature)
        if normalized == "claude":
            return self._call_claude(messages, max_tokens=max_tokens, temperature=temperature)
        if normalized == "ollama":
            return self._call_ollama(messages, max_tokens=max_tokens, temperature=temperature)
        raise ProviderExecutionError(normalized or "unknown", status=STATUS_UNAVAILABLE, error=f"Unknown provider: {provider}", model=_provider_model(normalized))

    def check_provider(self, provider: str, *, fresh: bool = True) -> dict[str, Any]:
        normalized = str(provider or "").strip().lower()
        if not normalized:
            return self._base_status("unknown").to_dict()

        if not fresh:
            cached = self._get_cached(normalized)
            if cached:
                return cached.to_dict()
            return self._base_status(normalized).to_dict()

        base = self._base_status(normalized)
        if base.status != STATUS_CONFIGURED_UNVERIFIED:
            self._status_cache[normalized] = base
            return base.to_dict()

        probe_messages = [
            {"role": "system", "content": "Reply with exactly OK."},
            {"role": "user", "content": "OK?"},
        ]
        probe_max_tokens = 64 if normalized == "gemini" else 8
        started = time.perf_counter()
        try:
            self._call_provider(normalized, probe_messages, max_tokens=probe_max_tokens, temperature=0.0)
            status = self._store_status(
                normalized,
                status=STATUS_HEALTHY,
                reason="Live health check passed.",
                latency_ms=(time.perf_counter() - started) * 1000,
                source="health_check",
                model=_provider_model(normalized),
            )
            return status.to_dict()
        except ProviderExecutionError as error:
            status = self._store_status(
                normalized,
                status=error.status,
                reason=_error_status(error.error)[1],
                error=error.error,
                latency_ms=error.latency_ms or (time.perf_counter() - started) * 1000,
                source="health_check",
                model=error.model or _provider_model(normalized),
            )
            return status.to_dict()
        except Exception as error:
            classified_status, reason = _error_status(str(error))
            status = self._store_status(
                normalized,
                status=classified_status,
                reason=reason,
                error=str(error),
                latency_ms=(time.perf_counter() - started) * 1000,
                source="health_check",
                model=_provider_model(normalized),
            )
            return status.to_dict()

    def check_gemini(self, fresh: bool = True) -> dict[str, Any]:
        return self.check_provider("gemini", fresh=fresh)

    def check_openai(self, fresh: bool = True) -> dict[str, Any]:
        return self.check_provider("openai", fresh=fresh)

    def check_groq(self, fresh: bool = True) -> dict[str, Any]:
        return self.check_provider("groq", fresh=fresh)

    def check_openrouter(self, fresh: bool = True) -> dict[str, Any]:
        return self.check_provider("openrouter", fresh=fresh)

    def check_claude(self, fresh: bool = True) -> dict[str, Any]:
        return self.check_provider("claude", fresh=fresh)

    def check_ollama(self, fresh: bool = True) -> dict[str, Any]:
        return self.check_provider("ollama", fresh=fresh)

    def probe_provider(self, provider: str, fresh: bool = False) -> dict[str, Any]:
        return self.check_provider(provider, fresh=fresh)

    def generate_with_provider(
        self,
        provider: str,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        normalized = str(provider or "").strip().lower()
        started = time.perf_counter()
        try:
            normalized_messages = _normalize_messages(messages)
            text = self._call_provider(
                normalized,
                normalized_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if not text.strip():
                raise ProviderExecutionError(
                    normalized,
                    status=STATUS_DEGRADED,
                    error="Provider returned empty content.",
                    model=_provider_model(normalized),
                )
            latency_ms = (time.perf_counter() - started) * 1000
            self._store_status(
                normalized,
                status=STATUS_HEALTHY,
                reason="Recent live inference succeeded.",
                latency_ms=latency_ms,
                source="runtime_inference",
                model=_provider_model(normalized),
                used=True,
            )
            return {
                "success": True,
                "provider": normalized,
                "model": _provider_model(normalized),
                "text": text.strip(),
                "latency_ms": round(latency_ms, 2),
                "status": STATUS_HEALTHY,
            }
        except ProviderExecutionError as error:
            latency_ms = error.latency_ms or (time.perf_counter() - started) * 1000
            self._store_status(
                normalized,
                status=error.status,
                reason=_error_status(error.error)[1],
                error=error.error,
                latency_ms=latency_ms,
                source="runtime_inference",
                model=error.model or _provider_model(normalized),
                used=True,
            )
            raise ProviderExecutionError(
                normalized,
                status=error.status,
                error=error.error,
                latency_ms=round(latency_ms, 2),
                model=error.model or _provider_model(normalized),
            )
        except Exception as error:
            latency_ms = (time.perf_counter() - started) * 1000
            classified_status, reason = _error_status(str(error))
            self._store_status(
                normalized,
                status=classified_status,
                reason=reason,
                error=str(error),
                latency_ms=latency_ms,
                source="runtime_inference",
                model=_provider_model(normalized),
                used=True,
            )
            raise ProviderExecutionError(
                normalized,
                status=classified_status,
                error=str(error),
                latency_ms=round(latency_ms, 2),
                model=_provider_model(normalized),
            )

    def generate_with_best_provider(
        self,
        messages: List[Dict[str, str]],
        *,
        preferred: Optional[str] = None,
        max_tokens: int,
        temperature: float,
    ) -> Dict[str, Any]:
        attempts: List[Dict[str, Any]] = []
        route_order = self._routing_order(preferred=preferred)

        for provider in route_order:
            status = get_provider_status(provider, fresh=False)
            if self._should_skip_for_runtime(status):
                attempts.append(
                    {
                        "provider": provider,
                        "status": status.status,
                        "reason": status.reason,
                    }
                )
                continue

            try:
                result = self.generate_with_provider(
                    provider,
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                result["attempts"] = attempts + [{"provider": provider, "status": STATUS_HEALTHY, "reason": "routed successfully"}]
                result["routing_order"] = route_order
                return result
            except ProviderExecutionError as error:
                attempts.append(
                    {
                        "provider": provider,
                        "status": error.status,
                        "reason": error.error,
                    }
                )

        return {
            "success": False,
            "provider": None,
            "model": None,
            "text": "",
            "attempts": attempts,
            "reason": "No healthy AI provider completed the request.",
            "routing_order": route_order,
        }

    def get_best_provider(self) -> dict[str, Any]:
        for provider in self._routing_order():
            status = get_provider_status(provider, fresh=False)
            if status.status == STATUS_HEALTHY:
                return status.to_dict()
        for provider in self._routing_order():
            status = get_provider_status(provider, fresh=False)
            if status.status == STATUS_CONFIGURED_UNVERIFIED:
                return status.to_dict()
        return {"status": STATUS_UNAVAILABLE, "error": "No providers are currently healthy."}

    def get_all_statuses(self, fresh: bool = False) -> Dict[str, dict[str, Any]]:
        return {provider: self.check_provider(provider, fresh=fresh) for provider in self._routing_order()}


provider_hub = ProviderHub()


def get_provider_status(provider: str, *, fresh: bool = False) -> ProviderStatus:
    normalized = str(provider or "").strip().lower()
    if fresh:
        payload = provider_hub.probe_provider(normalized, fresh=True)
        return ProviderStatus(
            provider=payload["provider"],
            model=payload.get("model") or _provider_model(normalized),
            mode="real" if payload["status"] in {STATUS_HEALTHY, STATUS_CONFIGURED_UNVERIFIED} else "hybrid",
            configured=bool(payload.get("configured", provider_hub._is_configured(normalized))),
            available=payload["status"] == STATUS_HEALTHY,
            installed=bool(payload.get("installed", provider_hub._is_installed(normalized))),
            reason=str(payload.get("reason") or payload.get("error") or payload["status"]),
            latency_ms=payload.get("latency_ms"),
            error=payload.get("error"),
            status=payload["status"],
            verified=bool(payload.get("verified", payload["status"] != STATUS_CONFIGURED_UNVERIFIED)),
            last_checked_at=payload.get("last_checked_at"),
            last_success_at=payload.get("last_success_at"),
            last_failure_at=payload.get("last_failure_at"),
            last_used_at=payload.get("last_used_at"),
            routing_order=int(payload.get("routing_order", provider_hub._routing_index(normalized))),
            source=str(payload.get("source") or "health_check"),
        )

    cached = provider_hub._get_cached(normalized, include_stale=True)
    if cached:
        return cached
    return provider_hub._base_status(normalized)


def list_provider_statuses(*, fresh: bool = False) -> List[Dict[str, Any]]:
    return [get_provider_status(provider, fresh=fresh).to_dict() for provider in provider_hub._routing_order()]


def summarize_provider_statuses(*, fresh: bool = False) -> Dict[str, Any]:
    items = list_provider_statuses(fresh=fresh)
    healthy = [item["provider"] for item in items if item["status"] == STATUS_HEALTHY]
    configured = [item["provider"] for item in items if item["configured"]]
    verified = [item["provider"] for item in items if item.get("verified")]
    return {
        "default_provider": DEFAULT_REASONING_PROVIDER,
        "routing_order": provider_hub._routing_order(),
        "available": healthy,
        "healthy": healthy,
        "configured": configured,
        "verified": verified,
        "items": items,
        "providers": {item["provider"]: item["status"] for item in items},
    }


def pick_provider(preferred: Optional[str] = None) -> Optional[str]:
    ordered = provider_hub._routing_order(preferred=preferred)
    for provider in ordered:
        status = get_provider_status(provider, fresh=False)
        if status.status == STATUS_HEALTHY:
            return provider
    return None


def generate_with_provider(
    provider: str,
    messages: List[Dict[str, str]],
    *,
    max_tokens: int,
    temperature: float,
) -> Dict[str, Any]:
    return provider_hub.generate_with_provider(
        provider,
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def generate_with_best_provider(
    messages: List[Dict[str, str]],
    *,
    preferred: Optional[str] = None,
    max_tokens: int,
    temperature: float,
) -> Dict[str, Any]:
    return provider_hub.generate_with_best_provider(
        messages,
        preferred=preferred,
        max_tokens=max_tokens,
        temperature=temperature,
    )
