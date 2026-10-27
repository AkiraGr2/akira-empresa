import unittest
import os
import tempfile
import shutil
from sentinel_cron import (
    compute_item_id,
    load_seen_registry,
    save_seen_registry,
    format_sentinel_briefing,
    run_sentinel_sweep,
)

class TestSentinelCronContract(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.reg_path = os.path.join(self.test_dir, "test_seen.json")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_deduplication_registry_lifecycle(self):
        seen = load_seen_registry(self.reg_path)
        self.assertEqual(len(seen), 0)

        id1 = compute_item_id("Title 1", "https://example.com/1")
        id2 = compute_item_id("Title 2", "https://example.com/2")
        self.assertNotEqual(id1, id2)

        save_seen_registry({id1, id2}, self.reg_path)
        reloaded = load_seen_registry(self.reg_path)
        self.assertIn(id1, reloaded)
        self.assertIn(id2, reloaded)

    def test_run_sentinel_sweep_and_deduplication(self):
        mock_results = [
            {"title": "Python 3.13 Released", "link": "https://python.org/313", "snippet": "New JIT in Python 3.13"},
            {"title": "FastAPI CVE Patched", "link": "https://fastapi.tiangolo.com/cve", "snippet": "Fix applied"}
        ]
        mock_search = lambda topic, n: mock_results if "Python" in topic else []

        # Run 1: Should discover both items
        res1 = run_sentinel_sweep(
            topics=["Python 3.13"],
            registry_path=self.reg_path,
            search_fn=mock_search
        )
        self.assertEqual(res1["status"], "success")
        self.assertEqual(res1["new_items_count"], 2)

        # Run 2: Same items should be deduplicated, new_items_count = 0
        res2 = run_sentinel_sweep(
            topics=["Python 3.13"],
            registry_path=self.reg_path,
            search_fn=mock_search
        )
        self.assertEqual(res2["status"], "no_new_items")
        self.assertEqual(res2["new_items_count"], 0)

    def test_rss_feed_sweep(self):
        sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
            <channel>
                <title>Upwork Jobs</title>
                <item>
                    <title>AI Agent Builder with Telegram</title>
                    <link>https://upwork.com/jobs/111</link>
                    <description>Need Python developer for Telegram bot.</description>
                </item>
            </channel>
        </rss>"""
        mock_fetch = lambda url: {"status": "success", "content": sample_rss}

        res = run_sentinel_sweep(
            topics=[],
            feed_urls=["https://upwork.com/rss"],
            registry_path=self.reg_path,
            fetch_fn=mock_fetch
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["new_items_count"], 1)
        self.assertIn("AI Agent Builder", res["new_items"][0]["title"])

    def test_format_sentinel_briefing(self):
        brief = format_sentinel_briefing([])
        self.assertIn("Sin novedades críticas", brief)

        items = [{"title": "Alerta Crítica", "link": "https://sec.org", "snippet": "Detalle", "source": "Sec"}]
        brief2 = format_sentinel_briefing(items)
        self.assertIn("ALERTA DE INTELIGENCIA PROACTIVA", brief2)
        self.assertIn("Alerta Crítica", brief2)

if __name__ == "__main__":
    unittest.main()
