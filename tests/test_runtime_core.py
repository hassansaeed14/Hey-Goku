import unittest
from unittest.mock import patch

import brain.runtime_core as runtime_core


class RuntimeCoreTests(unittest.TestCase):
    def test_special_intent_returns_structured_metadata(self):
        orchestration = {
            "primary_agent": "time",
            "secondary_agents": [],
            "execution_order": ["time"],
            "requires_multiple": False,
            "primary_selection_source": "intent",
            "top_score": 0,
            "mode": "real",
        }

        with patch.object(runtime_core, "detect_language", return_value="english"), patch.object(
            runtime_core,
            "detect_intent_with_confidence",
            return_value=("time", 0.92),
        ), patch.object(
            runtime_core.master_orchestrator,
            "analyze_task",
            return_value=orchestration,
        ), patch.object(
            runtime_core,
            "build_permission_response",
            return_value={"success": True, "permission": {"reason": ""}},
        ), patch.object(
            runtime_core,
            "respond_in_language",
            side_effect=lambda response, language: response,
        ), patch.object(runtime_core, "store_and_learn"):
            result = runtime_core.process_single_command_detailed("what time is it")

        self.assertEqual(result["intent"], "time")
        self.assertEqual(result["detected_intent"], "time")
        self.assertEqual(result["used_agents"], ["time"])
        self.assertEqual(result["execution_mode"], "special_intent")
        self.assertEqual(result["plan"], [])
        self.assertIn("current time", result["response"].lower())

    def test_keyword_orchestration_runs_multi_agent_workflow(self):
        orchestration = {
            "primary_agent": "research",
            "secondary_agents": ["summarize"],
            "execution_order": ["research", "summarize"],
            "requires_multiple": True,
            "primary_selection_source": "keyword_scoring",
            "top_score": 1,
            "mode": "real",
        }

        with patch.object(runtime_core, "detect_language", return_value="english"), patch.object(
            runtime_core,
            "detect_intent_with_confidence",
            return_value=("general", 0.30),
        ), patch.object(
            runtime_core.master_orchestrator,
            "analyze_task",
            return_value=orchestration,
        ), patch.object(
            runtime_core.master_orchestrator,
            "synthesize_responses",
            return_value={"response": "Synthesized research summary"},
        ), patch.object(
            runtime_core,
            "build_permission_response",
            return_value={"success": True, "permission": {"reason": ""}},
        ), patch.object(
            runtime_core,
            "research",
            return_value="Research result",
        ), patch.object(
            runtime_core,
            "summarize_text",
            return_value="Summary result",
        ), patch.object(
            runtime_core,
            "generate_response_payload",
            side_effect=AssertionError("LLM fallback should not run for orchestrated research workflow."),
        ), patch.object(
            runtime_core,
            "respond_in_language",
            side_effect=lambda response, language: response,
        ), patch.object(runtime_core, "store_and_learn"):
            result = runtime_core.process_single_command_detailed("research and summarize AI agents")

        self.assertEqual(result["intent"], "research")
        self.assertEqual(result["used_agents"], ["research", "summarize"])
        self.assertEqual(result["execution_mode"], "multi_agent")
        self.assertEqual(result["response"], "Synthesized research summary")
        self.assertTrue(result["plan"])
        self.assertEqual(result["orchestration"]["execution_order"], ["research", "summarize"])

    def test_task_add_request_uses_action_specific_permission(self):
        orchestration = {
            "primary_agent": "task",
            "secondary_agents": [],
            "execution_order": ["task"],
            "requires_multiple": False,
            "primary_selection_source": "intent",
            "top_score": 3,
            "mode": "real",
        }

        with patch.object(runtime_core, "detect_language", return_value="english"), patch.object(
            runtime_core,
            "detect_intent_with_confidence",
            return_value=("task", 0.94),
        ), patch.object(
            runtime_core.master_orchestrator,
            "analyze_task",
            return_value=orchestration,
        ), patch.object(
            runtime_core,
            "build_permission_response",
            side_effect=lambda action_name, **kwargs: {
                "success": True,
                "status": "approved",
                "permission": {"action_name": action_name, "reason": ""},
            },
        ) as permission_mock, patch.dict(
            runtime_core.AGENT_ROUTER,
            {"task": lambda cmd: "Task added"},
            clear=False,
        ), patch.object(
            runtime_core,
            "respond_in_language",
            side_effect=lambda response, language: response,
        ), patch.object(runtime_core, "store_and_learn"):
            result = runtime_core.process_single_command_detailed("add task buy milk")

        self.assertEqual(permission_mock.call_args.args[0], "task_add")
        self.assertEqual(result["permission_action"], "task_add")
        self.assertEqual(result["used_agents"], ["task"])
        self.assertEqual(result["agent_capabilities"][0]["id"], "task")
        self.assertEqual(result["execution_mode"], "single_agent")

    def test_provider_failure_returns_degraded_assistant_reply(self):
        orchestration = {
            "primary_agent": "general",
            "secondary_agents": [],
            "execution_order": [],
            "requires_multiple": False,
            "primary_selection_source": "intent",
            "top_score": 0,
            "mode": "real",
        }

        with patch.object(runtime_core, "detect_language", return_value="english"), patch.object(
            runtime_core,
            "detect_intent_with_confidence",
            return_value=("general", 0.88),
        ), patch.object(
            runtime_core.master_orchestrator,
            "analyze_task",
            return_value=orchestration,
        ), patch.object(
            runtime_core,
            "build_permission_response",
            return_value={"success": True, "permission": {"reason": ""}},
        ), patch.object(
            runtime_core,
            "generate_response_payload",
            return_value={
                "success": False,
                "error": "No healthy AI provider completed the request.",
                "providers_tried": [
                    {"provider": "gemini", "status": "unavailable", "reason": "Gemini unavailable"},
                    {"provider": "openai", "status": "rate_limited", "reason": "OpenAI rate limited"},
                ],
                "degraded_reply": "I can see the request, but I can't answer it reliably right now because my live AI providers aren't completing the request path.",
            },
        ), patch.object(
            runtime_core,
            "respond_in_language",
            side_effect=lambda response, language: response,
        ), patch.object(runtime_core, "store_and_learn"):
            result = runtime_core.process_single_command_detailed("what is quantum computing")

        self.assertEqual(result["execution_mode"], "degraded_assistant")
        self.assertTrue(result["degraded"])
        self.assertIsNone(result["provider"])
        self.assertIn("can't answer it reliably", result["response"].lower())


if __name__ == "__main__":
    unittest.main()
