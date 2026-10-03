import unittest


class ChatActionIntegrityGuardTests(unittest.TestCase):
    def test_common_rule_is_present_in_all_chat_provider_paths(self):
        with open("nexus.py", "r", encoding="utf-8") as handle:
            text = handle.read()

        self.assertIn("CHAT_ACTION_INTEGRITY_RULE", text)
        self.assertGreaterEqual(
            text.count("{CHAT_ACTION_INTEGRITY_RULE}"),
            4,
            "Gemini normal, Gemini stream, Groq and OpenRouter must all receive the rule",
        )

    def test_rule_distinguishes_shadow_from_executed_actions(self):
        with open("nexus.py", "r", encoding="utf-8") as handle:
            text = handle.read()

        self.assertIn("El modo shadow solo observa y NO ejecuta", text)
        self.assertIn("no inventes\nIDs, estados ni resultados de persistencia.", text)


if __name__ == "__main__":
    unittest.main()
