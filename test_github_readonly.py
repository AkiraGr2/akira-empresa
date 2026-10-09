import base64
import unittest
from unittest.mock import patch

from github_readonly import (
    GitHubReadValidationError,
    inspect_repository,
    read_repo_path,
)


class GitHubReadonlyGatewayTests(unittest.TestCase):
    def test_rejects_non_allowlisted_repository(self):
        with self.assertRaises(GitHubReadValidationError):
            read_repo_path("evil.example/repo", "")

    def test_rejects_parent_path_traversal(self):
        with self.assertRaises(GitHubReadValidationError):
            read_repo_path("AkiraGr2/akira-empresa", "../secret.txt")

    def test_reads_file_without_writes(self):
        encoded = base64.b64encode(b"print('ok')").decode("ascii")
        fake_file = {
            "type": "file",
            "name": "example.py",
            "path": "example.py",
            "size": 11,
            "content": encoded,
        }
        with patch("github_readonly._get_json", return_value=fake_file) as mocked:
            result = read_repo_path("AkiraGr2/akira-empresa", "example.py")
        self.assertTrue(result["ok"])
        self.assertTrue(result["operation"], "read_file")
        self.assertEqual(result["content"], "print('ok')")
        mocked.assert_called_once()

    def test_inspection_is_read_only_and_bounded(self):
        root = [
            {"name": "nexus.py", "path": "nexus.py", "type": "file", "size": 100},
            {"name": "persistence", "path": "persistence", "type": "dir", "size": 0},
        ]
        file_data = {
            "type": "file",
            "name": "nexus.py",
            "path": "nexus.py",
            "size": 12,
            "content": base64.b64encode(b"VERSION='test'").decode("ascii"),
        }

        def fake_get(url):
            if url.endswith("/git/ref/heads/main"):
                return {"object": {"sha": "a" * 40}}
            if url.endswith("/contents?ref=main"):
                return root
            return file_data

        with patch("github_readonly._get_json", side_effect=fake_get):
            result = inspect_repository(
                "AkiraGr2/akira-empresa",
                paths=["nexus.py"],
                max_files=8,
            )

        self.assertTrue(result["ok"])
        self.assertTrue(result["read_only"])
        self.assertEqual(result["branch"], "main")
        self.assertEqual(len(result["files"]), 1)
        self.assertEqual(result["files"][0]["status"], "ok")
        self.assertLessEqual(
            result["total_bytes"],
            result["limits"]["max_total_bytes"],
        )


    def test_reads_moderately_oversized_source_as_full_file_within_total_budget(self):
        path = "test_controlled_autonomy_contract.py"
        source = "x" * 45_000
        fake_file = {
            "type": "file",
            "name": path,
            "path": path,
            "size": len(source.encode("utf-8")),
            "content": base64.b64encode(source.encode("utf-8")).decode("ascii"),
        }
        root = [{"name": path, "path": path, "type": "file", "size": len(source)}]

        def fake_get(url):
            if url.endswith("/git/ref/heads/main"):
                return {"object": {"sha": "a" * 40}}
            if url.endswith("/contents?ref=main"):
                return root
            if url.endswith(f"/contents/{path}?ref=main"):
                return fake_file
            raise AssertionError(f"Unexpected GitHub URL: {url}")

        with patch("github_readonly._get_json", side_effect=fake_get):
            result = inspect_repository(
                "AkiraGr2/akira-empresa",
                paths=[path],
                max_files=1,
            )

        self.assertTrue(result["read_only"])
        self.assertEqual(result["files"][0]["status"], "ok")
        self.assertEqual(result["files"][0]["mode"], "full_file")
        self.assertEqual(result["files"][0]["content"], source)
        self.assertEqual(result["total_bytes"], len(source.encode("utf-8")))
        self.assertLessEqual(result["total_bytes"], result["limits"]["max_total_bytes"])


if __name__ == "__main__":
    unittest.main()
