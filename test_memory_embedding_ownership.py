import unittest

from persistence.service import NotFoundError, PersistenceService


class FakeTx:
    def __enter__(self): return self
    def __exit__(self, *args): return False


class FakeRepo:
    def __init__(self):
        self.memories = {
            "a": {"id": "a", "owner_scope": "scope:A", "status": "active"},
            "b": {"id": "b", "owner_scope": "scope:B", "status": "active"},
        }
        self.embeddings = {
            "a": {"memory_id": "a", "model": "test", "dimensions": 768},
            "b": {"memory_id": "b", "model": "test", "dimensions": 768},
        }

    def get(self, entity, record_id):
        if entity == "memories":
            return dict(self.memories.get(record_id)) if record_id in self.memories else None
        return None

    def get_memory_embedding(self, memory_id):
        row = self.embeddings.get(memory_id)
        return dict(row) if row else None

    def upsert_memory_embedding(self, memory_id, model, embedding, source_hash):
        self.embeddings[memory_id] = {
            "memory_id": memory_id, "model": model, "dimensions": len(embedding)
        }
        return dict(self.embeddings[memory_id])

    def search_memory_embeddings(self, embedding, model, limit=20, owner_scope=None):
        rows = [dict(v) for v in self.embeddings.values() if v["model"] == model]
        if owner_scope is not None:
            allowed = {
                mid for mid, mem in self.memories.items()
                if mem["owner_scope"] in (owner_scope, "owner")
            }
            rows = [r for r in rows if r["memory_id"] in allowed]
        return rows[:limit]

    def transaction(self):
        return FakeTx()


class MemoryEmbeddingOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.service = PersistenceService(FakeRepo())
        self.embedding = [0.0] * 768

    def test_embedding_read_follows_memory_scope(self):
        self.assertIsNotNone(
            self.service.get_memory_embedding("a", owner_scope="scope:A")
        )
        self.assertIsNone(
            self.service.get_memory_embedding("a", owner_scope="scope:B")
        )

    def test_embedding_write_rejects_foreign_memory(self):
        with self.assertRaises(NotFoundError):
            self.service.upsert_memory_embedding(
                "a", "test", self.embedding, "hash", owner_scope="scope:B"
            )

    def test_semantic_search_passes_owner_scope(self):
        rows = self.service.search_memory_semantic(
            self.embedding, "test", limit=10, owner_scope="scope:A"
        )
        self.assertEqual({r["memory_id"] for r in rows}, {"a"})

    def test_embedding_delete_rejects_foreign_memory(self):
        self.assertFalse(
            self.service.delete_memory_embedding("a", owner_scope="scope:B")
        )


if __name__ == "__main__":
    unittest.main()
