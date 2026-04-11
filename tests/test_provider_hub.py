import unittest
from types import SimpleNamespace
from unittest.mock import patch

import brain.provider_hub as provider_hub


def _fake_completion_result(text: str = "OK"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
    )


class ProviderHubTests(unittest.TestCase):
    def setUp(self):
        provider_hub.provider_hub._status_cache.clear()

    def test_provider_statuses_cover_major_backends(self):
        statuses = provider_hub.list_provider_statuses(fresh=False)
        provider_ids = {item["provider"] for item in statuses}
        self.assertTrue({"openai", "groq", "claude", "gemini", "ollama"}.issubset(provider_ids))

    def test_configured_provider_starts_as_unverified_not_healthy(self):
        with patch.object(provider_hub, "GEMINI_API_KEY", "demo-key"), patch.object(provider_hub, "genai", object()):
            status = provider_hub.get_provider_status("gemini", fresh=False)

        self.assertEqual(status.status, provider_hub.STATUS_CONFIGURED_UNVERIFIED)
        self.assertTrue(status.configured)
        self.assertFalse(status.available)

    def test_get_provider_status_preserves_last_verified_state_without_forcing_probe(self):
        cached = provider_hub.ProviderStatus(
            "gemini",
            "gemini-2.5-flash",
            "real",
            True,
            False,
            True,
            "Provider is rate limited.",
            status=provider_hub.STATUS_RATE_LIMITED,
            verified=True,
            last_checked_at=1.0,
        )
        provider_hub.provider_hub._status_cache["gemini"] = cached

        status = provider_hub.get_provider_status("gemini", fresh=False)

        self.assertEqual(status.status, provider_hub.STATUS_RATE_LIMITED)
        self.assertTrue(status.verified)

    def test_successful_groq_check_marks_provider_healthy(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kwargs: _fake_completion_result())
            )
        )

        with patch.object(provider_hub, "GROQ_API_KEY", "demo-key"), patch.object(provider_hub, "Groq", return_value=fake_client):
            result = provider_hub.provider_hub.check_groq(fresh=True)

        self.assertEqual(result["status"], provider_hub.STATUS_HEALTHY)
        self.assertIsNotNone(result["response_time_ms"])

    def test_extract_gemini_text_uses_candidate_parts_when_text_accessor_fails(self):
        class BrokenTextResponse:
            @property
            def text(self):
                raise ValueError("quick accessor failed")

        response = BrokenTextResponse()
        response.candidates = [
            SimpleNamespace(
                finish_reason=1,
                content=SimpleNamespace(parts=[SimpleNamespace(text="Gemini says hello")]),
            )
        ]

        text = provider_hub._extract_gemini_text(response)

        self.assertEqual(text, "Gemini says hello")

    def test_pick_provider_prefers_healthy_provider(self):
        fake_statuses = {
            "gemini": provider_hub.ProviderStatus("gemini", "gemini", "real", True, False, True, "not ready", status=provider_hub.STATUS_CONFIGURED_UNVERIFIED),
            "openai": provider_hub.ProviderStatus("openai", "gpt", "hybrid", False, False, True, "missing", status=provider_hub.STATUS_NOT_CONFIGURED),
            "groq": provider_hub.ProviderStatus("groq", "llama", "real", True, True, True, "healthy", status=provider_hub.STATUS_HEALTHY),
        }

        with patch.object(provider_hub, "get_provider_status", side_effect=lambda provider, fresh=False: fake_statuses.get(provider) or provider_hub.ProviderStatus(provider, "x", "hybrid", False, False, True, "missing", status=provider_hub.STATUS_NOT_CONFIGURED)):
            chosen = provider_hub.pick_provider(preferred="router")

        self.assertEqual(chosen, "groq")

    def test_generate_with_best_provider_uses_gemini_primary(self):
        statuses = {
            "gemini": provider_hub.ProviderStatus("gemini", "gemini-2.5-flash", "real", True, True, True, "healthy", status=provider_hub.STATUS_HEALTHY),
            "openai": provider_hub.ProviderStatus("openai", "gpt-4o-mini", "real", True, True, True, "healthy", status=provider_hub.STATUS_HEALTHY),
            "groq": provider_hub.ProviderStatus("groq", "llama-3.3-70b-versatile", "real", True, True, True, "healthy", status=provider_hub.STATUS_HEALTHY),
        }

        with patch.object(provider_hub, "get_provider_status", side_effect=lambda provider, fresh=False: statuses[provider]), patch.object(
            provider_hub.provider_hub,
            "generate_with_provider",
            side_effect=lambda provider, messages, max_tokens, temperature: {
                "success": True,
                "provider": provider,
                "model": statuses[provider].model,
                "text": f"{provider} says hello",
                "latency_ms": 12.0,
                "status": provider_hub.STATUS_HEALTHY,
            },
        ) as generate_mock:
            result = provider_hub.provider_hub.generate_with_best_provider(
                [{"role": "user", "content": "ping"}],
                max_tokens=10,
                temperature=0.0,
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "gemini")
        self.assertEqual(generate_mock.call_args.args[0], "gemini")

    def test_generate_with_best_provider_falls_back_to_openai(self):
        statuses = {
            "gemini": provider_hub.ProviderStatus("gemini", "gemini-2.5-flash", "real", True, False, True, "degraded", status=provider_hub.STATUS_DEGRADED),
            "openai": provider_hub.ProviderStatus("openai", "gpt-4o-mini", "real", True, True, True, "healthy", status=provider_hub.STATUS_HEALTHY),
            "groq": provider_hub.ProviderStatus("groq", "llama-3.3-70b-versatile", "real", True, True, True, "healthy", status=provider_hub.STATUS_HEALTHY),
        }

        def fake_generate(provider, messages, max_tokens, temperature):
            if provider == "gemini":
                raise provider_hub.ProviderExecutionError("gemini", status=provider_hub.STATUS_UNAVAILABLE, error="Gemini unavailable")
            return {
                "success": True,
                "provider": provider,
                "model": statuses[provider].model,
                "text": f"{provider} says hello",
                "latency_ms": 12.0,
                "status": provider_hub.STATUS_HEALTHY,
            }

        with patch.object(provider_hub, "get_provider_status", side_effect=lambda provider, fresh=False: statuses[provider]), patch.object(
            provider_hub.provider_hub,
            "generate_with_provider",
            side_effect=fake_generate,
        ):
            result = provider_hub.provider_hub.generate_with_best_provider(
                [{"role": "user", "content": "ping"}],
                max_tokens=10,
                temperature=0.0,
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "openai")
        self.assertEqual(result["attempts"][0]["provider"], "gemini")
        self.assertEqual(result["attempts"][0]["status"], provider_hub.STATUS_UNAVAILABLE)

    def test_generate_with_best_provider_falls_back_to_groq(self):
        statuses = {
            "gemini": provider_hub.ProviderStatus("gemini", "gemini-2.5-flash", "real", True, False, True, "degraded", status=provider_hub.STATUS_DEGRADED),
            "openai": provider_hub.ProviderStatus("openai", "gpt-4o-mini", "real", True, False, True, "rate limited", status=provider_hub.STATUS_RATE_LIMITED),
            "groq": provider_hub.ProviderStatus("groq", "llama-3.3-70b-versatile", "real", True, True, True, "healthy", status=provider_hub.STATUS_HEALTHY),
        }

        def fake_generate(provider, messages, max_tokens, temperature):
            if provider == "gemini":
                raise provider_hub.ProviderExecutionError("gemini", status=provider_hub.STATUS_UNAVAILABLE, error="Gemini unavailable")
            if provider == "groq":
                return {
                    "success": True,
                    "provider": "groq",
                    "model": statuses["groq"].model,
                    "text": "groq says hello",
                    "latency_ms": 12.0,
                    "status": provider_hub.STATUS_HEALTHY,
                }
            raise AssertionError("OpenAI should be skipped while rate limited")

        with patch.object(provider_hub, "get_provider_status", side_effect=lambda provider, fresh=False: statuses[provider]), patch.object(
            provider_hub.provider_hub,
            "generate_with_provider",
            side_effect=fake_generate,
        ):
            result = provider_hub.provider_hub.generate_with_best_provider(
                [{"role": "user", "content": "ping"}],
                max_tokens=10,
                temperature=0.0,
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "groq")
        self.assertEqual(result["attempts"][0]["provider"], "gemini")
        self.assertEqual(result["attempts"][1]["provider"], "openai")
        self.assertEqual(result["attempts"][1]["status"], provider_hub.STATUS_RATE_LIMITED)

    def test_runtime_provider_summary_explains_fallback_route(self):
        statuses = {
            "gemini": provider_hub.ProviderStatus("gemini", "gemini-2.5-flash", "real", True, False, True, "rate limited", status=provider_hub.STATUS_RATE_LIMITED),
            "openai": provider_hub.ProviderStatus("openai", "gpt-4o-mini", "real", True, False, True, "rate limited", status=provider_hub.STATUS_RATE_LIMITED),
            "groq": provider_hub.ProviderStatus("groq", "llama-3.3-70b-versatile", "real", True, True, True, "healthy", status=provider_hub.STATUS_HEALTHY, last_used_at=10.0),
        }

        with patch.object(provider_hub, "get_provider_status", side_effect=lambda provider, fresh=False: statuses.get(provider) or provider_hub.ProviderStatus(provider, "x", "hybrid", False, False, True, "missing", status=provider_hub.STATUS_NOT_CONFIGURED)):
            summary = provider_hub.get_runtime_provider_summary(preferred="gemini", fresh=False)

        self.assertEqual(summary["status"], provider_hub.STATUS_DEGRADED)
        self.assertEqual(summary["preferred_provider"], "gemini")
        self.assertEqual(summary["active_provider"], "groq")
        self.assertIn("routing through GROQ", summary["message"])


if __name__ == "__main__":
    unittest.main()
