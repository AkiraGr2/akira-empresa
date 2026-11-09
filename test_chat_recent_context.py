"""Execute the real formatter without starting network/provider clients."""
import ast
from pathlib import Path
import unittest

from persistence.service import PersistenceService, NotFoundError
from test_conversation_ownership import FakeRepo

tree = ast.parse(Path(__file__).with_name('nexus.py').read_text(encoding='utf-8'))
node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_format_conversation_context')
namespace = {}
exec(compile(ast.Module(body=[node], type_ignores=[]), 'nexus.py', 'exec'), namespace)
format_context = namespace['_format_conversation_context']


class OrderedRepo(FakeRepo):
    def search(self, entity, filters=None, limit=50, offset=0, order_by='created_at', descending=True):
        if entity != 'conversation_messages':
            return super().search(entity, filters, limit, offset, order_by, descending)
        rows = [r for r in self.messages if all(r.get(k) == v for k, v in (filters or {}).items())]
        return sorted(rows, key=lambda r: r['created_at'], reverse=descending)[offset:offset + limit]


class RecentContextTests(unittest.TestCase):
    def setUp(self):
        self.repo = OrderedRepo()
        self.repo.messages = [dict(conversation_id='conv_1', role='user' if i % 2 == 0 else 'assistant',
                                   content=f'message-{i}', created_at=i) for i in range(603)]
        self.service = PersistenceService(self.repo)

    def test_recent_context_beyond_first_500_and_no_current_duplicate(self):
        result = format_context(self.service, 'conv_1', 'message-602', owner='owner@example.test')
        self.assertIn('message-601', result)
        self.assertIn('message-582', result)
        self.assertNotIn('message-602', result)
        self.assertNotIn('message-499', result)
        self.assertLess(result.index('message-582'), result.index('message-601'))

    def test_budget_keeps_latest_messages(self):
        self.repo.messages[-4]['content'] = 'old-answer-' * 400
        result = format_context(self.service, 'conv_1', 'message-602', owner='owner@example.test', max_chars=70)
        self.assertIn('message-601', result)
        self.assertIn('message-600', result)
        self.assertNotIn('old-answer', result)

    def test_other_account_cannot_read_context(self):
        with self.assertRaises(NotFoundError):
            self.service.list_recent_messages('conv_1', owner='other@example.test')
        self.assertEqual(format_context(self.service, 'conv_1', '', owner='other@example.test'), '')

    def test_empty_new_chat_has_no_other_chat_context(self):
        self.assertEqual(format_context(self.service, None, '', owner='owner@example.test'), '')
        self.repo.messages = []
        self.assertEqual(format_context(self.service, 'conv_1', '', owner='owner@example.test'), '')


if __name__ == '__main__':
    unittest.main()
