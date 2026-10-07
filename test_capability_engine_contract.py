import ast
import datetime as dt
from pathlib import Path
import unittest

from persistence.service import PersistenceService, ConflictError

from persistence.capability import (
    CapabilityContractError,
    apply_verification_result,
    derive_effective_state,
    effective_verification_state,
    validate_capability,
    validate_capability_state,
    validate_capability_transition,
    validate_capability_verification,
)


def state(
    implementation_state="implemented",
    verification_state="unverified",
    availability_state="available",
    maturity="experimental",
    cost_compatibility="unknown",
):
    return {
        "implementation_state": implementation_state,
        "verification_state": verification_state,
        "availability_state": availability_state,
        "maturity": maturity,
        "cost_compatibility": cost_compatibility,
    }




class _CapabilityTx:
    def __init__(self, repo):
        self.repo = repo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def create(self, entity, record):
        self.repo.rows.setdefault(entity, []).append(dict(record))
        return dict(record), True

    def update(self, entity, record_id, changes, expected_version):
        rows = self.repo.rows.get(entity, [])
        for row in rows:
            if row.get("id", row.get("key")) == record_id and row.get("version") == expected_version:
                row.update(changes)
                row["version"] = expected_version + 1
                return dict(row)
        raise ConflictError("version conflict")

    def get(self, entity, record_id):
        return self.repo.get(entity, record_id)

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        return self.repo.search(entity, filters, limit, offset, order_by, descending)

    def advisory_xact_lock(self, key):
        return None

    def append_audit(self, payload):
        return None


class _CapabilityRepo:
    def __init__(self):
        self.rows = {"capabilities": []}
        self.audit = []

    def search(self, entity, filters=None, limit=50, offset=0, order_by="created_at", descending=True):
        rows = [dict(row) for row in self.rows.get(entity, [])]
        for key, value in (filters or {}).items():
            rows = [row for row in rows if row.get(key) == value]
        rows.sort(key=lambda row: row.get(order_by) or "", reverse=descending)
        return rows[offset:offset + limit]

    def append_audit(self, payload):
        self.audit.append(dict(payload))

    def audit_search(self, actor=None, action_prefix=None, limit=20):
        rows = list(reversed(self.audit))
        if actor is not None:
            rows = [r for r in rows if r.get("actor") == actor]
        if action_prefix is not None:
            rows = [r for r in rows if str(r.get("action", "")).startswith(action_prefix)]
        return rows[:limit]

    def transaction(self):
        return _CapabilityTx(self)

    def get(self, entity, record_id):
        for row in self.rows.get(entity, []):
            if row.get("id", row.get("key")) == record_id:
                return dict(row)
        return None

    def append_audit(self, payload):
        return None


