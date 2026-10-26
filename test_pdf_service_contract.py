"""
TEST PDF SERVICE CONTRACT
Verifies executive PDF generation in pure Python with zero dependencies.
"""

import unittest
import pdf_service

class TestPdfServiceContract(unittest.TestCase):
    def test_create_executive_pdf_valid_header(self):
        pdf_bytes = pdf_service.create_executive_pdf(
            title="Propuesta Comercial de Prueba",
            content="Resumen Ejecutivo:\nEsta es una prueba de generacion de documento.\n\nPresupuesto: $0.00 COP.",
            recipient="Jhon Grimm"
        )
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-1."))
        self.assertIn(b"%%EOF", pdf_bytes)
        self.assertGreater(len(pdf_bytes), 300)

if __name__ == "__main__":
    unittest.main()
