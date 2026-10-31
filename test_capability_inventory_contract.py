import unittest
from persistence.capability_inventory import capability_inventory, inventory_summary


class InventoryTests(unittest.TestCase):
    def test_complete_history_unique_ids_and_new_features(self):
        result = capability_inventory([])
        ids = [item['id'] for item in result['items']]
        expected = ({f'V{i}' for i in range(1, 9)} | {f'F{i}' for i in range(5, 21)}
                    | {f'P{i}' for i in range(1, 5)} | {f'M{i}' for i in range(1, 18)}
                    | {'L4'} | {f'T{i}' for i in range(1, 5)} | {f'E{i}' for i in range(1, 11)})
        historical = {x['id'] for x in result['items'] if x['origin'] == 'historical_60'}
        self.assertEqual(historical, expected)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(result['summary']['total'], 66)

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
