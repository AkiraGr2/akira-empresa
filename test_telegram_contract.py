"""
TEST TELEGRAM CONTRACT v3.0
Verifies the zero-cost Telegram integration contract:
- Auto-discovery of chat_id
- Webhook registration & updates processing
- Voice notes transcription & download
- Document (PDF) sending via sendDocument
- 1-word executive commands (/estado, /upwork, /pdf, etc.)
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

    @patch("urllib.request.urlopen")
    def test_send_telegram_document_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"""{
            "ok": true,
            "result": {
                "message_id": 105,
                "document": {"file_name": "test.pdf"}
            }
        }"""
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = telegram_service.send_telegram_document("dummy_token", "123456789", b"%PDF-1.4...", filename="test.pdf")
        self.assertTrue(res["ok"])
        self.assertEqual(res["message_id"], 105)
        self.assertEqual(res["filename"], "test.pdf")

    @patch("telegram_service.set_telegram_webhook")
    @patch("telegram_service.process_pending_telegram_updates")
    @patch("telegram_service.get_last_chat_id")
    @patch("telegram_service.send_telegram_message")
    def test_test_telegram_connection_success(self, mock_send, mock_get_id, mock_poll, mock_webhook):
        mock_get_id.return_value = "987654321"
        mock_webhook.return_value = {"ok": True, "webhook_url": "https://example.com/api/v8/telegram/webhook"}
        mock_poll.return_value = {"ok": True, "processed": 0}
        mock_send.return_value = {"ok": True, "chat_id": "987654321", "message_id": 101}

        res = telegram_service.test_telegram_connection("bot123456:ABC-DEF")
        self.assertTrue(res["ok"])
        self.assertEqual(res["chat_id"], "987654321")
        self.assertTrue(res["webhook_registered"])
        self.assertIn("bidireccional", res["message"])

    @patch("telegram_service.send_telegram_message")
    def test_handle_telegram_update_commands(self, mock_send):
        mock_send.return_value = {"ok": True, "message_id": 56}
        update = {
            "update_id": 124,
            "message": {
                "chat": {"id": 999},
                "text": "/estado"
            }
        }
        res = telegram_service.handle_telegram_update("dummy_token", update)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "status")
        mock_send.assert_called_once()
        self.assertIn("ESTADO EJECUTIVO", mock_send.call_args[0][2])

    @patch("telegram_service.get_telegram_file_bytes")
    @patch("telegram_service.transcribe_telegram_voice")
    @patch("telegram_service.send_telegram_message")
    def test_handle_telegram_voice_note(self, mock_send, mock_transcribe, mock_get_file):
        mock_get_file.return_value = (b"fake_audio_bytes", "voice/file_0.oga")
        mock_transcribe.return_value = "Hola Akira prepárame un resumen"
        mock_send.return_value = {"ok": True, "message_id": 57}
        
        update = {
            "update_id": 125,
            "message": {
                "chat": {"id": 999},
                "voice": {"file_id": "voice_123", "duration": 4}
            }
        }
        reply_gen = lambda t: f"Respuesta a: {t}"
        res = telegram_service.handle_telegram_update("dummy_token", update, reply_generator=reply_gen, groq_keys=["fake_gsk"])
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "chat_reply")
        mock_transcribe.assert_called_once()

if __name__ == "__main__":
    unittest.main()
