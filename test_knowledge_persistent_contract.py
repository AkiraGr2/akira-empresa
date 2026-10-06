import unittest

from persistence.core import ConflictError, NotFoundError, ValidationError
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
        self.tables = {
            "knowledge_records": {},
            "graph_nodes": {
                "node-A": {
                    "id": "node-A", "node_type": "concept", "label": "A",
                    "description": "A", "node_metadata": {}, "tags": [],
                    "weight": 1.0, "confidence": 1.0, "reuse_count": 0,
                    "owner_scope": "scope:A", "privacy_level": "PRIVATE",
                    "status": "active", "version": 1,
                },
            },
        }
        self.audit = []

    def transaction(self):
        return FakeTx(self)

    def _create(self, entity, record):
        table = self.tables.setdefault(entity, {})
        key = record.get("idempotency_key")
        if key:
            for current in table.values():
                if current.get("idempotency_key") == key and current.get("owner_scope") == record.get("owner_scope"):
                    return dict(current), False
        table[record["id"]] = dict(record, version=1)
        return dict(table[record["id"]]), True

    def get(self, entity, record_id):
        row = self.tables.get(entity, {}).get(record_id)
        return dict(row) if row else None

    def exists(self, entity, record_id):
        return self.get(entity, record_id) is not None

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        rows = [dict(v) for v in self.tables.get(entity, {}).values()]
        filters = filters or {}
        for key, value in filters.items():
            if key.endswith("__in"):
                field = key[:-4]
                rows = [r for r in rows if r.get(field) in set(value)]
            else:
                rows = [r for r in rows if r.get(key) == value]
        return rows[offset:offset + limit]

    def count(self, entity, filters=None):
        return len(self.search(entity, filters or {}, limit=10000))

    def _update(self, entity, record_id, changes, expected_version):
        row = self.tables.get(entity, {}).get(record_id)
        if row is None:
            raise NotFoundError(record_id)
        if row["version"] != expected_version:
            raise ConflictError("version conflict")
        row = dict(row)
        row.update(changes)
        row["version"] += 1
        self.tables[entity][record_id] = row
        return dict(row)


class KnowledgePersistenceContractTests(unittest.TestCase):
    def setUp(self):
        self.service = PersistenceService(FakeRepo())

    def knowledge(self, scope="scope:A", related_nodes=None):
        return {
            "concept": "contrato de conocimiento",
            "content": "Knowledge debe conservar provenance y distinguirse de Memory y Learning.",
            "domain": "architecture",
            "source": "test",
            "source_reference": "test://knowledge",
            "confidence": 0.8,
            "tags": ["f4"],
            "related_nodes": list(related_nodes or []),
            "owner_scope": scope,
            "privacy_level": "PRIVATE",
        }

    def test_create_reread_and_idempotency(self):
        first = self.service.save_knowledge(
            self.knowledge(), actor="owner@example.test",
            owner_scope="scope:A", idempotency_key="knowledge:test:v1",
        )
        second = self.service.save_knowledge(
            self.knowledge(), actor="owner@example.test",
            owner_scope="scope:A", idempotency_key="knowledge:test:v1",
        )
        self.assertEqual(first["outcome"], "created")
        self.assertEqual(second["outcome"], "already_synced")
        self.assertEqual(first["record"]["id"], second["record"]["id"])
        self.assertEqual(first["record"]["verification_status"], "unverified")

    def test_owner_isolation(self):
        first = self.service.save_knowledge(self.knowledge("scope:A"), owner_scope="scope:A")
        self.assertIsNotNone(self.service.get_knowledge(first["record"]["id"], owner_scope="scope:A"))
        self.assertIsNone(self.service.get_knowledge(first["record"]["id"], owner_scope="scope:B"))

    def test_related_nodes_must_be_accessible(self):
        created = self.service.save_knowledge(
            self.knowledge(related_nodes=["node-A"]),
            owner_scope="scope:A",
        )
        self.assertEqual(created["record"]["related_nodes"], ["node-A"])
        with self.assertRaises(NotFoundError):
            self.service.save_knowledge(
                self.knowledge(related_nodes=["node-A"]),
                owner_scope="scope:B",
            )
        with self.assertRaises(NotFoundError):
            self.service.save_knowledge(
                self.knowledge(related_nodes=["missing"]),
                owner_scope="scope:A",
            )

    def test_verified_requires_evidence_and_factual_edits_invalidate(self):
        created = self.service.save_knowledge(self.knowledge(), owner_scope="scope:A")
        kid = created["record"]["id"]
        with self.assertRaises(ValidationError):
            self.service.update_knowledge(
                kid,
                {"verification_status": "verified"},
                expected_version=1,
                actor="owner@example.test",
                owner_scope="scope:A",
            )
        verified = self.service.verify_knowledge(
            kid,
            [{
                "type": "manual_verification",
                "title": "evidence",
                "reference": "test://evidence",
                "note": "evidencia de contrato",
            }],
            actor="owner@example.test",
            expected_version=1,
            owner_scope="scope:A",
        )
        self.assertEqual(verified["verification_status"], "verified")
        self.assertIsNotNone(verified["last_verified_at"])
        self.assertEqual(verified["verified_by"], "owner@example.test")

        changed = self.service.update_knowledge(
            kid,
            {"content": "contenido factual modificado"},
            expected_version=verified["version"],
            actor="owner@example.test",
            owner_scope="scope:A",
        )
        self.assertEqual(changed["verification_status"], "partially_verified")
        self.assertIsNone(changed["last_verified_at"])
        self.assertIsNone(changed["verified_by"])

    def test_version_conflict_and_archive(self):
        created = self.service.save_knowledge(self.knowledge(), owner_scope="scope:A")
        updated = self.service.update_knowledge(
            created["record"]["id"],
            {"tags": ["f4", "updated"]},
            expected_version=1,
            actor="owner@example.test",
            owner_scope="scope:A",
        )
        self.assertEqual(updated["version"], 2)
        with self.assertRaises(ConflictError):
            self.service.update_knowledge(
                created["record"]["id"],
                {"tags": ["stale"]},
                expected_version=1,
                actor="owner@example.test",
                owner_scope="scope:A",
            )
        archived = self.service.archive_knowledge(
            created["record"]["id"],
            expected_version=2,
            actor="owner@example.test",
            owner_scope="scope:A",
        )
        self.assertEqual(archived["status"], "archived")

    def test_unknown_verification_state_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.save_knowledge(
                {**self.knowledge(), "verification_status": "invented"},
                owner_scope="scope:A",
            )


if __name__ == "__main__":
    unittest.main()
