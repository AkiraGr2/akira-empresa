import unittest
from unittest.mock import patch, MagicMock
import voice_service

class TestVoiceServiceContract(unittest.TestCase):
    def test_voice_empty_text(self):
        res = voice_service.generate_voice_bytes("")
        self.assertIsNone(res)

    @patch("edge_tts.Communicate")
    def test_voice_generation_mock(self, mock_comm):
        async def mock_stream():
            yield {"type": "audio", "data": b"OGG_OR_MP3_DATA"}
        instance = MagicMock()
        instance.stream = mock_stream
        mock_comm.return_value = instance

        data = voice_service.generate_voice_bytes("Hola Jhon")
        self.assertEqual(data, b"OGG_OR_MP3_DATA")

if __name__ == "__main__":
    unittest.main()
