import unittest

from persistence.core import ConflictError, ValidationError
from persistence.service import PersistenceService


class FakeTx:
    def __init__(self, repo):
        self.repo = repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def create(self, entity, record):
        return self.repo._create(entity, record)

    def update(self, entity, record_id, changes, expected_version):
        return self.repo._update(entity, record_id, changes, expected_version)

    def append_audit(self, event):
        self.repo.audit.append(dict(event))


class FakeRepo:
    def __init__(self):
        self.tables = {"memories": {}}
        self.audit = []

    def transaction(self):
        return FakeTx(self)

    def _create(self, entity, record):
        table = self.tables.setdefault(entity, {})
        key = record.get("idempotency_key")
        if key:
            for current in table.values():
                if (
                    current.get("idempotency_key") == key
                    and (
                        entity != "memories"
                        or current.get("owner_scope") == record.get("owner_scope")
                    )
                ):
                    return dict(current), False
        table[record["id"]] = dict(record, version=1)
        return dict(table[record["id"]]), True

    def get(self, entity, record_id):
        row = self.tables.get(entity, {}).get(record_id)
        return dict(row) if row else None

    def exists(self, entity, record_id):
        return self.get(entity, record_id) is not None

    def count(self, entity, filters=None):
        return len(self.search(entity, filters or {}, limit=10000))

    def search(
        self,
        entity,
        filters=None,
        limit=50,
        offset=0,
        order_by="created_at",
        descending=True,
    ):
        rows = [dict(v) for v in self.tables.get(entity, {}).values()]
        filters = filters or {}

        for key, value in filters.items():
            if key == "text_contains":
                needle = str(value).lower()
                rows = [r for r in rows if needle in str(r.get("content") or "").lower()]
                continue
            if key.endswith("__in"):
                field = key[:-4]
                allowed = set(value)
                rows = [r for r in rows if r.get(field) in allowed]
                continue
            rows = [r for r in rows if r.get(key) == value]

        if order_by in {"created_at", "updated_at", "importance", "last_accessed_at"}:
            rows.sort(key=lambda r: (r.get(order_by) is not None, r.get(order_by)), reverse=descending)

        return rows[offset:offset + limit]

    def _update(self, entity, record_id, changes, expected_version):
        row = self.tables.get(entity, {}).get(record_id)
        if row is None:
            raise KeyError(record_id)
        if row["version"] != expected_version:
            raise ConflictError("version conflict")
        row = dict(row)
        row.update(changes)
        row["version"] += 1
        self.tables[entity][record_id] = row
        return dict(row)


