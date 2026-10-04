import unittest

from persistence.service import PersistenceService, NotFoundError


class FakeRepo:
    def __init__(self):
        self.conversation = {
            "id": "conv_1",
            "title": "Privada",
            "created_by": "owner@example.test",
            "status": "active",
            "version": 1,
        }
        self.messages = [
            {"id": "msg_1", "conversation_id": "conv_1", "role": "user", "content": "hola"},
        ]

    def get(self, entity, record_id):
        if entity == "conversations" and record_id == self.conversation["id"]:
            return dict(self.conversation)
        return None

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        filters = filters or {}
        if entity == "conversations":
            rows = [dict(self.conversation)]
            for key, value in filters.items():
                rows = [row for row in rows if row.get(key) == value]
            return rows[:limit]
        if entity == "conversation_messages":
            rows = [dict(row) for row in self.messages]
            for key, value in filters.items():
                rows = [row for row in rows if row.get(key) == value]
            return rows[offset:offset + limit]
        return []

    def count(self, entity, filters=None):
        filters = filters or {}
        rows = self.search(entity, filters, limit=500)
        return len(rows)


class ConversationOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.service = PersistenceService(FakeRepo())

    def test_get_conversation_is_scoped_when_owner_is_supplied(self):
        self.assertIsNotNone(
            self.service.get_conversation("conv_1", owner="owner@example.test")
        )
        self.assertIsNone(
            self.service.get_conversation("conv_1", owner="other@example.test")
        )
        self.assertIsNotNone(
            self.service.get_conversation("conv_1")
        )

    def test_message_reads_reject_cross_owner_access(self):
        rows = self.service.list_messages(
            "conv_1", owner="owner@example.test"
        )
        self.assertEqual(len(rows), 1)

        with self.assertRaises(NotFoundError):
            self.service.list_messages(
                "conv_1", owner="other@example.test"
            )

        self.assertEqual(
            self.service.count_messages("conv_1", owner="owner@example.test"),
            1,
        )
        with self.assertRaises(NotFoundError):
            self.service.count_messages(
                "conv_1", owner="other@example.test"
            )


if __name__ == "__main__":
    unittest.main()
