import unittest
from unittest.mock import patch
import deep_research

class TestDeepResearchContract(unittest.TestCase):
    @patch("web_engine.fetch_url")
    @patch("web_engine.search_web")
    def test_execute_deep_research_success(self, mock_search, mock_fetch):
        mock_search.side_effect = [
            # Broad search
            {
                "ok": True,
                "results": [
                    {"title": "Doc Principal", "link": "https://python.org/doc1"},
                    {"title": "Doc Secundaria", "link": "https://python.org/doc2"}
                ]
            },
            # Subquery 1
            {
                "ok": True,
                "results": [{"title": "Subquery Result 1", "link": "https://sub.org/item1"}]
            },
            # Subquery 2
            {
                "ok": True,
                "results": [{"title": "Subquery Result 2", "link": "https://sub.org/item2"}]
            }
        ]

        mock_fetch.return_value = {
            "ok": True,
            "title": "Doc Principal",
            "content": "Python 3.13 implementa un nuevo compilador JIT que acelera la ejecucion en un 15 por ciento.",
            "cached": True,
            "char_count": 89
        }

        res = deep_research.execute_deep_research("Python 3.13 JIT", max_subqueries=2)
        self.assertTrue(res["ok"])
        self.assertEqual(res["topic"], "Python 3.13 JIT")
        self.assertEqual(res["steps_executed"], 3)
        self.assertGreaterEqual(res["sources_count"], 2)
        self.assertIn("# DOSSIER DE INVESTIGACIÓN PROFUNDA", res["markdown_report"])
        self.assertIn("Python 3.13 implementa un nuevo compilador JIT", res["markdown_report"])

    def test_empty_topic(self):
        res = deep_research.execute_deep_research("   ")
        self.assertFalse(res["ok"])

if __name__ == "__main__":
    unittest.main()
