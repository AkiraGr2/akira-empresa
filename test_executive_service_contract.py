"""
TEST EXECUTIVE SERVICE CONTRACT
Verifies the daily briefing, sentinel, and deliverable logic at zero cost.
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

if __name__ == "__main__":
    unittest.main()
