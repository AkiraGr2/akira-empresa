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
        from nexus import _format_conversation_context

        class Service:
            def list_messages(self, *args, **kwargs):
                return [
                    {
                        "role": "assistant",
                        "model": "groq",
                        "content": "He recibido la corrección y la he registrado como un nuevo conocimiento candidato. ID de aprendizaje: learn_fake."
                    },
                    {
                        "role": "assistant",
                        "model": "learning_engine",
                        "content": "Lo registré como conocimiento candidato. ID de aprendizaje: learn_real."
                    }
                ]

        context = _format_conversation_context(Service(), "conv_test", "mensaje actual")
        self.assertIn("RESPUESTA HISTORICA NO VERIFICABLE", context)
        self.assertIn("learn_real", context)
        self.assertNotIn("learn_fake", context)


if __name__ == "__main__":
    unittest.main()
