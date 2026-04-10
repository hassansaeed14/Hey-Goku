from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from voice.voice_manager import load_user_profile, load_voice_profiles, resolve_voice_profile, save_user_profile


@dataclass(slots=True)
class VoiceSettings:
    profile_id: str = "jarvis"
    persona: str = "jarvis"
    language: str = "en-US"
    voice_gender: str = "male"
    rate: float = 0.95
    pitch: float = 0.85
    volume: float = 1.0
    wake_words: List[str] = field(default_factory=lambda: ["hey aura", "aura"])
    wake_word_sensitivity: float = 0.7
    phrase_time_limit: int = 8
    ambient_noise_adjustment: bool = True
    backend: str = "local_hybrid"
    enabled: bool = True
    auto_speak_responses: bool = True
    preferred_input_device: Optional[str] = None
    preferred_output_device: Optional[str] = None
    preferred_provider: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def load_voice_settings() -> VoiceSettings:
    user_profile = load_user_profile()
    profile_id = str(user_profile.get("voice_profile") or "jarvis").strip().lower()
    voice_profile = resolve_voice_profile(profile_id)
    merged = VoiceSettings(
        profile_id=profile_id,
        persona=profile_id,
        language=str(user_profile.get("language") or voice_profile.get("language") or "en-US"),
        voice_gender=str(user_profile.get("voice_gender") or voice_profile.get("gender") or "male"),
        rate=float(user_profile.get("voice_rate") or voice_profile.get("rate") or 0.95),
        pitch=float(user_profile.get("voice_pitch") or voice_profile.get("pitch") or 0.85),
        volume=float(user_profile.get("voice_volume") or voice_profile.get("volume") or 1.0),
        auto_speak_responses=bool(user_profile.get("auto_speak", True)),
    )
    return merged


def save_voice_settings(settings: VoiceSettings) -> VoiceSettings:
    user_profile = load_user_profile()
    user_profile.update(
        {
            "voice_profile": settings.profile_id,
            "voice_gender": settings.voice_gender,
            "voice_rate": settings.rate,
            "voice_pitch": settings.pitch,
            "voice_volume": settings.volume,
            "language": settings.language,
            "auto_speak": settings.auto_speak_responses,
        }
    )
    save_user_profile(user_profile)
    return settings


def update_voice_settings(**updates: object) -> VoiceSettings:
    settings = load_voice_settings()
    for key, value in updates.items():
        if value is None:
            continue
        if key == "persona":
            key = "profile_id"
        if key == "voice_profile":
            key = "profile_id"
        if hasattr(settings, key):
            setattr(settings, key, value)
    return save_voice_settings(settings)


def list_voice_personas() -> List[Dict[str, str]]:
    profiles = load_voice_profiles()
    return [
        {
            "id": profile_id,
            "name": profile_id.replace("_", " ").title(),
            "description": str(payload.get("description") or ""),
            "gender": str(payload.get("gender") or ""),
            "language": str(payload.get("language") or ""),
        }
        for profile_id, payload in profiles.items()
    ]