class CapabilityEngineContractTests(unittest.TestCase):
    def test_tool_registry_permission_downgrade_is_blocked(self):
        source = Path("persistence/service.py").read_text(encoding="utf-8")
        self.assertIn('if "owner" in current_permissions and "owner" not in incoming_permissions:', source)
        self.assertIn('raise ConflictError(', source)

    def test_tool_invocation_gateway_enforces_registry_contract(self):
        source = Path("nexus.py").read_text(encoding="utf-8")
        self.assertIn('tool = service.get_tool_by_name(tool_name)', source)
        self.assertIn('if tool.get("status") != "available":', source)
        self.assertIn('if "owner" in permissions and owner_scope is None:', source)
        self.assertIn('if not permissions or not permissions.intersection({"auth", "owner"}):', source)

    def test_selftest_only_verifies_sensitive_tool_permissions(self):
        source = Path("persistence/selftest.py").read_text(encoding="utf-8")
        start = source.index("def _ensure_tools(service):")
        end = source.index("def _ensure_test_agent(service):")
        block = source[start:end]
        self.assertIn('permissions != {"owner"}', block)
        self.assertNotIn("register_tool(", block)


    def test_runtime_state_uses_non_id_primary_key(self):
        source = Path("persistence/postgres.py").read_text(encoding="utf-8")
        self.assertIn('primary_key = spec.get("primary_key", "id")', source)
        core = Path("persistence/core.py").read_text(encoding="utf-8")
        self.assertIn('"primary_key": "key"', core)

    def test_runtime_build_change_invalidates_verified_capability(self):
        repo = _CapabilityRepo()
        repo.rows["runtime_state"] = []
        repo.rows["capability_verifications"] = []
        repo.rows["capabilities"].append({
            "id": "cap_runtime_test",
            "name": "runtime_test_capability",
            "description": "Capability para probar invalidacion por build.",
            "category": "general",
            "kind": "intrinsic",
            "implementation_state": "implemented",
            "verification_state": "verified",
            "availability_state": "available",
            "maturity": "experimental",
            "cost_compatibility": "unknown",
            "dependencies": [],
            "limitations": [],
            "verification_spec": {
                "method": "selftest",
                "test_key": "runtime_test",
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": ["build_change"],
                },
            },
            "provenance": {"source": "ci", "created_by": "ci"},
            "version": 2,
            "schema_version": "capability.v1",
            "last_verification_id": "capver_old",
            "last_verified_at": "2026-10-07T00:00:00+00:00",
        })
        service = PersistenceService(repo)
        first = service.handle_runtime_build_change("sha256:first", actor="selftest")
        same = service.handle_runtime_build_change("sha256:first", actor="selftest")
        changed = service.handle_runtime_build_change("sha256:second", actor="selftest")
        self.assertEqual(first["outcome"], "initialized")
        self.assertEqual(first["invalidated"], [])
        self.assertEqual(same["outcome"], "unchanged")
        self.assertEqual(changed["outcome"], "changed")
        self.assertEqual([x["name"] for x in changed["invalidated"]], ["runtime_test_capability"])
        self.assertEqual(service.get_capability("cap_runtime_test")["verification_state"], "stale")
        self.assertEqual(len(repo.rows["capability_verifications"]), 1)
        self.assertEqual(repo.rows["capability_verifications"][0]["event_type"], "invalidation")

    def test_runtime_capability_persistence_reuses_canonical_fixture(self):
        source = Path("persistence/selftest.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        fn = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "t_capability_persistence"
        )
        fn_source = ast.get_source_segment(source, fn) or ""
        self.assertIn('service.list_capabilities(filters={"name": "selftest_capability"}, limit=1)', fn_source)
        self.assertNotIn('service.create_capability(payload', fn_source)

    def test_runtime_selftest_guard_receives_local_context(self):
        source = Path("persistence/selftest.py").read_text(encoding="utf-8")
        self.assertIn("def _guard(name, fn, service, created_ids):", source)
        self.assertIn("results.append(_guard(name, fn, service, created_ids))", source)

    def test_canonical_capability_catalog_uses_valid_categories(self):
        from persistence.capability_catalog import BASE_CAPABILITIES
        for capability in BASE_CAPABILITIES:
            record = validate_capability(capability)
            self.assertIn(record["category"], {
                "identity", "memory", "knowledge", "learning", "graph", "cognitive",
                "tooling", "agents", "missions", "security", "storage", "multimedia",
                "orchestration", "repair", "evolution", "hive", "external", "general",
            })

    def test_self_model_migration_split_is_quote_safe(self):
        from persistence.migrations import MIGRATIONS

        sql = next(
            sql for version, sql in MIGRATIONS
            if version == "047_self_model_f2_coherence"
        )
        statements = [stmt.strip() for stmt in sql.split(";") if stmt.strip()]
        self.assertEqual(len(statements), 4)

        for statement in statements:
            in_single_quote = False
            i = 0
            while i < len(statement):
                if statement[i] == "'":
                    if in_single_quote and i + 1 < len(statement) and statement[i + 1] == "'":
                        i += 2
                        continue
                    in_single_quote = not in_single_quote
                i += 1
            self.assertFalse(in_single_quote, "migration 047 deja una cadena SQL entre comillas sin cerrar")

    def test_verification_timestamps_are_ordered(self):
        base = {
            "event_type": "verification",
            "test_key": "timestamp_contract",
            "test_version": "v1",
            "result": "pass",
            "evidence": [{
                "type": "ci",
                "title": "timestamp contract",
                "reference": "ci:timestamps",
                "summary": "orden temporal",
                "hash": "",
            }],
            "runtime_version": "ci",
            "build_ref": "ci",
            "actor": "ci",
            "executor": "ci",
            "evaluator": "ci",
            "started_at": "2026-10-07T01:00:00+00:00",
            "finished_at": "2026-10-06T23:59:59+00:00",
        }
        with self.assertRaises(CapabilityContractError):
            validate_capability_verification(base)

        valid = dict(base)
        valid["finished_at"] = "2026-10-07T01:00:01+00:00"
        self.assertEqual(validate_capability_verification(valid)["finished_at"], valid["finished_at"])

    def test_invalid_verification_spec_is_rejected(self):
        base = {
            "name": "invalid_spec",
            "description": "Capability con contrato incompleto.",
            "category": "general",
            "kind": "intrinsic",
            **state(),
            "dependencies": [],
            "limitations": [],
            "provenance": {"source": "ci", "created_by": "ci"},
        }
        missing_test_key = dict(base)
        missing_test_key["verification_spec"] = {
            "method": "selftest",
            "freshness_policy": {"mode": "on_change", "max_age_seconds": None, "invalidate_on": []},
        }
        with self.assertRaises(CapabilityContractError):
            validate_capability(missing_test_key)

        extra_field = dict(base)
        extra_field["verification_spec"] = {
            "method": "selftest",
            "test_key": "invalid_spec_contract",
            "freshness_policy": {"mode": "on_change", "max_age_seconds": None, "invalidate_on": []},
            "untrusted_runtime_claim": True,
        }
        with self.assertRaises(CapabilityContractError):
            validate_capability(extra_field)

    def test_valid_capability_and_effective_state(self):
        record = validate_capability({
            "name": "ci_capability_contract",
            "description": "Contrato determinista del Capability Engine.",
            "category": "general",
            "kind": "composite",
            **state(),
            "dependencies": [],
            "limitations": [],
            "verification_spec": {
                "method": "selftest",
                "test_key": "ci_capability_contract",
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": ["build_change"],
                },
            },
            "provenance": {"source": "ci", "created_by": "ci"},
        })
        self.assertEqual(record["verification_state"], "unverified")
        self.assertEqual(derive_effective_state(record), "implemented_unverified_available")

    def test_impossible_state_is_rejected(self):
        with self.assertRaises(CapabilityContractError):
            validate_capability_state(state(
                implementation_state="not_implemented",
                verification_state="verified",
                availability_state="available",
            ))

    def test_illegal_transition_is_rejected(self):
        with self.assertRaises(CapabilityContractError):
            validate_capability_transition(
                state(verification_state="unverified"),
                state(verification_state="stale"),
            )

    def test_valid_verification_transition_is_accepted(self):
        result = validate_capability_transition(
            state(verification_state="unverified"),
            state(verification_state="verified"),
        )
        self.assertEqual(result["verification_state"], "verified")

    def test_pass_verification_marks_capability_verified(self):
        current = {
            **state(),
            "verification_spec": {
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": [],
                }
            },
        }
        event = {
            "event_type": "verification",
            "result": "pass",
            "evidence": [{
                "type": "ci",
                "title": "Capability contract",
                "reference": "ci:capability",
                "summary": "Contrato aprobado por CI.",
                "hash": "",
            }],
        }
        after = apply_verification_result(current, event)
        self.assertEqual(after["verification_state"], "verified")

    def test_invalidation_turns_verified_into_stale(self):
        current = {
            **state(verification_state="verified"),
            "verification_spec": {
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": [],
                }
            },
        }
        event = {
            "event_type": "invalidation",
            "result": "fail",
            "evidence": [{
                "type": "ci",
                "title": "Invalidation",
                "reference": "ci:invalidation",
                "summary": "Cambio de dependencia.",
                "hash": "",
            }],
        }
        after = apply_verification_result(current, event)
        self.assertEqual(after["verification_state"], "stale")

    def test_time_based_freshness_expires_verified_state(self):
        verified_at = "2026-10-04T12:00:00+00:00"
        record = {
            **state(verification_state="verified"),
            "last_verified_at": verified_at,
            "verification_spec": {
                "freshness_policy": {
                    "mode": "time_based",
                    "max_age_seconds": 3600,
                    "invalidate_on": ["time"],
                }
            },
        }
        fresh_now = dt.datetime(2026, 10, 4, 12, 30, tzinfo=dt.timezone.utc)
        stale_now = dt.datetime(2026, 10, 4, 14, 1, tzinfo=dt.timezone.utc)
        self.assertEqual(effective_verification_state(record, now=fresh_now), "verified")
        self.assertEqual(effective_verification_state(record, now=stale_now), "stale")

    def test_partial_verified_effective_state_requires_available(self):
        record = {
            **state(
                implementation_state="partial",
                verification_state="verified",
                availability_state="available",
            ),
            "verification_spec": {
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": [],
                }
            },
        }
        self.assertEqual(derive_effective_state(record), "partial_verified")


    def test_capability_registry_bootstrap_is_idempotent_by_name_and_key(self):
        service = PersistenceService(_CapabilityRepo())
        payload = {
            "name": "bootstrap_capability",
            "description": "Capability de prueba para bootstrap.",
            "category": "general",
            "kind": "intrinsic",
            "implementation_state": "implemented",
            "verification_state": "unverified",
            "availability_state": "available",
            "maturity": "experimental",
            "cost_compatibility": "unknown",
            "dependencies": [],
            "limitations": [],
            "verification_spec": {
                "method": "selftest",
                "test_key": "bootstrap_capability_contract",
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": ["build_change"],
                },
            },
            "provenance": {"source": "ci", "created_by": "ci"},
        }
        first = service.create_capability(
            payload,
            actor="ci",
            idempotency_key="bootstrap:capability:bootstrap_capability:v1",
        )
        second = service.create_capability(
            payload,
            actor="ci",
            idempotency_key="bootstrap:capability:bootstrap_capability:v1",
        )
        self.assertEqual(first["outcome"], "created")
        self.assertEqual(second["outcome"], "already_synced")
        self.assertEqual(first["record"]["id"], second["record"]["id"])

    def test_capability_registry_bootstrap_ignores_dynamic_verification_state(self):
        service = PersistenceService(_CapabilityRepo())
        payload = {
            "name": "verified_bootstrap_capability",
            "description": "Capability de prueba para bootstrap.",
            "category": "general",
            "kind": "intrinsic",
            "implementation_state": "implemented",
            "verification_state": "unverified",
            "availability_state": "available",
            "maturity": "experimental",
            "cost_compatibility": "unknown",
            "dependencies": [],
            "limitations": [],
            "verification_spec": {
                "method": "selftest",
                "test_key": "verified_bootstrap_contract",
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": ["build_change"],
                },
            },
            "provenance": {"source": "ci", "created_by": "ci"},
        }
        first = service.create_capability(
            payload,
            actor="ci",
            idempotency_key="bootstrap:capability:verified:v1",
        )
        existing = dict(first["record"])
        existing.update({
            "verification_state": "verified",
            "availability_state": "available",
            "version": 2,
        })
        service.repo.rows["capabilities"][0] = existing

        second = service.create_capability(
            payload,
            actor="ci",
            idempotency_key="bootstrap:capability:verified:v1",
        )
        self.assertEqual(second["outcome"], "already_synced")
        self.assertEqual(second["record"]["id"], first["record"]["id"])
        self.assertEqual(second["record"]["verification_state"], "verified")

    def test_capability_registry_rejects_conflicting_reuse_of_name(self):
        service = PersistenceService(_CapabilityRepo())
        payload = {
            "name": "conflicting_capability",
            "description": "Definicion A.",
            "category": "general",
            "kind": "intrinsic",
            "implementation_state": "implemented",
            "verification_state": "unverified",
            "availability_state": "available",
            "maturity": "experimental",
            "cost_compatibility": "unknown",
            "dependencies": [],
            "limitations": [],
            "verification_spec": {
                "method": "selftest",
                "test_key": "conflicting_capability_contract",
                "freshness_policy": {
                    "mode": "on_change",
                    "max_age_seconds": None,
                    "invalidate_on": [],
                },
            },
            "provenance": {"source": "ci", "created_by": "ci"},
        }
        service.create_capability(
            payload,
            actor="ci",
            idempotency_key="bootstrap:conflicting_capability:v1",
        )
        changed = dict(payload)
        changed["description"] = "Definicion B."
        with self.assertRaises(ConflictError):
            service.create_capability(
                changed,
                actor="ci",
                idempotency_key="bootstrap:conflicting_capability:v2",
            )


if __name__ == "__main__":
    unittest.main()
