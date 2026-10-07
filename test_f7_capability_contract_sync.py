from persistence.capability_catalog import COGNITIVE_CYCLE_PERSISTENT_CAPABILITY
from persistence.migrations import MIGRATIONS


def test_f7_capability_contract_sync_migration_matches_canonical_catalog():
    version, sql = next(
        (version, sql)
        for version, sql in MIGRATIONS
        if version == "052_cognitive_cycle_persistent_capability_contract_sync"
    )

    assert version == "052_cognitive_cycle_persistent_capability_contract_sync"
    assert "UPDATE public.capabilities" in sql
    assert "WHERE name = 'cognitive_cycle_persistent'" in sql
    assert "owner_scope=''owner''" in sql

    canonical_limitations = COGNITIVE_CYCLE_PERSISTENT_CAPABILITY["limitations"]
    assert len(canonical_limitations) == 3
    for limitation in canonical_limitations:
        assert limitation.replace("'", "''") in sql
