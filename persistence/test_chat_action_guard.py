import unittest

from nexus import enforce_akira_identity_global


class ChatActionGuardTests(unittest.TestCase):
    def test_blocks_unsupported_learning_registration_claim(self):
        response = enforce_akira_identity_global(
            "He recibido la corrección y la he registrado como un nuevo conocimiento candidato. "
            "ID de aprendizaje: learn_correccion_20261003_01."
        )
        self.assertIn("No ejecuté ninguna acción persistente", response)
        self.assertNotIn("ID de aprendizaje:", response)

    def test_keeps_explicit_negative_claim(self):
        response = enforce_akira_identity_global(
            "No he registrado ningún aprendizaje todavía."
        )
        self.assertEqual(response, "No he registrado ningún aprendizaje todavía.")


if __name__ == "__main__":
    unittest.main()
