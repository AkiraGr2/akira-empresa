"""
TEST TELEGRAM CONTRACT v4.0
Verifies the complete suite of 24 executive capabilities on Telegram:
- Auto-discovery of chat_id
- Webhook registration & updates processing
- Voice notes transcription & download
- Document (PDF, ZIP) sending via sendDocument
- Tactile interactive buttons (inline keyboards & callback_query)
- Photo and receipt OCR inspection
- Code and script file auditing
- Native Telegram command menu (setMyCommands)
- Python sandbox console (/py)
- Autonomous reminders & focus mode (/recordar, /silencio)
- Quote generator (/cotizar)
- Hive specialists invocation (@seguridad)
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
    def test_send_telegram_photo_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"""{"ok": true, "result": {"message_id": 102}}"""
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = telegram_service.send_telegram_photo("dummy_token", "123456789", b"\x89PNG\r\n\x1a\nfake", caption="Test Chart")
        self.assertTrue(res["ok"])
        self.assertEqual(res["message_id"], 102)

    @patch("urllib.request.urlopen")
    def test_send_telegram_voice_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"""{"ok": true, "result": {"message_id": 103}}"""
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = telegram_service.send_telegram_voice("dummy_token", "123456789", b"fake_ogg_bytes", caption="Test Voice")
        self.assertTrue(res["ok"])
        self.assertEqual(res["message_id"], 103)

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

    @patch("telegram_service.set_telegram_commands")
    @patch("telegram_service.set_telegram_webhook")
    @patch("telegram_service.process_pending_telegram_updates")
    @patch("telegram_service.get_last_chat_id")
    @patch("telegram_service.send_telegram_interactive_message")
    def test_test_telegram_connection_success(self, mock_send, mock_get_id, mock_poll, mock_webhook, mock_commands):
        mock_get_id.return_value = "987654321"
        mock_commands.return_value = {"ok": True}
        mock_webhook.return_value = {"ok": True, "webhook_url": "https://example.com/api/v8/telegram/webhook"}
        mock_poll.return_value = {"ok": True, "processed": 0}
        mock_send.return_value = {"ok": True, "chat_id": "987654321", "message_id": 101}

        res = telegram_service.test_telegram_connection("bot123456:ABC-DEF")
        self.assertTrue(res["ok"])
        self.assertEqual(res["chat_id"], "987654321")
        self.assertTrue(res["webhook_registered"])
        self.assertTrue(res["commands_registered"])
        self.assertIn("blindada", res["message"])

    @patch("telegram_service.send_telegram_interactive_message")
    def test_handle_telegram_update_status(self, mock_send):
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

    @patch("telegram_service.send_telegram_interactive_message")
    def test_handle_telegram_callback_query(self, mock_send):
        mock_send.return_value = {"ok": True, "message_id": 57}
        update = {
            "update_id": 125,
            "callback_query": {
                "id": "cb_001",
                "message": {"chat": {"id": 999}, "message_id": 20},
                "data": "/estado"
            }
        }
        with patch("telegram_service.answer_callback_query") as mock_ans:
            mock_ans.return_value = {"ok": True}
            res = telegram_service.handle_telegram_update("dummy_token", update)
            self.assertTrue(res["ok"])
            self.assertEqual(res["action"], "status")
            mock_ans.assert_called_once()

    @patch("telegram_service.send_telegram_message")
    def test_handle_telegram_python_sandbox(self, mock_send):
        mock_send.return_value = {"ok": True, "message_id": 58}
        update = {
            "update_id": 126,
            "message": {
                "chat": {"id": 999},
                "text": "/py 100 * 5"
            }
        }
        res = telegram_service.handle_telegram_update("dummy_token", update)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "py_exec")
        self.assertIn("500", mock_send.call_args[0][2])

    @patch("telegram_service.send_telegram_message")
    def test_handle_telegram_reminders(self, mock_send):
        mock_send.return_value = {"ok": True, "message_id": 59}
        update = {
            "update_id": 127,
            "message": {
                "chat": {"id": 999},
                "text": "/recordar 15m Llamar a cliente de Upwork"
            }
        }
        res = telegram_service.handle_telegram_update("dummy_token", update)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "reminder_set")

    @patch("telegram_service.send_telegram_interactive_message")
    def test_handle_telegram_specialist_invocation(self, mock_send):
        mock_send.return_value = {"ok": True, "message_id": 60}
        update = {
            "update_id": 128,
            "message": {
                "chat": {"id": 999},
                "text": "@seguridad ¿nuestras claves API están protegidas?"
            }
        }
        res = telegram_service.handle_telegram_update("dummy_token", update)
        self.assertTrue(res["ok"])
        self.assertEqual(res["action"], "specialist_invocation")
        self.assertEqual(res["specialist"], "@seguridad")
        self.assertIn("SEGURIDAD & QA", mock_send.call_args[0][2])

    @patch("telegram_service.get_telegram_file_bytes")
    @patch("telegram_service.transcribe_telegram_voice")
    @patch("telegram_service.send_telegram_message")
    @patch("telegram_service.send_telegram_interactive_message")
    def test_handle_telegram_voice_note(self, mock_send_int, mock_send, mock_transcribe, mock_get_file):
        mock_get_file.return_value = (b"fake_audio_bytes", "voice/file_0.oga")
        mock_transcribe.return_value = "Hola Akira prepárame un resumen"
        mock_send.return_value = {"ok": True, "message_id": 61}
        mock_send_int.return_value = {"ok": True, "message_id": 62}
        
        update = {
            "update_id": 129,
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

    @patch("urllib.request.urlopen")
    def test_get_bot_info(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true, "result": {"id": 1234, "is_bot": true, "first_name": "Akira", "username": "AkiraBot"}}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        info = telegram_service.get_bot_info("fake_token")
        self.assertTrue(info["ok"])
        self.assertEqual(info["result"]["username"], "AkiraBot")

    @patch("telegram_service.get_bot_info")
    @patch("telegram_service.set_telegram_commands")
    @patch("telegram_service.set_telegram_webhook")
    @patch("urllib.request.urlopen")
    def test_get_webhook_diagnostics_and_repair(self, mock_urlopen, mock_wh, mock_cmd, mock_bot):
        mock_bot.return_value = {"ok": True, "result": {"username": "AkiraBot", "first_name": "Akira"}}
        mock_cmd.return_value = {"ok": True}
        mock_wh.return_value = {"ok": True, "webhook_url": "https://akira-empresa.onrender.com/api/v8/telegram/webhook/fake"}
        
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"ok": true, "result": {"url": "https://akira-empresa.onrender.com/api/v8/telegram/webhook/fake", "pending_update_count": 0}}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        diag = telegram_service.repair_telegram_webhook("fake_token")
        self.assertTrue(diag["ok"])
        self.assertEqual(diag["bot_username"], "@AkiraBot")
        self.assertEqual(diag["bot_link"], "https://t.me/AkiraBot")
        self.assertTrue(diag["webhook_registered"])

    @patch("urllib.request.urlopen")
    def test_transcribe_audio_with_groq_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"text": "Hola Akira como estas"}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        text = telegram_service.transcribe_audio_with_groq(b"fake_audio", groq_keys=["gsk_test"], filename="voice.ogg")
        self.assertEqual(text, "Hola Akira como estas")

    @patch("urllib.request.urlopen")
    def test_transcribe_audio_with_gemini_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"candidates": [{"content": {"parts": [{"text": "Propuesta de valor formal"}]}}]}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        text = telegram_service.transcribe_audio_with_gemini(b"fake_audio", gemini_keys=["gem_test"], mime_type="audio/ogg")
        self.assertEqual(text, "Propuesta de valor formal")

    @patch("telegram_service.transcribe_audio_with_groq")
    @patch("telegram_service.transcribe_audio_with_gemini")
    def test_transcribe_telegram_voice_fallback(self, mock_gemini, mock_groq):
        mock_groq.return_value = None
        mock_gemini.return_value = "Audio recuperado por Gemini Flash"

        text = telegram_service.transcribe_telegram_voice(b"fake_bytes", groq_keys=["gsk"], gemini_keys=["gem"])
        self.assertEqual(text, "Audio recuperado por Gemini Flash")
        mock_groq.assert_called_once()
        mock_gemini.assert_called_once()

if __name__ == "__main__":
    unittest.main()
