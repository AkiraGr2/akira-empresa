"""Regression for tools added to the production agents without contract updates."""
import ast
from pathlib import Path
import unittest
from agent_contracts import AGENT_CONTRACTS, validate_agent_definition, validate_agent_result


class AlignmentTests(unittest.TestCase):
    def test_production_seed_matches_contract_and_exclusions(self):
        tree = ast.parse(Path('nexus.py').read_text(encoding='utf-8'))
        seeds = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == '_AGENT_SEED' for t in n.targets))
        for seed in seeds:
            self.assertEqual(validate_agent_definition({**seed, 'status': 'idle'}), (True, []))
            contract = AGENT_CONTRACTS[seed['name']]
            self.assertFalse(set(contract['allowed_tools']) & set(contract['forbidden_tools']))

    def test_web_fetch_requires_actual_content_and_success(self):
        for agent in ('researcher', 'learner', 'developer'):
            good = {'ok': True, 'result': {'ok': True, 'url': 'https://example.org', 'content': 'Evidence'}}
            self.assertTrue(validate_agent_result(agent, 'web_fetch', good)[0])
            for bad in ({'ok': True}, {'ok': True, 'result': {'ok': True, 'url': 'https://example.org', 'content': ''}}):
                self.assertFalse(validate_agent_result(agent, 'web_fetch', bad)[0])

    def test_audit_result_must_be_coherent(self):
        for agent in ('developer', 'tester', 'reviewer'):
            good = {'ok': True, 'valid': True, 'language': 'python', 'syntax_errors': []}
            self.assertTrue(validate_agent_result(agent, 'code_syntax_audit', good)[0])
            self.assertFalse(validate_agent_result(agent, 'code_syntax_audit', {'ok': True})[0])
            self.assertFalse(validate_agent_result(agent, 'code_syntax_audit', {**good, 'valid': False})[0])
            bad_source = {**good, 'valid': False, 'syntax_errors': [{'line': 1}]}
            self.assertTrue(validate_agent_result(agent, 'code_syntax_audit', bad_source)[0])

    def test_new_tools_do_not_grant_other_agents_access(self):
        self.assertFalse(validate_agent_result('memorizer', 'web_fetch', {'ok': True})[0])
        self.assertFalse(validate_agent_result('researcher', 'code_syntax_audit', {'ok': True})[0])


if __name__ == '__main__':
    unittest.main()
