import ast
import asyncio
from pathlib import Path
import unittest
from unittest.mock import Mock, AsyncMock
from persistence.model_registry import GROQ_FALLBACK_MODELS, model_registry_snapshot


class StartupRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_database_still_seeds_once_after_old_deadline(self):
        tree = ast.parse(Path('nexus.py').read_text(encoding='utf-8'))
        fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                  and n.name == '_initialize_runtime_registries')
        service = object()
        seed, cleanup = Mock(), Mock()
        async def inline_thread(fn, *args):
            return fn(*args)
        runtime = Mock(sleep=AsyncMock(), to_thread=inline_thread)
        env = {'asyncio': runtime, '_persistence_service': Mock(side_effect=[None]*30+[service]),
               '_seed_tools_and_agents': seed, '_cleanup_orphan_missions': cleanup}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<startup>', 'exec'), env)
        await env['_initialize_runtime_registries']()
        self.assertEqual(runtime.sleep.await_count, 30)
        seed.assert_called_once_with()
        cleanup.assert_called_once_with(service)

    def test_all_runtime_fallbacks_are_in_registry_without_duplicates(self):
        rows = model_registry_snapshot()['routes']
        keys = [(r['provider'], r['model'], r['role']) for r in rows]
        self.assertEqual(len(keys), len(set(keys)))
        for model in GROQ_FALLBACK_MODELS:
            self.assertIn(('groq', model, 'fallback'), keys)
        self.assertIn(('groq', 'llama-3.1-8b-instant', 'voice_fast'), keys)


if __name__ == '__main__':
    unittest.main()
