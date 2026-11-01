import ast
from pathlib import Path
import unittest
from unittest.mock import patch
import deep_research
import fact_checker


class NewToolDispatchTests(unittest.TestCase):
    def test_deep_research_adapter_maps_bounded_queries(self):
        with patch.object(deep_research, 'execute_deep_research', return_value={'ok': True}) as run:
            self.assertTrue(deep_research.deep_research_topic('topic', 2, 3)['ok'])
            run.assert_called_once_with('topic', max_subqueries=2)
        self.assertFalse(deep_research.deep_research_topic('topic', 9, 100)['ok'])

    def test_fact_tool_accepts_sources_keyword_without_network_search(self):
        with patch.object(fact_checker.web_engine, 'search_web') as search:
            result = fact_checker.triangulate_claim('Python programming language', sources=[])
            search.assert_not_called()
            self.assertFalse(result['verified'])
        self.assertFalse(fact_checker.triangulate_claim('claim', sources=['file:///private'])['ok'])

    def test_new_routes_reject_unauthorized_before_reading_inputs(self):
        tree = ast.parse(Path('nexus.py').read_text(encoding='utf-8'))
        names = {'api_deep_research', 'api_fact_triangulate', 'api_web_structured_extract',
                 'api_code_audit_dependencies', 'api_dossier_generate', 'api_sentinel_sweep'}
        for fn in tree.body:
            if isinstance(fn, ast.AsyncFunctionDef) and fn.name in names:
                body = ast.unparse(fn)
                self.assertLess(body.index('_require_owner(request)'), body.index('await request.json()'))
                self.assertIsInstance(fn.body[2], ast.If)
                self.assertIsInstance(fn.body[2].body[0], ast.Return)


if __name__ == '__main__':
    unittest.main()
