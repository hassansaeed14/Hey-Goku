from __future__ import annotations

from typing import Any, Dict

from voice.voice_manager import build_spoken_preview, format_speech_text


BROWSER_TTS_PROVIDER = "browser_speech_synthesis"
DISABLED_BACKEND_PROVIDER = "elevenlabs"
BACKEND_TTS_DISABLED_MESSAGE = (
    "Backend TTS is disabled in this build. AURA speaks through browser speech synthesis only."
)


def tts_available() -> bool:
    return bool(get_tts_status().get("available"))


def get_tts_status() -> Dict[str, Any]:
    return {
        "provider": BROWSER_TTS_PROVIDER,
        "status": "browser_only",
        "available": True,
        "client_managed": True,
        "backend_enabled": False,
        "disabled_provider": DISABLED_BACKEND_PROVIDER,
        "message": BACKEND_TTS_DISABLED_MESSAGE,
    }


def list_voices() -> list[Dict[str, Any]]:
    return [
        {
            "id": "browser-default",
            "name": "Browser speech",
            "provider": BROWSER_TTS_PROVIDER,
            "locked": True,
            "client_managed": True,
        }
    ]


def speak_text(text: str, *, blocking: bool = True, preview_only: bool = False) -> Dict[str, Any]:
    del blocking

    payload_text = build_spoken_preview(text) if preview_only else format_speech_text(text)
    if not payload_text:
        return {
            "success": False,
            "status": "empty_text",
            "message": "Speech text is empty.",
            "provider": BROWSER_TTS_PROVIDER,
            "client_managed": True,
        }

    return {
        "success": False,
        "status": "disabled",
        "message": BACKEND_TTS_DISABLED_MESSAGE,
        "provider": BROWSER_TTS_PROVIDER,
        "client_managed": True,
        "backend_enabled": False,
        "spoken_text": payload_text,
    }


def stop_speaking() -> Dict[str, Any]:
    return {
        "success": True,
        "status": "client_managed",
        "message": "Speech playback is controlled by the browser client.",
        "provider": BROWSER_TTS_PROVIDER,
        "client_managed": True,
        "backend_enabled": False,
    }


def speak(text: str, read_full: bool = False) -> bool:
    del text, read_full
    return False
