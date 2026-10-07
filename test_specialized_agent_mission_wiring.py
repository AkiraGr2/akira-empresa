import unittest

from nexus import _build_tool_inputs, _validate_mission_plan


class StubService:
    def list_agents(self, limit=200):
        return [
            {
                "name": "developer",
                "role": "developer",
                "status": "idle",
                "allowed_tools": ["github_repo_read", "developer_propose"],
            },
            {
                "name": "tester",
                "role": "tester",
                "status": "idle",
                "allowed_tools": ["github_repo_read", "python_test"],
            },
            {
                "name": "reviewer",
                "role": "reviewer",
                "status": "idle",
                "allowed_tools": ["github_repo_read", "python_test", "code_review"],
            },
            {
                "name": "autonomy_orchestrator",
                "role": "autonomy_orchestrator",
                "status": "idle",
                "allowed_tools": ["controlled_autonomy_start"],
            },
        ]

    def list_tools(self, limit=200):
        return [
            {"name": "github_repo_read", "status": "available"},
            {"name": "developer_propose", "status": "available"},
            {"name": "python_test", "status": "available"},
            {"name": "code_review", "status": "available"},
            {"name": "controlled_autonomy_start", "status": "available"},
        ]


class SpecializedAgentMissionWiringTests(unittest.TestCase):
    def test_specialized_plan_validates_with_two_review_dependencies(self):
        plan = {
            "steps": [
                {
                    "order": 1,
                    "task": "proponer un cambio pequeño",
                    "agent": "developer",
                    "tool": "developer_propose",
                    "repo": "AkiraGr2/akira-empresa",
                    "paths": ["README.md"],
                    "queries": [],
                    "expected_output": "propuesta de cambio verificable",
                    "receives_from": None,
                },
                {
                    "order": 2,
                    "task": "ejecutar las pruebas contractuales",
                    "agent": "tester",
                    "tool": "python_test",
                    "tests": ["test_specialized_agents_contract"],
                    "compile_paths": ["nexus.py"],
                    "expected_output": "resultado reproducible de pruebas",
                    "receives_from": None,
                },
                {
                    "order": 3,
                    "task": "revisar propuesta y evidencia",
                    "agent": "reviewer",
                    "tool": "code_review",
                    "repo": "AkiraGr2/akira-empresa",
                    "paths": ["README.md"],
                    "expected_output": "veredicto de revisión con hallazgos",
                    "receives_from": [1, 2],
                },
            ]
        }
        ok, reason = _validate_mission_plan(plan, StubService())
        self.assertTrue(ok, reason)

    def test_specialized_inputs_transport_proposal_and_test_evidence(self):
        step1 = {
            "order": 1,
            "task": "proponer un cambio pequeño",
            "expected_output": "propuesta de cambio verificable",
            "repo": "AkiraGr2/akira-empresa",
            "paths": ["README.md"],
            "queries": ["Akira"],
        }
        developer_inputs = _build_tool_inputs("developer_propose", step1, {}, "mission_test")
        self.assertEqual(developer_inputs["repo"], "AkiraGr2/akira-empresa")
        self.assertEqual(developer_inputs["paths"], ["README.md"])
        self.assertIn("proponer un cambio pequeño", developer_inputs["instruction"])

        step2 = {
            "order": 2,
            "task": "ejecutar pruebas",
            "expected_output": "resultado reproducible",
            "tests": ["test_specialized_agents_contract"],
            "compile_paths": ["nexus.py"],
        }
        tester_inputs = _build_tool_inputs("python_test", step2, {}, "mission_test")
        self.assertEqual(tester_inputs["tests"], ["test_specialized_agents_contract"])
        self.assertEqual(tester_inputs["compile_paths"], ["nexus.py"])

        step3 = {
            "order": 3,
            "task": "revisar",
            "expected_output": "veredicto",
            "repo": "AkiraGr2/akira-empresa",
            "paths": ["README.md"],
            "receives_from": [1, 2],
        }
        outputs = {
            1: {"proposal": {"status": "proposal", "changes": []}},
            2: {"status": "passed", "tests": []},
        }
        review_inputs = _build_tool_inputs("code_review", step3, outputs, "mission_test")
        self.assertEqual(review_inputs["repo"], "AkiraGr2/akira-empresa")
        self.assertEqual(review_inputs["proposal"]["status"], "proposal")
        self.assertEqual(review_inputs["test_results"]["status"], "passed")

    def test_controlled_autonomy_inputs_are_bounded_and_idempotent(self):
        step = {
            "order": 4,
            "task": "mejorar un archivo pequeño",
            "expected_output": "cambio probado y propuesto",
            "repo": "AkiraGr2/akira-empresa",
            "paths": ["README.md"],
            "queries": ["controlled autonomy"],
            "tests": ["test_controlled_autonomy_contract"],
        }
        inputs = _build_tool_inputs("controlled_autonomy_start", step, {}, "mission_test")
        self.assertEqual(inputs["repository"], "AkiraGr2/akira-empresa")
        self.assertEqual(inputs["base_branch"], "main")
        self.assertEqual(inputs["paths"], ["README.md"])
        self.assertEqual(inputs["idempotency_key"], "mission:mission_test:autonomy:4")
        self.assertEqual(inputs["tests"], ["test_controlled_autonomy_contract"])

    def test_controlled_autonomy_is_visible_to_planner(self):
        plan = {
            "steps": [{
                "order": 1,
                "task": "mejorar README de forma controlada",
                "agent": "autonomy_orchestrator",
                "tool": "controlled_autonomy_start",
                "repo": "AkiraGr2/akira-empresa",
                "paths": ["README.md"],
                "expected_output": "ejecucion detenida ante aprobacion humana",
                "receives_from": None,
            }]
        }
        ok, reason = _validate_mission_plan(plan, StubService())
        self.assertTrue(ok, reason)

    def test_review_cannot_use_one_dependency(self):
        plan = {
            "steps": [
                {
                    "order": 1,
                    "task": "propuesta",
                    "agent": "developer",
                    "tool": "developer_propose",
                    "repo": "AkiraGr2/akira-empresa",
                    "paths": ["README.md"],
                    "expected_output": "propuesta de cambio",
                    "receives_from": None,
                },
                {
                    "order": 2,
                    "task": "revision",
                    "agent": "reviewer",
                    "tool": "code_review",
                    "repo": "AkiraGr2/akira-empresa",
                    "paths": ["README.md"],
                    "expected_output": "veredicto de revisión",
                    "receives_from": [1],
                },
            ]
        }
        ok, reason = _validate_mission_plan(plan, StubService())
        self.assertFalse(ok)
        self.assertIn("review_requires_two_dependencies", reason)

    def test_review_dependencies_must_be_developer_then_tester(self):
        plan = {
            "steps": [
                {
                    "order": 1,
                    "task": "ejecutar pruebas",
                    "agent": "tester",
                    "tool": "python_test",
                    "tests": ["test_specialized_agents_contract"],
                    "expected_output": "resultado de pruebas reproducible",
                    "receives_from": None,
                },
                {
                    "order": 2,
                    "task": "propuesta",
                    "agent": "developer",
                    "tool": "developer_propose",
                    "repo": "AkiraGr2/akira-empresa",
                    "paths": ["README.md"],
                    "expected_output": "propuesta de cambio verificable",
                    "receives_from": None,
                },
                {
                    "order": 3,
                    "task": "revisar propuesta y pruebas",
                    "agent": "reviewer",
                    "tool": "code_review",
                    "repo": "AkiraGr2/akira-empresa",
                    "paths": ["README.md"],
                    "expected_output": "veredicto de revisión",
                    "receives_from": [1, 2],
                },
            ]
        }
        ok, reason = _validate_mission_plan(plan, StubService())
        self.assertFalse(ok)
        self.assertIn("review_first_dependency_must_be_developer", reason)


if __name__ == "__main__":
    unittest.main()