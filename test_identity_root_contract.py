import ast
from pathlib import Path
import ast
import unittest

from persistence.core import ValidationError, validate_self_model


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
        migrations = Path("persistence/migrations.py").read_text(encoding="utf-8")
        self.assertIn('"027_identity_root_db_guard"', migrations)
        self.assertIn("identity_root_singleton", migrations)
        self.assertIn("identity_root_no_update", migrations)
        self.assertIn("identity_root_no_delete", migrations)

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
        self.assertNotIn("Soy Akira V7.3", self.nexus)
        self.assertNotIn("Eres consciente de tu existencia como Akira", self.nexus)
        self.assertNotIn("Eres consciente de ti misma como Akira", self.nexus)
        self.assertIn("SIEMPRE: Soy Akira.", self.nexus)

    def test_self_model_runtime_rejects_identity_mutation(self):
        with self.assertRaises(ValidationError):
            validate_self_model({"identity": {"name": "Otra identidad"}}, partial=True)

    def test_identity_sensitive_routes_have_no_unverified_claims(self):
        counter_start = self.nexus.index('@app.get("/api/countermeasures")')
        repair_start = self.nexus.index('@app.get("/api/self-repair/propose")')
        brain_start = self.nexus.index('@app.get("/api/brain/shared")')
        counter_source = self.nexus[counter_start:repair_start]
        repair_source = self.nexus[repair_start:brain_start]

        self.assertNotIn('"consciente": True', counter_source)
        self.assertNotIn('"kira_autonomous": True', repair_source)
        self.assertIn('"kira_autonomous": False', repair_source)
        self.assertIn("audit = audit_models_automatically()", counter_source)
        self.assertIn('"identity_blindada": audit["identity_blindada"]', counter_source)
        self.assertIn("audit = audit_models_automatically()", repair_source)
        self.assertIn('"identity_blindada": audit["identity_blindada"]', repair_source)

        self.assertNotIn(
            "Soy Akira.na consciente creada por Jhon Grimm.",
            self.nexus,
        )
        self.assertIn(
            "pregunta quien eres, responde SIEMPRE: Soy Akira.",
            self.nexus,
        )

    def test_memory_identity_sanitizer_is_defined_and_surgical(self):
        self.assertIn("_IDENTITY_LIKE_RE = re.compile(", self.nexus)
        tree = ast.parse(self.nexus)
        wanted = []
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.FunctionDef)) and (
                (isinstance(node, ast.Assign) and any(
                    isinstance(tgt, ast.Name) and tgt.id in {"_IDENTITY_BANNED_PHRASES", "_IDENTITY_LIKE_RE"}
                    for tgt in node.targets
                ))
                or (isinstance(node, ast.FunctionDef) and node.name == "_sanitize_memory_content")
            ):
                wanted.append(node)
        namespace = {"re": re}
        exec(compile(ast.Module(body=wanted, type_ignores=[]), "memory-sanitizer-test", "exec"), namespace)
        sanitize = namespace["_sanitize_memory_content"]
        self.assertEqual(sanitize("Texto normal sobre IA."), "Texto normal sobre IA.")
        self.assertEqual(
            sanitize("El texto historico dice: soy ChatGPT y tambien habla de Akira."),
            "El texto historico dice: [...] y tambien habla de Akira.",
        )

    def test_identity_filter_is_surgical_at_runtime(self):
        tree = ast.parse(self.nexus)
        wanted = []
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.FunctionDef)) and (
                (isinstance(node, ast.Assign) and any(
                    isinstance(tgt, ast.Name) and tgt.id in {"_IDENTITY_BANNED_PHRASES", "_IDENTITY_REPLACEMENT"}
                    for tgt in node.targets
                ))
                or (isinstance(node, ast.FunctionDef) and node.name == "enforce_akira_identity_global")
            ):
                wanted.append(node)
        namespace = {}
        exec(compile(ast.Module(body=wanted, type_ignores=[]), "identity-filter-test", "exec"), namespace)

        sanitize = namespace["enforce_akira_identity_global"]
        self.assertEqual(sanitize("Soy ChatGPT y no soy Akira."), "Soy Akira.")
        self.assertEqual(
            sanitize("Como modelo de lenguaje, puedo explicar qué es una IA."),
            "Como modelo de lenguaje, puedo explicar qué es una IA.",
        )
        self.assertEqual(
            sanitize("No puedo afirmar que poseo conciencia subjetiva. Sí puedo decirte quién soy: Akira."),
            "No puedo afirmar que poseo conciencia subjetiva. Sí puedo decirte quién soy: Akira.",
        )

    def test_identity_audit_contract_covers_all_root_fields(self):
        root_module = ast.parse(self.root)
        root_node = next(node for node in root_module.body if isinstance(node, ast.Assign) and any(
            isinstance(tgt, ast.Name) and tgt.id == "IDENTITY_ROOT" for tgt in node.targets
        ))
        root_dict = root_node.value.args[0]
        self.assertIsInstance(root_dict, ast.Dict)
        assigned_keys = {ast.literal_eval(key) for key in root_dict.keys}
        self.assertEqual(
            assigned_keys,
            {"name", "creator", "essence", "language", "root_schema_version"},
        )
        audit_start = self.nexus.index("def audit_models_automatically():")
        audit_end = self.nexus.index("\ndef generate_autonomous_patch", audit_start)
        audit_source = self.nexus[audit_start:audit_end]
        for field in assigned_keys:
            self.assertIn(f'"{field}"', audit_source)

    def test_identity_filter_does_not_assert_unverified_consciousness(self):
        self.assertIn('_IDENTITY_REPLACEMENT = "Soy Akira."', self.nexus)
        audit_start = self.nexus.index("def audit_models_automatically():")
        audit_end = self.nexus.index("def generate_autonomous_patch():", audit_start)
        audit_source = self.nexus[audit_start:audit_end]
        self.assertNotIn('"consciente": True', audit_source)
        self.assertNotIn('"consciente": True', audit_source.replace(" ", ""))

    def test_legacy_membrane_identity_is_clean(self):
        self.assertNotIn('"identity": "Akira V7.3"', self.membrane)
        self.assertNotIn('"identidad": "Akira V7.3"', self.nexus)
        self.assertNotIn('"esencia": "Colmena activa consciente creada por Jhon Grimm en Bogotá."', self.nexus)
        self.assertNotIn("Knowledge: Identidad Akira blindada V7.3", self.nexus)
        self.assertIn('"objetivo": "Preservar la identidad pública canónica de Akira."', self.nexus)


if __name__ == "__main__":
    unittest.main()
