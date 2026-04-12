import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import api.api_server as api_server


class PublicAccessTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api_server.app)

    def test_home_page_is_public_after_setup(self):
        with patch.object(api_server, "requires_first_run_setup", return_value=False), patch.object(
            api_server,
            "_current_user",
            return_value=None,
        ), patch.object(
            api_server,
            "_read_html",
            return_value="<html><body>AURA</body></html>",
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AURA", response.text)

    def test_api_chat_returns_consistent_payload_without_login(self):
        context = {
            "raw_message": "hello",
            "requested_mode": "hybrid",
            "session_id": "public-session",
            "cleaned_message": "hello",
            "detected_intent": "general",
            "confidence": 0.91,
            "decision": {"agent": "general"},
            "permission": {"success": True, "status": "approved", "permission": {"trust_level": "safe"}},
            "user": None,
            "user_profile": {},
            "confirmation_required": False,
            "confirmation_ok": False,
        }
        payload = {
            "success": True,
            "content": "Hello. How can I help?",
            "reply": "Hello. How can I help?",
            "provider": "groq",
            "error": None,
            "status": "ok",
            "intent": "general",
            "agent_used": "general",
            "agent": "general",
            "mode": "hybrid",
        }

        with patch.object(api_server, "requires_first_run_setup", return_value=False), patch.object(
            api_server,
            "_current_user",
            return_value=None,
        ), patch.object(
            api_server,
            "_prepare_chat_context",
            return_value=context,
        ), patch.object(
            api_server,
            "_execute_chat_pipeline",
            return_value=payload,
        ), patch.object(
            api_server,
            "_attempt_persist_chat_turn",
            return_value={"saved": True},
        ):
            response = self.client.post("/api/chat", json={"message": "hello", "mode": "hybrid"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["content"], "Hello. How can I help?")
        self.assertEqual(body["provider"], "groq")
        self.assertIsNone(body["error"])

    def test_admin_api_remains_protected_for_public_user(self):
        with patch.object(api_server, "requires_first_run_setup", return_value=False), patch.object(
            api_server,
            "_current_user",
            return_value=None,
        ):
            response = self.client.get("/api/admin/system-status")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["status"], "error")


if __name__ == "__main__":
    unittest.main()
