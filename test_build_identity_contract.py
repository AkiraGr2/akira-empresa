import unittest
from pathlib import Path

from persistence.build_identity import _is_runtime_source


class BuildIdentityContractTests(unittest.TestCase):
    def test_excludes_test_modules_at_repository_and_package_levels(self):
        for path in (
            Path("test_cognitive_runtime_execution.py"),
            Path("test_build_identity_contract.py"),
            Path("persistence/test_capability_contract.py"),
            Path("tests/test_runtime.py"),
            Path("conftest.py"),
        ):
            with self.subTest(path=str(path)):
                self.assertFalse(_is_runtime_source(path))

    def test_includes_runtime_modules_and_dependencies(self):
        for path in (
            Path("nexus.py"),
            Path("persistence/build_identity.py"),
            Path("persistence/autonomy.py"),
            Path("requirements.txt"),
        ):
            with self.subTest(path=str(path)):
                self.assertTrue(_is_runtime_source(path))

    def test_excludes_non_python_build_configuration(self):
        self.assertFalse(_is_runtime_source(Path(".github/workflows/backend-syntax.yml")))
        self.assertFalse(_is_runtime_source(Path("README.md")))


if __name__ == "__main__":
    unittest.main()
