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

    def test_runtime_agent_checks_accept_current_contract_and_reject_drift(self):
        from agent_contracts import AGENT_CONTRACTS
        from persistence.tool_catalog import CANONICAL_TOOL_NAMES
        agents = {name: {'name': name, **contract} for name, contract in AGENT_CONTRACTS.items()}
        required = ('session_auth', 'persistent_memory', 'memory_recall', 'learning_persistent',
                    'graph_persistent', 'selftest_capability', 'evolution_engine_v1')
        service = Mock()
        service.get_agent_by_name.side_effect = agents.get
        service.get_tool_by_name.return_value = {'permissions': ['owner'], 'status': 'available'}
        service.self_knowledge_snapshot.side_effect = lambda **kwargs: {
            'identity': {'name': 'Akira', 'root_schema_version': 'identity_root.v1'},
            'capabilities': [{'name': n, 'effective_state': 'verified'} for n in required],
            'agents': list(agents.values()), 'tools': [{'name': n} for n in CANONICAL_TOOL_NAMES]}
        tree = ast.parse(Path('persistence/selftest.py').read_text(encoding='utf-8'))
        for name in ('t_specialized_agents_persistence', 't_self_knowledge_snapshot'):
            fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
            env = {'service': service, '_res': lambda name, ok, detail: {'ok': ok, 'detail': detail}}
            exec(compile(ast.Module(body=[fn], type_ignores=[]), '<selftest>', 'exec'), env)
            self.assertTrue(env[name]() ['ok'])
            original = agents['developer']
            agents['developer'] = {**original, 'allowed_tools': ['github_repo_read']}
            self.assertFalse(env[name]() ['ok'])
            agents['developer'] = original


if __name__ == '__main__':
    unittest.main()
