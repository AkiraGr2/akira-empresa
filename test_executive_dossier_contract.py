import unittest
import os
import tempfile
import shutil
import base64
from executive_dossier import (
    build_dossier_text,
    compile_executive_dossier,
    generate_and_dispatch_dossier,
)

class TestExecutiveDossierContract(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_build_dossier_text(self):
        sections = {
            "resumen_ejecutivo": "Hallazgos principales del análisis.",
            "vulnerabilidades_detectadas": [
                {"paquete": "requests", "version": "2.28.1", "cve": "CVE-2023-32681"},
            ],
            "recomendaciones": ["Actualizar dependencias a la brevedad."]
        }
        text = build_dossier_text("Auditoría de Seguridad", sections, metadata={"Auditor": "Akira"})
        self.assertIn("INFORME ESTRATÉGICO EJECUTIVO", text)
        self.assertIn("Resumen Ejecutivo", text)
        self.assertIn("CVE-2023-32681", text)
        self.assertIn("Auditor: Akira", text)

    def test_compile_executive_dossier(self):
        title = "Investigación JIT Python 3.13"
        content = "Detalle del compilador experimental JIT incorporado en la rama 3.13."
        res = compile_executive_dossier(
            title=title,
            content_or_sections=content,
            recipient="Director Jhon Grimm",
            output_dir=self.test_dir,
            save_to_disk=True,
            include_base64=True
        )
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["size_bytes"] > 200)
        self.assertTrue(len(res["sha256"]) == 64)
        self.assertIsNotNone(res["file_path"])
        self.assertTrue(os.path.exists(res["file_path"]))

        # Verify PDF header
        with open(res["file_path"], "rb") as f:
            header = f.read(5)
            self.assertEqual(header, b"%PDF-")

        # Verify base64 output
        decoded = base64.b64decode(res["pdf_base64"])
        self.assertTrue(decoded.startswith(b"%PDF-"))

    def test_generate_and_dispatch_resilience(self):
        # Should complete compilation and gracefully handle missing/invalid telegram config
        res = generate_and_dispatch_dossier(
            title="Prueba de Resiliencia",
            content_or_sections={"resumen": "Prueba"},
            send_telegram=True, # Will fail gracefully without throwing
            chat_id="000000"
        )
        self.assertEqual(res["status"], "success")
        self.assertIn("sent_to_telegram", res)

if __name__ == "__main__":
    unittest.main()
