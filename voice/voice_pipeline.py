from __future__ import annotations

from typing import Any, Dict

from brain.core_ai import process_command_detailed
from voice.noise_filter import analyze_transcript_noise, clean_transcript_text
from voice.voice_controller import get_voice_status
from voice.wake_word import detect_wake_word


def process_voice_text(text: str) -> Dict[str, Any]:
    cleaned = clean_transcript_text(text)
    wake = detect_wake_word(cleaned)
    command_text = str(wake["remaining_text"] if wake.get("detected") else cleaned).strip()

    if not command_text:
        return {
            "success": False,
            "status": "empty_command",
            "message": "AURA heard the wake word but no command followed.",
            "voice": get_voice_status(),
            "noise": analyze_transcript_noise(text),
        }

    result = process_command_detailed(command_text)
    return {
        "success": True,
        "status": "processed",
        "transcript": text,
        "cleaned_transcript": cleaned,
        "wake_word": wake,
        "command_text": command_text,
        "noise": analyze_transcript_noise(text),
        "voice": get_voice_status(),
        "result": result,
    }
