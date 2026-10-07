import unittest

from persistence.service import ConflictError, PersistenceService, NotFoundError


class FakeTx:
    def __init__(self, repo):
        self.repo = repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def create(self, entity, record):
        rows = self.repo.rows.setdefault(entity, [])
        key = record.get("idempotency_key")
        if key is not None:
            for row in rows:
                if row.get("idempotency_key") == key:
                    return dict(row), False
        rows.append(dict(record))
        return dict(record), True

    def update(self, entity, record_id, changes, expected_version):
        rows = self.repo.rows.get(entity, [])
        row = next(r for r in rows if r["id"] == record_id)
        if row["version"] != expected_version:
            raise RuntimeError("version conflict")
        row.update(changes)
        row["version"] += 1
        return dict(row)

    def append_audit(self, payload):
        return None


class FakeRepo:
    def __init__(self):
        self.rows = {
            "conversations": [{
                "id": "conv_1",
                "title": "Chat",
                "created_by": "owner@example.test",
                "status": "active",
                "message_count": 0,
                "version": 1,
            }],
            "conversation_messages": [],
        }

    def get(self, entity, record_id):
        for row in self.rows.get(entity, []):
            if row.get("id") == record_id:
                return dict(row)
        return None

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        rows = [dict(row) for row in self.rows.get(entity, [])]
        for key, value in (filters or {}).items():
            rows = [row for row in rows if row.get(key) == value]
        return rows[offset:offset + limit]

    def count(self, entity, filters=None):
        return len(self.search(entity, filters, limit=5000))

    def transaction(self):
        return FakeTx(self)


class ConversationIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo()
        self.service = PersistenceService(self.repo)

    def test_same_message_idempotency_key_does_not_duplicate_or_increment_count(self):
        first = self.service.add_message(
            "conv_1",
            "user",
            "hola",
            actor="owner@example.test",
            owner="owner@example.test",
            idempotency_key="chat:exchange-1:user",
        )
        second = self.service.add_message(
            "conv_1",
            "user",
            "hola",
            actor="owner@example.test",
            owner="owner@example.test",
            idempotency_key="chat:exchange-1:user",
        )

        self.assertEqual(first["outcome"], "created")
        self.assertEqual(second["outcome"], "already_synced")
        self.assertEqual(first["record"]["id"], second["record"]["id"])
        self.assertEqual(self.repo.get("conversations", "conv_1")["message_count"], 1)
        self.assertEqual(len(self.repo.rows["conversation_messages"]), 1)

    def test_reusing_key_for_other_role_is_rejected(self):
        self.service.add_message(
            "conv_1",
            "user",
            "hola",
            actor="owner@example.test",
            owner="owner@example.test",
            idempotency_key="chat:exchange-2:user",
        )
        with self.assertRaises(ConflictError):
            self.service.add_message(
                "conv_1",
                "assistant",
                "respuesta distinta",
                actor="owner@example.test",
                owner="owner@example.test",
                idempotency_key="chat:exchange-2:user",
            )

    def test_cross_owner_conversation_idempotency_is_rejected(self):
        self.repo.rows["conversations"].append({
            "id": "conv_2",
            "title": "Other",
            "created_by": "other@example.test",
            "status": "active",
            "message_count": 0,
            "version": 1,
            "idempotency_key": "chat:exchange-cross-owner:conversation",
        })
        from persistence.core import ConflictError
        with self.assertRaises(ConflictError):
            self.service.create_conversation(
                {"title": "attempt"},
                actor="owner@example.test",
                idempotency_key="chat:exchange-cross-owner:conversation",
            )

    def test_message_lookup_respects_conversation_owner(self):
        created = self.service.add_message(
            "conv_1",
            "assistant",
            "respuesta",
            actor="owner@example.test",
            owner="owner@example.test",
            idempotency_key="chat:exchange-3:assistant",
        )
        self.assertEqual(
            self.service.get_message_by_idempotency_key(
                "chat:exchange-3:assistant",
                owner="owner@example.test",
            )["id"],
            created["record"]["id"],
        )
        self.assertIsNone(
            self.service.get_message_by_idempotency_key(
                "chat:exchange-3:assistant",
                owner="other@example.test",
            )
        )

    def test_existing_message_is_returned_without_count_mutation(self):
        self.service.add_message(
            "conv_1",
            "assistant",
            "respuesta estable",
            actor="owner@example.test",
            owner="owner@example.test",
            idempotency_key="chat:exchange-4:assistant",
        )
        before = self.repo.get("conversations", "conv_1")["message_count"]

        replay = self.service.add_message(
            "conv_1",
            "assistant",
            "respuesta estable",
            actor="owner@example.test",
            owner="owner@example.test",
            idempotency_key="chat:exchange-4:assistant",
        )

        self.assertEqual(replay["record"]["content"], "respuesta estable")
        self.assertEqual(
            self.repo.get("conversations", "conv_1")["message_count"],
            before,
        )


if __name__ == "__main__":
    unittest.main()
