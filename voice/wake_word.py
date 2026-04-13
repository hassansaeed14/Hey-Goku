from __future__ import annotations

import re
from typing import Dict, Iterable, List

from voice.voice_config import load_voice_settings


WAKE_VARIANT_ALIASES = {
    "aura": ("aura", "ora"),
    "hey": ("hey", "heya", "hi"),
}


def _normalize_phrase(text: str) -> str:
    lowered = str(text or "").strip().lower()
    lowered = re.sub(r"[^\w\s]+", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def _build_flexible_pattern(phrase: str) -> re.Pattern[str]:
    tokens = [re.escape(token) for token in _normalize_phrase(phrase).split() if token]
    if not tokens:
        return re.compile(r"$^")
    separator = r"[\s,.;:!?-]+"
    pattern = rf"^\s*(?:{separator})*{separator.join(tokens)}(?:{separator}|$)"
    return re.compile(pattern, flags=re.IGNORECASE)


def _candidate_variants(phrase: str) -> Iterable[tuple[str, float]]:
    normalized = _normalize_phrase(phrase)
    if not normalized:
        return []

    tokens = normalized.split()
    variants: list[tuple[str, float]] = [(normalized, 1.0)]

    if len(tokens) == 2:
        first, second = tokens
        if first in WAKE_VARIANT_ALIASES and second in WAKE_VARIANT_ALIASES:
            for first_variant in WAKE_VARIANT_ALIASES[first]:
                for second_variant in WAKE_VARIANT_ALIASES[second]:
                    variant = f"{first_variant} {second_variant}".strip()
                    confidence = 1.0 if variant == normalized else 0.92
                    variants.append((variant, confidence))

    seen: set[str] = set()
    deduped: list[tuple[str, float]] = []
    for variant, confidence in variants:
        if variant in seen:
            continue
        seen.add(variant)
        deduped.append((variant, confidence))
    return deduped


def detect_wake_word(text: str, wake_words: List[str] | None = None) -> Dict[str, object]:
    original = str(text or "").strip()
    lowered = original.lower()
    words = wake_words or load_voice_settings().wake_words
    normalized_text = re.sub(r"^[\s,.;:!?-]+", "", lowered)
    for wake_word in words:
        candidate = str(wake_word or "").strip().lower()
        if not candidate:
            continue
        for variant, confidence in _candidate_variants(candidate):
            pattern = _build_flexible_pattern(variant)
            if pattern.match(normalized_text):
                cleaned = pattern.sub("", original, count=1).strip(" ,.:;!-")
                return {
                    "detected": True,
                    "wake_word": candidate,
                    "remaining_text": cleaned,
                    "confidence": confidence,
                    "matched_at_start": True,
                }
    return {
        "detected": False,
        "wake_word": None,
        "remaining_text": original,
        "confidence": 0.0,
        "matched_at_start": False,
    }
