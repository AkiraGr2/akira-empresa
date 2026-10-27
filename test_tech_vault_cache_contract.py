import unittest
import os
import time
import tech_vault_cache

class TestTechVaultCacheContract(unittest.TestCase):
    def test_cache_miss_and_hit(self):
        url = "https://example.com/test-article"
        # Initial miss
        cached = tech_vault_cache.get_cached_url(url)
        self.assertIsNone(cached)

        # Save
        payload = {"title": "Test Title", "content": "Article body content"}
        saved = tech_vault_cache.save_cached_url(url, payload, ttl_seconds=60)
        self.assertTrue(saved)

        # Hit
        hit = tech_vault_cache.get_cached_url(url)
        self.assertIsNotNone(hit)
        self.assertTrue(hit["cached"])
        self.assertEqual(hit["title"], "Test Title")

    def test_cache_expiration(self):
        url = "https://example.com/expired-item"
        payload = {"title": "Expired"}
        # 1-second TTL
        tech_vault_cache.save_cached_url(url, payload, ttl_seconds=1)
        time.sleep(1.2)
        # Should be expired
        expired = tech_vault_cache.get_cached_url(url)
        self.assertIsNone(expired)

    def test_stats(self):
        stats = tech_vault_cache.get_cache_stats()
        self.assertTrue(stats["ok"])
        self.assertIn("entries_count", stats)
        self.assertIn("total_size_bytes", stats)

if __name__ == "__main__":
    unittest.main()
