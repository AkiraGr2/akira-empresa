import unittest
from unittest.mock import patch, MagicMock
import io
from PIL import Image
import ocr_service

class TestOcrServiceContract(unittest.TestCase):
    def test_empty_bytes(self):
        res = ocr_service.analyze_document_image(b"")
        self.assertIn("No se recibieron", res)

    def test_fallback_with_valid_image(self):
        # Create a small valid image in memory
        img = Image.new("RGB", (100, 100), color="white")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        report = ocr_service.analyze_document_image(image_bytes, gemini_api_key=None)
        self.assertIn("LECTURA Y AUDITORÍA", report)
        self.assertIn("100x100 px", report)

    @patch("urllib.request.urlopen")
    def test_gemini_vision_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"candidates": [{"content": {"parts": [{"text": "Factura Exito: Total $50.000 COP"}]}}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        img = Image.new("RGB", (50, 50), color="white")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        report = ocr_service.analyze_document_image(image_bytes, gemini_api_key="fake_key")
        self.assertIn("Factura Exito", report)
        self.assertIn("Total $50.000 COP", report)

if __name__ == "__main__":
    unittest.main()
