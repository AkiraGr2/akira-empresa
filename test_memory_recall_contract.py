import unittest
from contextlib import contextmanager

from persistence.memory_recall import recall_memories
from persistence.postgres import PostgresRepository


class FakeRecallService:
    def __init__(self):
        self.memories = {}
        self.semantic_by_scope = {}
        self.semantic_calls = []
        self.learning_calls = []
        self.reuse_calls = []

    def search_memory(self, filters=None, limit=50, owner_scope=None):
        filters = filters or {}
        rows = [
            dict(row)
            for row in self.memories.values()
            if row.get("status") == "active"
            and (
                owner_scope is None
                or row.get("owner_scope") == owner_scope
                or row.get("owner_scope") == "owner"
            )
        ]
        needle = filters.get("text_contains")
        if needle:
            needle = str(needle).lower()
            rows = [
                row for row in rows
                if needle in str(row.get("content") or "").lower()
            ]
        return rows[:limit]

    def search_memory_semantic(self, embedding, model, limit=20, owner_scope=None):
        self.semantic_calls.append({
            "owner_scope": owner_scope,
            "model": model,
            "limit": limit,
        })
        return list(self.semantic_by_scope.get(owner_scope, []))[:limit]

    def get_memory(self, memory_id, owner_scope=None):
        row = self.memories.get(memory_id)
        if row is None:
            return None
        if owner_scope is None:
            return dict(row)
        if row.get("owner_scope") not in {owner_scope, "owner"}:
            return None
        return dict(row)

    def get_learning(self, learning_id, owner_scope=None):
        self.learning_calls.append((learning_id, owner_scope))
        return {
            "id": learning_id,
            "status": "verified",
            "owner_scope": owner_scope,
            "learning_context": {"promoted": True},
        }

    def record_reuse(self, learning_id, actor="system", owner_scope=None):
        self.reuse_calls.append((learning_id, actor, owner_scope))


class FakeCursor:
    def __init__(self):
        self.calls = []
        self.rows = []

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchall(self):
        return self.rows


class MemoryRecallContractTests(unittest.TestCase):
    MODEL = "gemini-embedding-2"
    VECTOR_A = [1.0] + [0.0] * 767

    def setUp(self):
        self.service = FakeRecallService()
        self.service.memories = {
            "mem_a": {
                "id": "mem_a",
                "content": "recuerdo alpino controlado",
                "memory_type": "semantic",
                "importance": 8,
                "confidence": 0.9,
                "status": "active",
                "owner_scope": "g:user-A",
                "created_at": "2026-10-04T17:00:00+00:00",
                "source": "chat",
            },
            "mem_b": {
                "id": "mem_b",
                "content": "recuerdo marino controlado",
                "memory_type": "semantic",
                "importance": 8,
                "confidence": 0.9,
                "status": "active",
                "owner_scope": "g:user-B",
                "created_at": "2026-10-04T17:00:00+00:00",
                "source": "chat",
            },
        }

    def test_semantic_branch_is_owner_scoped(self):
        self.service.semantic_by_scope = {
            "g:user-A": [{"memory_id": "mem_a", "semantic_score": 1.0}],
            "g:user-B": [{"memory_id": "mem_b", "semantic_score": 1.0}],
        }

        result_a = recall_memories(
            self.service,
            "consulta remota",
            owner_scope="g:user-A",
            extract_keywords=lambda _q: [],
            generate_embedding=lambda _q: self.VECTOR_A,
            embedding_model=self.MODEL,
        )
        result_b = recall_memories(
            self.service,
            "consulta remota",
            owner_scope="g:user-B",
            extract_keywords=lambda _q: [],
            generate_embedding=lambda _q: self.VECTOR_A,
            embedding_model=self.MODEL,
        )

        self.assertEqual([row["id"] for row in result_a], ["mem_a"])
        self.assertEqual([row["id"] for row in result_b], ["mem_b"])
        self.assertEqual(
            [call["owner_scope"] for call in self.service.semantic_calls],
            ["g:user-A", "g:user-B"],
        )

    def test_lexical_fallback_survives_missing_embeddings(self):
        result = recall_memories(
            self.service,
            "marino",
            include_semantic=True,
            owner_scope="g:user-B",
            extract_keywords=lambda _q: ["marino"],
            generate_embedding=lambda _q: None,
            embedding_model=self.MODEL,
        )
        self.assertEqual([row["id"] for row in result], ["mem_b"])
        self.assertEqual(self.service.semantic_calls, [])

    def test_archived_memory_is_never_recalled(self):
        self.service.memories["mem_b"]["status"] = "archived"
        result = recall_memories(
            self.service,
            "marino",
            include_semantic=False,
            owner_scope="g:user-B",
            extract_keywords=lambda _q: ["marino"],
            generate_embedding=None,
            embedding_model=self.MODEL,
        )
        self.assertEqual(result, [])

    def test_protected_learning_uses_same_owner_scope(self):
        self.service.memories["mem_learning"] = {
            "id": "mem_learning",
            "content": "aprendizaje promovido",
            "memory_type": "semantic",
            "importance": 7,
            "confidence": 1.0,
            "status": "active",
            "owner_scope": "g:user-A",
            "created_at": "2026-10-04T17:00:00+00:00",
            "source": "learning_promoted",
            "source_id": "learning-A",
        }
        result = recall_memories(
            self.service,
            "aprendizaje",
            include_semantic=False,
            owner_scope="g:user-A",
            extract_keywords=lambda _q: ["aprendizaje"],
            generate_embedding=None,
            embedding_model=self.MODEL,
        )
        self.assertEqual([row["id"] for row in result], ["mem_learning"])
        self.assertEqual(
            self.service.learning_calls,
            [("learning-A", "g:user-A")],
        )
        self.assertEqual(
            self.service.reuse_calls,
            [("learning-A", "recall", "g:user-A")],
        )


class SemanticPostgresQueryContractTests(unittest.TestCase):
    def test_search_parameter_order_matches_sql_placeholders(self):
        repo = PostgresRepository.__new__(PostgresRepository)
        cursor = FakeCursor()

        @contextmanager
        def fake_cursor():
            yield cursor

        repo._cursor = fake_cursor
        vector = [1.0] + [0.0] * 767
        expected_literal = repo._vector_literal(vector)

        rows = repo.search_memory_embeddings(
            vector,
            "gemini-embedding-2",
            limit=20,
            owner_scope="g:user-A",
        )

        self.assertEqual(rows, [])
        self.assertEqual(len(cursor.calls), 1)
        _sql, params = cursor.calls[0]
        self.assertEqual(
            params,
            [
                expected_literal,
                "gemini-embedding-2",
                "g:user-A",
                expected_literal,
                20,
            ],
        )


if __name__ == "__main__":
    unittest.main()
