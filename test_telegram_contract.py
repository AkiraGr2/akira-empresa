"""
TEST TELEGRAM CONTRACT
Verifies the zero-cost Telegram integration contract, auto-discovery of chat_id,
and executive notification delivery.
"""

import unittest
from unittest.mock import patch, MagicMock
import telegram_service

class TestTelegramContract(unittest.TestCase):
    def test_empty_token(self):
        res = telegram_service.test_telegram_connection("")
        self.assertFalse(res["ok"])
        self.assertIn("Token", res["error"])

    @patch("urllib.request.urlopen")
    def test_get_last_chat_id_auto_detection(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"""{
            "ok": true,
            "result": [
                {
                    "update_id": 1000,
                    "message": {
                        "message_id": 1,
                        "from": {"id": 123456789, "first_name": "Jhon"},
                        "chat": {"id": 123456789, "first_name": "Jhon", "type": "private"},
                        "text": "/start"
                    }
                }
            ]
        }"""
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        chat_id = telegram_service.get_last_chat_id("dummy_token")
        self.assertEqual(chat_id, "123456789")

    @patch("urllib.request.urlopen")
    def test_send_telegram_message_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"""{
            "ok": true,
            "result": {
                "message_id": 99,
                "text": "Hola Jhon"
            }
        }"""
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = telegram_service.send_telegram_message("dummy_token", "123456789", "Hola Jhon")
        self.assertTrue(res["ok"])
        self.assertEqual(res["chat_id"], "123456789")
        self.assertEqual(res["message_id"], 99)

    @patch("telegram_service.get_last_chat_id")
    @patch("telegram_service.send_telegram_message")
    def test_test_telegram_connection_success(self, mock_send, mock_get_id):
        mock_get_id.return_value = "987654321"
        mock_send.return_value = {"ok": True, "chat_id": "987654321", "message_id": 101}

        res = telegram_service.test_telegram_connection("bot123456:ABC-DEF")
        self.assertTrue(res["ok"])
        self.assertEqual(res["chat_id"], "987654321")
        self.assertIn("éxito", res["message"])

if __name__ == "__main__":
    unittest.main()
