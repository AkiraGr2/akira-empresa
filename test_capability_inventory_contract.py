import unittest
from unittest.mock import Mock
from persistence.capability_inventory import capability_inventory, inventory_summary


class InventoryTests(unittest.TestCase):
    def test_bootstrap_cannot_self_certify_or_hide_later_entries(self):
        from persistence.runtime import _seed_capabilities
        from persistence.capability_catalog import BASE_CAPABILITIES
        service = Mock()
        service.create_capability.side_effect = [RuntimeError('historical conflict')] + [None] * (len(BASE_CAPABILITIES) - 1)
        _seed_capabilities(service)
        self.assertEqual(service.create_capability.call_count, len(BASE_CAPABILITIES))
        for call in service.create_capability.call_args_list:
            self.assertEqual(call.args[0]['verification_state'], 'unverified')

    def test_all_catalog_entries_can_be_registered_without_fabricated_evidence(self):
        from persistence.runtime import _seed_capabilities
        from persistence.service import PersistenceService
        from persistence.capability_catalog import BASE_CAPABILITIES
        from test_capability_engine_contract import _CapabilityRepo
        repo = _CapabilityRepo()
        service = PersistenceService(repo)
        _seed_capabilities(service)
        self.assertEqual({r['name'] for r in repo.rows['capabilities']}, {r['name'] for r in BASE_CAPABILITIES})
        self.assertTrue(all(r['verification_state'] == 'unverified' for r in repo.rows['capabilities']))
        _seed_capabilities(service)
        self.assertEqual(len(repo.rows['capabilities']), len(BASE_CAPABILITIES))

    def test_complete_history_unique_ids_and_new_features(self):
        result = capability_inventory([])
        ids = [item['id'] for item in result['items']]
        expected = ({f'V{i}' for i in range(1, 9)} | {f'F{i}' for i in range(5, 21)}
                    | {f'P{i}' for i in range(1, 5)} | {f'M{i}' for i in range(1, 18)}
                    | {'L4'} | {f'T{i}' for i in range(1, 5)} | {f'E{i}' for i in range(1, 11)})
        historical = {x['id'] for x in result['items'] if x['origin'] == 'historical_60'}
        self.assertEqual(historical, expected)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(result['summary']['total'], 72)

    def test_contract_verification_does_not_certify_features(self):
        result = capability_inventory([{'name': 'tool_registry', 'effective_state': 'verified'}])
        self.assertEqual(result['summary']['verified_contracts'], 1)
        self.assertTrue(all(x['verification'] == 'unverified' for x in result['items']))
        self.assertIn('1 de 1', inventory_summary(result['runtime_registry']))

    def test_placeholders_and_simulation_are_explicit(self):
        rows = {x['id']: x for x in capability_inventory([])['items']}
        for key in ['E7', 'E10']:
            self.assertEqual(rows[key]['implementation_evidence'], 'placeholder')
            self.assertTrue(rows[key]['limitations'])
        self.assertEqual(rows['E9']['implementation_evidence'], 'simulation')


if __name__ == '__main__':
    unittest.main()
