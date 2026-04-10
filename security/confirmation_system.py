from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import bcrypt

from security.security_config import CONFIRMATION_CODES_FILE


class ConfirmationSystem:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or CONFIRMATION_CODES_FILE

    def _load(self) -> Dict[str, Dict[str, str]]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _save(self, payload: Dict[str, Dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def code_exists(self, user_id: str) -> bool:
        payload = self._load()
        return bool(payload.get(str(user_id or "").strip()))

    def set_confirmation_code(self, user_id: str, code: str) -> bool:
        normalized_user = str(user_id or "").strip()
        normalized_code = str(code or "").strip()
        if not normalized_user or len(normalized_code) < 4:
            return False
        payload = self._load()
        payload[normalized_user] = {
            "hash": bcrypt.hashpw(normalized_code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        }
        self._save(payload)
        return True

    def verify_code(self, user_id: str, code: str) -> bool:
        payload = self._load()
        entry = payload.get(str(user_id or "").strip())
        if not entry:
            return False
        try:
            return bcrypt.checkpw(str(code or "").strip().encode("utf-8"), str(entry["hash"]).encode("utf-8"))
        except Exception:
            return False

    def change_code(self, user_id: str, old_code: str, new_code: str) -> bool:
        if not self.verify_code(user_id, old_code):
            return False
        return self.set_confirmation_code(user_id, new_code)
