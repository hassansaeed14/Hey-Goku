import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import api.api_server as api_server


class ApiProviderStatusTests(unittest.TestCase):
    def setUp(self):
        api_server.PROVIDER_HEALTH_CACHE.update(
            {
                "checked_at_ts": 0.0,
                "checked_at": 0.0,
                "items": [],
                "providers": {},
            }
        )
        self.client = TestClient(api_server.app)

    def test_provider_endpoint_returns_truthful_status_payload(self):
        provider_summary = {
            "default_provider": "gemini",
            "routing_order": ["gemini", "openai", "groq"],
            "healthy": ["gemini"],
            "configured": ["gemini", "groq"],
            "verified": ["gemini"],
            "items": [
                {
                    "provider": "gemini",
                    "model": "gemini-2.5-flash",
                    "status": "healthy",
                    "reason": "Live health check passed.",
                    "configured": True,
                    "installed": True,
                    "response_time_ms": 120.0,
                },
                {
                    "provider": "groq",
                    "model": "llama-3.3-70b-versatile",
                    "status": "configured_unverified",
                    "reason": "Provider is configured but has not passed a live check yet.",
                    "configured": True,
                    "installed": True,
                    "response_time_ms": None,
                },
            ],
            "providers": {"gemini": "healthy", "groq": "configured_unverified"},
        }

        with patch.object(api_server, "_current_user", return_value={"id": "owner", "username": "owner", "admin": True}), patch.object(
            api_server,
            "requires_first_run_setup",
            return_value=False,
        ), patch.object(
            api_server,
            "summarize_provider_statuses",
            return_value=provider_summary,
        ):
            response = self.client.get("/api/providers")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["providers"]["gemini"], "healthy")
        self.assertEqual(payload["providers"]["groq"], "configured_unverified")
        self.assertEqual(payload["routing_order"], ["gemini", "openai", "groq"])

    def test_system_health_uses_provider_truth_model(self):
        provider_snapshot = {
            "items": [
                {"provider": "gemini", "status": "healthy"},
                {"provider": "groq", "status": "configured_unverified"},
            ],
            "providers": {"gemini": "healthy", "groq": "configured_unverified"},
            "routing_order": ["gemini", "openai", "groq"],
        }

        with patch.object(api_server, "_provider_health_snapshot", return_value=provider_snapshot), patch.object(
            api_server,
            "get_voice_status",
            return_value={"stt": {"available": False}, "tts": {"available": True}},
        ), patch.object(
            api_server,
            "_chat_requests_today",
            return_value=3,
        ):
            payload = api_server._system_health_payload()

        self.assertEqual(payload["brain"], "working")
        self.assertEqual(payload["providers"]["gemini"], "healthy")
        self.assertEqual(payload["routing_order"], ["gemini", "openai", "groq"])


if __name__ == "__main__":
    unittest.main()
