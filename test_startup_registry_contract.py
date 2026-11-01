import ast
import asyncio
from pathlib import Path
import unittest
from unittest.mock import Mock, AsyncMock
from persistence.model_registry import GROQ_FALLBACK_MODELS, model_registry_snapshot


class StartupRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_database_still_cleans_up_after_old_deadline(self):
        tree = ast.parse(Path('nexus.py').read_text(encoding='utf-8'))
        fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                  and n.name == '_cleanup_when_persistence_ready')
        service = object()
        seed, cleanup = Mock(), Mock()
        async def inline_thread(fn, *args):
            return fn(*args)
        runtime = Mock(sleep=AsyncMock(), to_thread=inline_thread)
        env = {'asyncio': runtime, '_persistence_service': Mock(side_effect=[None]*30+[service]),
               '_seed_tools_and_agents': seed, '_cleanup_orphan_missions': cleanup}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), '<startup>', 'exec'), env)
        await env['_cleanup_when_persistence_ready']()
        self.assertEqual(runtime.sleep.await_count, 30)
        seed.assert_not_called()
        cleanup.assert_called_once_with(service)

    def test_all_production_tool_seeds_validate_and_match_registry(self):
        from persistence.core import validate_tool
        from persistence.tool_catalog import CANONICAL_TOOL_NAMES
        tree = ast.parse(Path('nexus.py').read_text(encoding='utf-8'))
        seeds = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == '_TOOL_SEED' for t in n.targets))
        self.assertEqual([r['name'] for r in seeds], list(CANONICAL_TOOL_NAMES))
        for row in seeds:
            self.assertEqual(validate_tool(row)['name'], row['name'])

    def test_registry_callback_completes_before_selftest(self):
        from unittest.mock import patch
        from persistence import runtime
        service = Mock()
        service.handle_runtime_build_change.return_value = {'outcome': 'unchanged', 'invalidated': []}
        order = []
        def seed():
            self.assertIs(runtime.STATE['service'], service)
            order.append('seed')
        def tests(*args, **kwargs):
            self.assertEqual(order, ['seed'])
            order.append('tests')
            return []
        with patch.dict(runtime.STATE, runtime.STATE.copy()), patch.dict('os.environ', {'AKIRA_PERSISTENCE_SELFTEST': '1'}), \
             patch.object(runtime, 'PersistenceService', return_value=service), \
             patch.object(runtime, '_seed_capabilities'), patch.object(runtime, 'runtime_build_ref', return_value='test'), \
             patch.object(runtime, 'run_logic_tests', side_effect=tests), \
             patch.object(runtime, 'run_restart_probe', return_value={'test': 'restart', 'status': 'PASS'}), \
             patch.object(runtime, '_start_self_knowledge_observer'):
            runtime.boot(backend_factory=lambda: (Mock(), Mock()), on_ready=seed)
        self.assertEqual(order, ['seed', 'tests'])

    def test_all_runtime_fallbacks_are_in_registry_without_duplicates(self):
        rows = model_registry_snapshot()['routes']
        keys = [(r['provider'], r['model'], r['role']) for r in rows]
        self.assertEqual(len(keys), len(set(keys)))
        for model in GROQ_FALLBACK_MODELS:
            self.assertIn(('groq', model, 'fallback'), keys)
        self.assertIn(('groq', 'llama-3.1-8b-instant', 'voice_fast'), keys)


if __name__ == '__main__':
    unittest.main()
