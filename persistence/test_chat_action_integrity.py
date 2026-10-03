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


    def test_history_marks_unverified_operational_claims(self):
        from persistence.chat_context import sanitize_historical_assistant_message

        false_claim = sanitize_historical_assistant_message(
            "assistant",
            "groq",
            "He recibido la corrección y la he registrado como un nuevo conocimiento candidato. ID de aprendizaje: learn_fake."
        )
        self.assertIn("RESPUESTA HISTORICA NO VERIFICABLE", false_claim)
        self.assertNotIn("learn_fake", false_claim)

        real_claim = sanitize_historical_assistant_message(
            "assistant",
            "learning_engine",
            "Lo registré como conocimiento candidato. ID de aprendizaje: learn_real."
        )
        self.assertIn("learn_real", real_claim)

    def test_github_readonly_gateway_rejects_untrusted_repo(self):
        from github_readonly import GitHubReadValidationError, read_repo_path

        with self.assertRaises(GitHubReadValidationError):
            read_repo_path("example/other-repo", "")

    def test_github_readonly_gateway_rejects_path_traversal(self):
        from github_readonly import GitHubReadValidationError, read_repo_path

        with self.assertRaises(GitHubReadValidationError):
            read_repo_path("AkiraGr2/akira-empresa", "../secret.txt")

if __name__ == "__main__":
    unittest.main()
