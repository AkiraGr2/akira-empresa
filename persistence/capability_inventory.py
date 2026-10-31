"""Display inventory; source presence never confers runtime verification."""
import json
from pathlib import Path


def capability_inventory(registry):
    catalog = json.loads((Path(__file__).resolve().parents[1] / 'data/capability_inventory.json').read_text(encoding='utf-8'))
    items = catalog['items']
    ids = [item['id'] for item in items]
    if len(ids) != len(set(ids)) or sum(x['origin'] == 'historical_60' for x in items) != 60:
        raise ValueError('invalid_inventory')
    # Runtime registry represents broader contracts; do not transfer its status
    # to individual UI features without a feature-specific verification.
    summary = {'total': len(items), 'historical': 60,
               'added': sum(x['origin'] == 'added' for x in items),
               'runtime_contracts': len(registry),
               'verified_contracts': sum(x.get('effective_state') == 'verified' for x in registry)}
    return {'version': catalog['version'], 'items': items, 'summary': summary,
            'runtime_registry': registry}


def inventory_summary(registry):
    s = capability_inventory(registry)['summary']
    return (f"{s['total']} elementos inventariados ({s['historical']} histÃ³ricas + {s['added']} nuevas); "
            f"{s['verified_contracts']} de {s['runtime_contracts']} contratos principales verificados. "
            "Las funciones individuales requieren evidencia propia.")
