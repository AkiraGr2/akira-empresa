"""
TEST EXECUTIVE SERVICE CONTRACT
Verifies the daily briefing, sentinel, deliverable, upwork sentinel, and PDF generation logic at zero cost.
"""

import unittest
from unittest.mock import patch, MagicMock
import executive_service

class TestExecutiveServiceContract(unittest.TestCase):
    @patch("web_engine.search_web")
    def test_generate_executive_briefing(self, mock_search):
        mock_search.return_value = {
            "ok": True,
            "results": [
                {"title": "Noticia 1", "snippet": "Detalle 1", "link": "https://example.com/1"},
                {"title": "Noticia 2", "snippet": "Detalle 2", "link": "https://example.com/2"},
            ]
        }
        res = executive_service.generate_executive_briefing()
        self.assertTrue(res["ok"])
        self.assertIn("Briefing Ejecutivo Diario", res["briefing_markdown"])
        self.assertIn("$0.00 COP", res["briefing_markdown"])
        self.assertIn("Noticia 1", res["voice_text"])
        self.assertEqual(res["system_status"]["capabilities_active"], 41)

    @patch("web_engine.search_web")
    @patch("telegram_service.send_telegram_message")
    def test_run_opportunity_sentinel(self, mock_tg, mock_search):
        mock_search.return_value = {
            "ok": True,
            "results": [
                {"title": "Proyecto Upwork", "snippet": "Automatización con Python", "link": "https://upwork.com/job/1"}
            ]
        }
        mock_tg.return_value = {"ok": True, "message_id": 42}
        
        res = executive_service.run_opportunity_sentinel(
            query="test query",
            telegram_token="fake_tok",
            chat_id="123"
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["telegram_sent"])
        self.assertIn("Centinela Akira", res["report_markdown"])
        self.assertEqual(res["count"], 1)

    @patch("web_engine.search_web")
    @patch("telegram_service.send_telegram_message")
    def test_run_upwork_sentinel(self, mock_tg, mock_search):
        mock_search.return_value = {
            "ok": True,
            "results": [
                {"title": "Python Automation Project", "snippet": "Build scraper and REST API", "link": "https://upwork.com/job/99"}
            ]
        }
        mock_tg.return_value = {"ok": True, "message_id": 43}
        
        res = executive_service.run_upwork_sentinel(telegram_token="fake_tok", chat_id="123")
        self.assertTrue(res["ok"])
        self.assertTrue(res["telegram_sent"])
        self.assertIn("PROPUESTA GANADORA", res["proposal"])
        self.assertEqual(res["opportunity"]["title"], "Python Automation Project")

    @patch("telegram_service.send_telegram_document")
    def test_generate_and_send_pdf(self, mock_send_doc):
        mock_send_doc.return_value = {"ok": True, "message_id": 44, "filename": "Propuesta_Logistica.pdf"}
        
        res = executive_service.generate_and_send_pdf("fake_tok", "123", "Logistica y Rutas")
        self.assertTrue(res["ok"])
        self.assertEqual(res["filename"], "Propuesta_Logistica.pdf")
        mock_send_doc.assert_called_once()

if __name__ == "__main__":
    unittest.main()
