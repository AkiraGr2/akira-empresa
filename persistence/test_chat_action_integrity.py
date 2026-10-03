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

    def test_blocks_unsupported_learning_registration_claim(self):
        from nexus import enforce_akira_identity_global

        response = enforce_akira_identity_global(
            "He recibido la corrección y la he registrado como un nuevo conocimiento candidato. "
            "ID de aprendizaje: learn_correccion_20261003_01."
        )
        self.assertIn("No ejecuté ninguna acción persistente", response)
        self.assertNotIn("ID de aprendizaje:", response)

    def test_keeps_explicit_negative_claim(self):
        from nexus import enforce_akira_identity_global

        response = enforce_akira_identity_global(
            "No he registrado ningún aprendizaje todavía."
        )
        self.assertEqual(response, "No he registrado ningún aprendizaje todavía.")


if __name__ == "__main__":
    unittest.main()
