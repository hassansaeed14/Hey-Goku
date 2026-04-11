import unittest
from unittest.mock import patch

import brain.response_engine as response_engine


class ResponseEngineTests(unittest.TestCase):
    def test_generate_response_payload_uses_degraded_reply_when_all_providers_fail(self):
        with patch.object(
            response_engine,
            "generate_with_best_provider",
            return_value={
                "success": False,
                "reason": "No healthy AI provider completed the request.",
                "attempts": [
                    {"provider": "gemini", "status": "unavailable", "reason": "Gemini unavailable"},
                    {"provider": "openai", "status": "rate_limited", "reason": "OpenAI rate limited"},
                    {"provider": "groq", "status": "auth_failed", "reason": "Groq auth failed"},
                ],
                "routing_order": ["gemini", "openai", "groq"],
            },
        ):
            payload = response_engine.generate_response_payload("What is wrong with my setup?")

        self.assertFalse(payload["success"])
        self.assertIn("live ai providers", payload["degraded_reply"].lower())
        self.assertIn("gemini", payload["degraded_reply"].lower())

    def test_generate_response_payload_strips_canned_filler_for_questions(self):
        with patch.object(
            response_engine,
            "generate_with_best_provider",
            return_value={
                "success": True,
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "text": "Certainly, sir. Quantum computing uses qubits.",
                "attempts": [],
                "routing_order": ["gemini", "openai", "groq"],
            },
        ):
            payload = response_engine.generate_response_payload("What is quantum computing?")

        self.assertTrue(payload["success"])
        self.assertEqual(payload["content"], "Quantum computing uses qubits.")

    def test_generate_response_payload_strips_stale_memory_filler_for_non_history_question(self):
        with patch.object(
            response_engine,
            "generate_with_best_provider",
            return_value={
                "success": True,
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "text": "We've discussed this before. Quantum computing uses qubits to represent probabilities.",
                "attempts": [],
                "routing_order": ["gemini", "openai", "groq"],
            },
        ):
            payload = response_engine.generate_response_payload("What is quantum computing?")

        self.assertTrue(payload["success"])
        self.assertEqual(payload["content"], "Quantum computing uses qubits to represent probabilities.")

    def test_generate_response_payload_strips_false_repeat_claims(self):
        with patch.object(
            response_engine,
            "generate_with_best_provider",
            return_value={
                "success": True,
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "text": "I've answered this question for you multiple times before. Elon Musk is a business magnate and entrepreneur.",
                "attempts": [],
                "routing_order": ["gemini", "openai", "groq"],
            },
        ):
            payload = response_engine.generate_response_payload("Who is Elon Musk?")

        self.assertTrue(payload["success"])
        self.assertEqual(payload["content"], "Elon Musk is a business magnate and entrepreneur.")

    def test_generate_response_payload_strips_recap_wrappers(self):
        with patch.object(
            response_engine,
            "generate_with_best_provider",
            return_value={
                "success": True,
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "text": "I've noticed that you've asked about stress multiple times before. To recap, some common strategies include deep breathing and a short walk.",
                "attempts": [],
                "routing_order": ["gemini", "openai", "groq"],
            },
        ):
            payload = response_engine.generate_response_payload("What should I do if I am feeling stressed?")

        self.assertTrue(payload["success"])
        self.assertEqual(payload["content"], "Some common strategies include deep breathing and a short walk.")

    def test_generate_response_payload_strips_repeat_claim_sentences(self):
        with patch.object(
            response_engine,
            "generate_with_best_provider",
            return_value={
                "success": True,
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "text": "You've asked this question before, multiple times. I'd be happy to explain it again. Quantum computing uses qubits and quantum effects to process information.",
                "attempts": [],
                "routing_order": ["gemini", "openai", "groq"],
            },
        ):
            payload = response_engine.generate_response_payload("What is quantum computing?")

        self.assertTrue(payload["success"])
        self.assertEqual(payload["content"], "Quantum computing uses qubits and quantum effects to process information.")

    def test_generate_response_payload_applies_cleanup_to_direct_requests(self):
        with patch.object(
            response_engine,
            "generate_with_best_provider",
            return_value={
                "success": True,
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "text": "It seems like you've asked this before. I'll provide the answer again. Here's a Python function:\ndef reverse_string(s):\n    return s[::-1]",
                "attempts": [],
                "routing_order": ["gemini", "openai", "groq"],
            },
        ):
            payload = response_engine.generate_response_payload("Write me a Python function to reverse a string")

        self.assertTrue(payload["success"])
        self.assertTrue(payload["content"].startswith("Here's a Python function:"))


if __name__ == "__main__":
    unittest.main()
