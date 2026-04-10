from __future__ import annotations

from typing import Any, Dict, List

from voice.voice_config import load_voice_settings
from voice.voice_manager import build_spoken_preview, choose_voice_metadata, format_speech_text

try:
    import pyttsx3  # type: ignore
except Exception:  # pragma: no cover
    pyttsx3 = None


def _build_engine():
    if pyttsx3 is None:
        return None
    try:
        return pyttsx3.init()
    except Exception:
        return None


def tts_available() -> bool:
    return _build_engine() is not None


def list_voices() -> List[Dict[str, Any]]:
    engine = _build_engine()
    if engine is None:
        return []
    voices = []
    for voice in engine.getProperty("voices"):
        voices.append(
            {
                "id": getattr(voice, "id", ""),
                "name": getattr(voice, "name", ""),
                "languages": [str(item) for item in getattr(voice, "languages", [])],
            }
        )
    return voices


def _set_voice(engine, voice_gender: str, language: str):
    voices = list_voices()
    selected = choose_voice_metadata(voices, gender=voice_gender, language=language)
    if not selected:
        return None
    try:
        engine.setProperty("voice", selected.get("id", ""))
    except Exception:
        return None
    return selected


def speak_text(text: str, *, blocking: bool = True, preview_only: bool = False) -> Dict[str, Any]:
    if not tts_available():
        return {"success": False, "status": "unavailable", "message": "Local text-to-speech backend is not available."}

    engine = _build_engine()
    settings = load_voice_settings()
    if engine is None:
        return {"success": False, "status": "engine_error", "message": "Could not initialize TTS engine."}

    try:
        base_rate = engine.getProperty("rate")
        engine.setProperty("rate", int(base_rate * float(settings.rate)))
        engine.setProperty("volume", max(0.0, min(1.0, float(settings.volume))))
        selected_voice = _set_voice(engine, settings.voice_gender, settings.language)
        payload = build_spoken_preview(text) if preview_only else format_speech_text(text)
        if not payload:
            return {"success": False, "status": "empty_text", "message": "Speech text is empty."}
        engine.say(payload)
        if blocking:
            engine.runAndWait()
        return {
            "success": True,
            "status": "spoken",
            "message": "Speech completed.",
            "persona": settings.profile_id,
            "voice_id": selected_voice.get("id", "") if selected_voice is not None else "",
            "spoken_text": payload,
        }
    except Exception as error:
        return {"success": False, "status": "tts_error", "message": str(error)}


def stop_speaking() -> Dict[str, Any]:
    if not tts_available():
        return {"success": False, "status": "unavailable", "message": "Local text-to-speech backend is not available."}
    engine = _build_engine()
    if engine is None:
        return {"success": False, "status": "engine_error", "message": "Could not initialize TTS engine."}
    try:
        engine.stop()
        return {"success": True, "status": "stopped", "message": "Speech playback stopped."}
    except Exception as error:
        return {"success": False, "status": "tts_error", "message": str(error)}


def speak(text: str, read_full: bool = False) -> bool:
    return bool(speak_text(text, preview_only=not read_full).get("success"))
