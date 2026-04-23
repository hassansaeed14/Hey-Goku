import unittest

from agents.registry import get_agent_summary, list_agents, validate_registry


class AgentRegistryTests(unittest.TestCase):
    def test_registry_entries_follow_capability_doctrine(self):
        self.assertEqual(validate_registry(), [])

    def test_agent_listing_exposes_capability_metadata(self):
        agent = list_agents()[0]
        self.assertIn("capability_mode", agent)
        self.assertEqual(agent["CAPABILITY_MODE"], agent["capability_mode"])
        self.assertIn("trust_level", agent)
        self.assertIn("integration_path", agent)
        self.assertIn("ui_claim", agent)

    def test_summary_tracks_capability_modes(self):
        summary = get_agent_summary()
        self.assertGreater(summary["capability_modes"]["real"], 0)
        self.assertGreater(summary["capability_modes"]["hybrid"], 0)
        self.assertGreater(summary["capability_modes"]["placeholder"], 0)
        self.assertEqual(summary["connected"], summary["total"] - summary["placeholders"])
        self.assertLess(summary["capability_modes"]["hybrid"], 80)

    def test_prompt_wrapper_agents_are_downgraded_to_placeholder(self):
        agents = {agent["id"]: agent for agent in list_agents()}

        for agent_id in (
            "reasoning",
            "study",
            "research",
            "code",
            "summarize",
            "assignment_writer_agent",
            "automation_designer_agent",
            "react_ui_agent",
        ):
            self.assertEqual(agents[agent_id]["capability_mode"], "placeholder")

        for agent_id in (
            "general",
            "insights",
            "task",
            "math",
            "web_search",
            "file",
            "model_router_agent",
        ):
            self.assertEqual(agents[agent_id]["capability_mode"], agents[agent_id]["CAPABILITY_MODE"])
            self.assertNotEqual(agents[agent_id]["capability_mode"], "placeholder")


if __name__ == "__main__":
    unittest.main()
