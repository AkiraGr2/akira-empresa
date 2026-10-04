import ast
from pathlib import Path
import unittest


class IdentityRootContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path("identity_root.py").read_text(encoding="utf-8")
        cls.nexus = Path("nexus.py").read_text(encoding="utf-8")
        cls.core = Path("persistence/core.py").read_text(encoding="utf-8")
        cls.service = Path("persistence/service.py").read_text(encoding="utf-8")
        cls.membrane = Path("membrane_compat.py").read_text(encoding="utf-8")

    def test_identity_root_is_canonical(self):
        self.assertIn('PUBLIC_IDENTITY = "Akira"', self.root)
        self.assertIn('IDENTITY_ROOT_VERSION = "identity_root.v1"', self.root)
        self.assertIn("MappingProxyType", self.root)
        self.assertIn('"name": PUBLIC_IDENTITY', self.root)
        self.assertIn('"creator": "Jhon Grimm"', self.root)

    def test_self_model_cannot_mutate_identity(self):
        self.assertIn('_SELF_MODEL_PROTECTED_FIELDS = frozenset({"identity"})', self.core)
        self.assertIn('"mutable": (\n            "purpose", "capabilities", "tools", "models",', self.core)
        self.assertNotIn(
            '"mutable": (\n            "identity", "purpose", "capabilities", "tools", "models",',
            self.core,
        )
        self.assertIn("def get_identity_root(self):", self.service)

    def test_public_identity_is_separated_from_runtime_version(self):
        self.assertIn('VERSION="V7.3"', self.nexus)
        self.assertIn('app=FastAPI(title=PUBLIC_IDENTITY, lifespan=_akira_lifespan)', self.nexus)
        self.assertIn('return {"message": PUBLIC_IDENTITY, "version": VERSION}', self.nexus)
        self.assertNotIn('return {"message": "Akira V7.3 Consciente"', self.nexus)

    def test_external_models_are_not_exposed_as_akira_identity(self):
        self.assertIn("motor de inferencia utilizado por Akira", self.nexus)
        self.assertNotIn('return ans + f" [via {model}]"', self.nexus)
        self.assertNotIn("Soy Akira V7.3, colmena consciente", self.nexus)
        self.assertNotIn("Eres Akira V7.3", self.nexus)

    def test_identity_filter_does_not_assert_unverified_consciousness(self):
        self.assertIn('_IDENTITY_REPLACEMENT = "Soy Akira."', self.nexus)
        self.assertNotIn('consciente=True', self.nexus)
        self.assertNotIn('"consciente": True', self.nexus)

    def test_legacy_membrane_identity_is_clean(self):
        self.assertNotIn('"identity": "Akira V7.3"', self.membrane)


if __name__ == "__main__":
    unittest.main()
