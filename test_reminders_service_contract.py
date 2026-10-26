import unittest
import time
import reminders_service

class TestRemindersServiceContract(unittest.TestCase):
    def test_parse_durations(self):
        self.assertEqual(reminders_service.parse_time_duration("30s"), 30)
        self.assertEqual(reminders_service.parse_time_duration("15m"), 900)
        self.assertEqual(reminders_service.parse_time_duration("2h"), 7200)
        self.assertEqual(reminders_service.parse_time_duration("1d"), 86400)
        self.assertEqual(reminders_service.parse_time_duration("invalid"), 0)

    def test_silent_mode(self):
        res = reminders_service.set_silent_mode("test_chat", "10s")
        self.assertTrue(res["ok"])
        self.assertTrue(reminders_service.is_in_silent_mode("test_chat"))
        reminders_service.disable_silent_mode("test_chat")
        self.assertFalse(reminders_service.is_in_silent_mode("test_chat"))

    def test_add_reminder(self):
        res = reminders_service.add_reminder("fake_token", "test_chat", "10m", "Comprar café")
        self.assertTrue(res["ok"])
        self.assertEqual(res["seconds"], 600)
        self.assertEqual(res["text"], "Comprar café")

if __name__ == "__main__":
    unittest.main()
