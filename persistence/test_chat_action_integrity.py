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

    def test_2d_brain_inspection_uses_only_direct_renderer_evidence(self):
        with open("nexus.py", "r", encoding="utf-8") as handle:
            text = handle.read()

        start = text.index("def _detect_github_read_request")
        end = text.index("def check_security", start)
        detector = text[start:end]
        self.assertIn('paths.append("js/obsidian_membrane.js")', detector)
        self.assertNotIn('paths.extend(["js/obsidian_membrane.js", "index.html"])', detector)
        self.assertIn('"cyMembrane.on"', detector)
        self.assertIn('"_updateMembraneContextPanel"', detector)

    def test_github_evidence_policy_excludes_prior_chat_claims(self):
        with open("nexus.py", "r", encoding="utf-8") as handle:
            text = handle.read()
        self.assertGreaterEqual(text.count("prior chat text is not evidence"), 2)

    def test_2d_brain_inspection_targets_renderer_and_panel_not_chat_client(self):
        with open("nexus.py", "r", encoding="utf-8") as handle:
            text = handle.read()

        start = text.index("def _detect_github_read_request")
        end = text.index("def check_security", start)
        detector = text[start:end]
        self.assertIn('paths.append("js/obsidian_membrane.js")', detector)
        self.assertNotIn('"js/akira_brain.js", "js/obsidian_membrane.js"', detector)
        self.assertNotIn('paths.append("index.html")', detector)
        self.assertIn('"cyMembrane.on"', detector)
        self.assertIn('"_updateMembraneContextPanel"', detector)

    def test_stream_chat_has_github_readonly_evidence_path(self):
        with open("nexus.py", "r", encoding="utf-8") as handle:
            text = handle.read()

        stream_start = text.index('@app.post("/api/chat/stream")')
        stream_body = text[stream_start:]
        self.assertIn('github_read = _detect_github_read_request(msg)', stream_body)
        self.assertIn('service, "github_repo_read", github_read', stream_body)
        self.assertIn("[GitHub READ-ONLY EVIDENCE — SERVER RESULT]", stream_body)
        self.assertIn('conversation_context = (conversation_context + github_context)[:52000]', stream_body)

    def test_oversized_file_returns_targeted_evidence_instead_of_failing(self):
        import base64
        from unittest.mock import patch
        from github_readonly import inspect_repository

        source = "// tap\n" + ("x" * 50000) + "\nfunction openBrainContext(nodeId) {}\n" + ("y" * 50000)
        fake_root = [
            {"name": "js", "path": "js", "type": "dir", "size": 0},
        ]
        fake_file = {
            "type": "file",
            "name": "obsidian_membrane.js",
            "path": "js/obsidian_membrane.js",
            "size": len(source.encode("utf-8")),
            "content": base64.b64encode(source.encode("utf-8")).decode("ascii"),
        }

        def fake_get(url):
            if url.endswith("/contents?ref=main"):
                return fake_root
            return fake_file

        with patch("github_readonly._get_json", side_effect=fake_get):
            result = inspect_repository(
                "AkiraGr2/akira-v3-frontend",
                paths=["js/obsidian_membrane.js"],
                queries=["tap", "brainContext"],
                max_files=8,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["files"][0]["status"], "ok")
        self.assertEqual(result["files"][0]["mode"], "targeted_snippets")
        self.assertGreaterEqual(len(result["files"][0]["matches"]), 1)
        snippets = " ".join(m["snippet"] for m in result["files"][0]["matches"])
        self.assertIn("openBrainContext", snippets)

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
