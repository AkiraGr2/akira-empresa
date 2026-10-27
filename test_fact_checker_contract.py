import unittest
from unittest.mock import patch
import fact_checker

class TestFactCheckerContract(unittest.TestCase):
    @patch("web_engine.search_web")
    def test_triangulate_claim_verified(self, mock_search):
        mock_search.return_value = {
            "ok": True,
            "results": [
                {
                    "title": "FastAPI Soporta WebSockets",
                    "link": "https://fastapi.tiangolo.com/advanced/websockets/",
                    "snippet": "FastAPI provides direct native support for WebSockets and async communication."
                },
                {
                    "title": "Tutorial WebSockets en FastAPI",
                    "link": "https://tutorial.example.org/fastapi-websockets",
                    "snippet": "En este tutorial aprenderás a crear WebSockets nativos con FastAPI y Starlette."
                }
            ]
        }
        res = fact_checker.triangulate_claim("FastAPI WebSockets")
        self.assertTrue(res["ok"])
        self.assertTrue(res["verified"])
        self.assertEqual(res["verdict"], "VERIFICADO")
        self.assertGreaterEqual(res["consensus_score"], 0.5)
        self.assertEqual(len(res["supporting_sources"]), 2)

    @patch("web_engine.search_web")
    def test_triangulate_claim_with_contradiction(self, mock_search):
        mock_search.return_value = {
            "ok": True,
            "results": [
                {
                    "title": "Librería Deprecada",
                    "link": "https://docs.deprecated.com",
                    "snippet": "Esta característica está obsoleta y deprecada desde la versión 2.0."
                }
            ]
        }
        res = fact_checker.triangulate_claim("Uso de función especial")
        self.assertTrue(res["ok"])
        self.assertFalse(res["verified"])
        self.assertGreater(len(res["discrepancies"]), 0)

    def test_empty_claim(self):
        res = fact_checker.triangulate_claim("   ")
        self.assertFalse(res["ok"])

if __name__ == "__main__":
    unittest.main()
