import unittest
import sandbox_service

class TestSandboxServiceContract(unittest.TestCase):
    def test_python_eval(self):
        res = sandbox_service.execute_python_sandbox("2 + 2 * 10")
        self.assertTrue(res["ok"])
        self.assertIn("22", res["output"])

    def test_python_exec_stdout(self):
        code = "for i in range(3): print(f'item {i}')"
        res = sandbox_service.execute_python_sandbox(code)
        self.assertTrue(res["ok"])
        self.assertIn("item 0", res["output"])
        self.assertIn("item 2", res["output"])

    def test_python_security_block(self):
        res = sandbox_service.execute_python_sandbox("import os; os.system('echo hi')")
        self.assertFalse(res["ok"])
        self.assertIn("restringida", res["error"])

    def test_audit_code(self):
        code = "def suma(a, b):\n    return a + b\n"
        report = sandbox_service.audit_code_content("math_utils.py", code)
        self.assertIn("AUDITORÍA EJECUTIVA", report)
        self.assertIn("Sintaxis Python válida", report)

    def test_simulate_negotiation(self):
        report = sandbox_service.simulate_negotiation("El cliente dice que está muy caro")
        self.assertIn("SIMULADOR DE NEGOCIACIÓN", report)
        self.assertIn("PIVOTE DE VALOR", report)

if __name__ == "__main__":
    unittest.main()
