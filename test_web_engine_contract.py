"""
TEST WEB ENGINE CONTRACT
Verifies the zero-cost live web search and deep URL extractor contract.
"""

import unittest
from unittest.mock import patch, MagicMock
import web_engine

class TestWebEngineContract(unittest.TestCase):
    def test_search_web_empty_query(self):
        res = web_engine.search_web("   ")
        self.assertFalse(res["ok"])
        self.assertEqual(res["count"], 0)

    def test_fetch_url_invalid_scheme(self):
        res = web_engine.fetch_url("ftp://example.com/file")
        self.assertFalse(res["ok"])
        self.assertIn("URL inválida", res["error"])

    @patch("urllib.request.urlopen")
    def test_search_web_mocked_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"""
        <html><body>
          <a class="result__a" href="https://example.com/item1">Item Uno</a>
          <a class="result__snippet">Este es el resumen de prueba del item 1.</a>
        </body></html>
        """
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = web_engine.search_web("prueba", max_results=2)
        self.assertTrue(res["ok"])
        self.assertEqual(res["provider"], "duckduckgo_live")
        self.assertGreaterEqual(len(res["results"]), 1)
        self.assertEqual(res["results"][0]["title"], "Item Uno")
        self.assertEqual(res["results"][0]["link"], "https://example.com/item1")

    @patch("urllib.request.urlopen")
    def test_fetch_url_mocked_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"""
        <html>
          <head><title>Mi Pagina de Prueba</title><script>var x = 1;</script></head>
          <body>
            <header>Cabecera a ignorar</header>
            <main><p>Contenido principal extraido con exito.</p></main>
            <footer>Pie a ignorar</footer>
          </body>
        </html>
        """
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = web_engine.fetch_url("https://example.com/test", max_chars=100)
        self.assertTrue(res["ok"])
        self.assertEqual(res["title"], "Mi Pagina de Prueba")
        self.assertIn("Contenido principal", res["content"])
        self.assertNotIn("Cabecera a ignorar", res["content"])
        self.assertNotIn("Pie a ignorar", res["content"])

    @patch("web_engine.search_web")
    def test_augment_prompt_with_web(self, mock_search):
        mock_search.return_value = {
            "ok": True,
            "timestamp": "2026-10-26T14:00:00Z",
            "results": [
                {"title": "Resultado 1", "link": "https://r1.com", "snippet": "Info 1"}
            ]
        }
        text = web_engine.augment_prompt_with_web("test")
        self.assertIn("DATOS EN VIVO DE INTERNET", text)
        self.assertIn("Resultado 1", text)
        self.assertIn("https://r1.com", text)

if __name__ == "__main__":
    unittest.main()