class PersistentMemoryContractTests(unittest.TestCase):
    def setUp(self):
        self.service = PersistenceService(FakeRepo())

    @staticmethod
    def memory(content, scope, privacy="PRIVATE", source="test"):
        return {
            "content": content,
            "memory_type": "semantic",
            "importance": 7,
            "confidence": 0.9,
            "source": source,
            "source_reference": "test://persistent-memory",
            "owner_scope": scope,
            "privacy_level": privacy,
            "tags": ["persistent-memory"],
        }

    def test_create_and_reread_memory(self):
        created = self.service.save_memory(
            self.memory("memoria A", "g:user-A"),
            actor="owner@example.test",
            owner_scope="g:user-A",
        )
        self.assertEqual(created["outcome"], "created")
        record = self.service.get_memory(created["record"]["id"], owner_scope="g:user-A")
        self.assertIsNotNone(record)
        self.assertEqual(record["content"], "memoria A")
        self.assertEqual(record["owner_scope"], "g:user-A")
        self.assertEqual(record["version"], 1)

    def test_idempotency_does_not_duplicate(self):
        key = "persistent-memory:idem:v1"
        first = self.service.save_memory(
            self.memory("memoria idem", "g:user-A"),
            actor="owner@example.test",
            owner_scope="g:user-A",
            idempotency_key=key,
        )
        second = self.service.save_memory(
            self.memory("memoria idem", "g:user-A"),
            actor="owner@example.test",
            owner_scope="g:user-A",
            idempotency_key=key,
        )
        self.assertEqual(first["outcome"], "created")
        self.assertEqual(second["outcome"], "already_synced")
        self.assertEqual(first["record"]["id"], second["record"]["id"])
        self.assertEqual(self.service.count_memory({"idempotency_key": key}), 1)

    def test_idempotency_is_scoped_to_owner(self):
        key = "persistent-memory:idem:owner-scope:v1"
        first = self.service.save_memory(
            self.memory("memoria scope A", "g:user-A"),
            actor="owner@example.test",
            owner_scope="g:user-A",
            idempotency_key=key,
        )
        second = self.service.save_memory(
            self.memory("memoria scope B", "g:user-B"),
            actor="owner2@example.test",
            owner_scope="g:user-B",
            idempotency_key=key,
        )
        self.assertEqual(first["outcome"], "created")
        self.assertEqual(second["outcome"], "created")
        self.assertNotEqual(first["record"]["id"], second["record"]["id"])

    def test_owner_scope_isolation(self):
        a = self.service.save_memory(
            self.memory("solo A", "g:user-A"),
            actor="owner@example.test",
            owner_scope="g:user-A",
        )
        b = self.service.save_memory(
            self.memory("solo B", "g:user-B"),
            actor="owner@example.test",
            owner_scope="g:user-B",
        )
        ids_a = {r["id"] for r in self.service.search_memory(owner_scope="g:user-A")}
        ids_b = {r["id"] for r in self.service.search_memory(owner_scope="g:user-B")}
        self.assertIn(a["record"]["id"], ids_a)
        self.assertNotIn(b["record"]["id"], ids_a)
        self.assertIn(b["record"]["id"], ids_b)
        self.assertNotIn(a["record"]["id"], ids_b)

    def test_private_memory_is_not_hive_visible(self):
        private = self.service.save_memory(
            self.memory("privada", "g:user-A", privacy="PRIVATE"),
            actor="owner@example.test",
            owner_scope="g:user-A",
        )
        shareable = self.service.save_memory(
            self.memory("compartible", "g:user-A", privacy="SHAREABLE"),
            actor="owner@example.test",
            owner_scope="g:user-A",
        )
        hive_ids = {
            r["id"]
            for r in self.service.search_memory(
                hive=True,
                owner_scope="g:user-A",
                limit=20,
            )
        }
        self.assertNotIn(private["record"]["id"], hive_ids)
        self.assertIn(shareable["record"]["id"], hive_ids)

    def test_version_conflict_and_archive(self):
        created = self.service.save_memory(
            self.memory("mutable", "g:user-A"),
            actor="owner@example.test",
            owner_scope="g:user-A",
        )
        memory_id = created["record"]["id"]
        updated = self.service.update_memory(
            memory_id,
            {"importance": 8},
            expected_version=1,
            actor="owner@example.test",
        )
        self.assertEqual(updated["version"], 2)

        with self.assertRaises(ConflictError):
            self.service.update_memory(
                memory_id,
                {"importance": 9},
                expected_version=1,
                actor="owner@example.test",
            )

        archived = self.service.archive_memory(
            memory_id,
            expected_version=2,
            actor="owner@example.test",
        )
        self.assertEqual(archived["status"], "archived")
        self.assertEqual(
            self.service.search_memory(
                {"text_contains": "mutable"},
                owner_scope="g:user-A",
            ),
            [],
        )
        self.assertTrue(self.service.exists_memory(memory_id))

    def test_invalid_memory_input_writes_nothing(self):
        before = self.service.count_memory({"status": "active"})
        with self.assertRaises(ValidationError):
            self.service.save_memory(
                self.memory(" ", "g:user-A"),
                actor="owner@example.test",
                owner_scope="g:user-A",
            )
        after = self.service.count_memory({"status": "active"})
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
