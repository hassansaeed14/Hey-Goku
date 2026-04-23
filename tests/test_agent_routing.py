import unittest
from unittest.mock import patch

from agents.agent_fabric import AgentBlueprint, match_generated_agent_request
from agents.registry import filter_chat_routable_agents, get_agent_capability_mode
import brain.runtime_core as runtime_core


class AgentRoutingTruthTests(unittest.TestCase):
    def test_generated_prompt_wrapper_categories_default_to_placeholder(self):
        placeholder_blueprint = AgentBlueprint(
            id="mock_generated_agent",
            module_name="mock_generated_agent",
            name="Mock Generated Agent",
            category="advanced",
            description="Planned generated agent.",
            capability_mode="placeholder",
            trust_level="safe",
            backend="planned",
            integration_path="Connect this generated agent before enabling live routing.",
            keywords=("mock generated", "analysis helper"),
            status="live",
            icon="ADV",
            stateful=False,
        )

        with patch(
            "agents.agent_fabric.discover_generated_agent_blueprints",
            return_value=[placeholder_blueprint],
        ), patch("builtins.print") as print_mock:
            match = match_generated_agent_request("use the mock generated analysis helper")

        self.assertIsNone(match)
        print_mock.assert_any_call("[AGENT ROUTING] blocked placeholder agent: mock_generated_agent")

    def test_registry_filters_placeholder_agents_from_chat_routing(self):
        allowed, blocked = filter_chat_routable_agents(["permission", "cognitive", "study"])

        self.assertEqual(allowed, ["permission"])
        self.assertEqual(blocked, ["cognitive", "study"])
        self.assertEqual(get_agent_capability_mode("cognitive"), "placeholder")
        self.assertEqual(get_agent_capability_mode("permission"), "real")

    def test_generated_placeholder_agent_is_not_auto_matched(self):
        placeholder_blueprint = AgentBlueprint(
            id="mock_placeholder_agent",
            module_name="mock_placeholder_agent",
            name="Mock Placeholder Agent",
            category="documents",
            description="Planned placeholder agent.",
            capability_mode="placeholder",
            trust_level="safe",
            backend="planned",
            integration_path="Connect this planned agent before enabling it.",
            keywords=("mock placeholder", "document helper"),
            status="experimental",
            icon="DOC",
            stateful=False,
        )

        with patch(
            "agents.agent_fabric.discover_generated_agent_blueprints",
            return_value=[placeholder_blueprint],
        ), patch("builtins.print") as print_mock:
            match = match_generated_agent_request("use the mock placeholder document helper")

        self.assertIsNone(match)
        print_mock.assert_any_call("[AGENT ROUTING] blocked placeholder agent: mock_placeholder_agent")

    def test_runtime_blocks_placeholder_primary_agent_and_falls_back(self):
        orchestration = {
            "primary_agent": "cognitive",
            "secondary_agents": [],
            "execution_order": ["cognitive"],
            "requires_multiple": False,
            "primary_selection_source": "intent",
            "top_score": 3,
            "mode": "real",
            "reason": "placeholder route should be blocked",
        }

        with patch.object(runtime_core, "detect_language", return_value="english"), patch.object(
            runtime_core,
            "detect_intent_with_confidence",
            return_value=("general", 0.82),
        ), patch.object(
            runtime_core.master_orchestrator,
            "analyze_task",
            return_value=orchestration,
        ), patch.object(
            runtime_core,
            "_enforce_runtime_permission",
            return_value={"success": True, "status": "approved", "permission": {"trust_level": "safe", "reason": ""}},
        ), patch.object(
            runtime_core,
            "_llm_response_with_provider",
            return_value={
                "success": True,
                "text": "I can help with that through the general assistant path.",
                "provider_name": "groq",
                "model": "llama-3.3-70b-versatile",
                "providers_tried": ["groq"],
                "tokens_used": 32,
                "time_ms": 18.0,
            },
        ), patch.object(
            runtime_core,
            "respond_in_language",
            side_effect=lambda response, language: response,
        ), patch.object(
            runtime_core,
            "store_and_learn",
        ), patch("builtins.print") as print_mock:
            result = runtime_core.process_single_command_detailed("plan a cognitive pipeline")

        self.assertEqual(result["execution_mode"], "fallback_llm")
        self.assertEqual(result["orchestration"]["primary_agent"], "general")
        self.assertIn("cognitive", result["orchestration"].get("blocked_placeholders", []))
        self.assertEqual(result["used_agents"], [])
        self.assertIn("general assistant path", result["response"].lower())
        print_mock.assert_any_call("[AGENT ROUTING] blocked placeholder agent: cognitive")


if __name__ == "__main__":
    unittest.main()
