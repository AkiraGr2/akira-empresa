        return _res(name, bool(ok and verified), f"resultado={outcome}; effective_state={effective}; configured={configured}")

    def t_capability_persistence():
        name = "TEST_CAPABILITY_PERSISTENCE"

        # El registry canonico ya contiene esta capability. El selftest debe
        # comprobar su roundtrip sin intentar redefinir ni duplicar la entrada.
        rows = service.list_capabilities(filters={"name": "selftest_capability"}, limit=1)
        if not rows:
            return _res(name, False, "capability canonica selftest_capability no existe")
        cap = rows[0]
        evidence = [{
            "type": "selftest",
            "title": "Capability persistence roundtrip",
            "reference": "selftest:capability:v1",
            "summary": "Capability y verification persistidas y releidas.",
            "hash": "",
        }]
        event = {
            "event_type": "verification",
            "test_key": "capability_persistence",
            "test_version": "v1",
            "result": "pass",
            "evidence": evidence,
            "environment": {"runtime": "selftest"},
            "dependency_snapshot": [],
            "runtime_version": "selftest",
            "build_ref": "selftest",
            "actor": "selftest",
            "executor": "selftest",
            "evaluator": "system",
        }
        try:
            vr = service.record_capability_verification(
                cap["id"], event, actor="selftest",
                idempotency_key="selftest:capability:verification:v1",
            )
        except Exception as e:
            return _res(
                name,
                False,
                f"record_capability_verification fallo: {type(e).__name__}: {str(e)[:300]}",
            )
        cap2 = service.get_capability(cap["id"])
        rows = service.get_capability_verifications(cap["id"], limit=10)
        try:
            repeat = service.record_capability_verification(
                cap["id"], event, actor="selftest",
                idempotency_key="selftest:capability:verification:v1",
            )
        except Exception as e:
            return _res(name, False, f"reintento idempotente fallo: {type(e).__name__}: {str(e)[:300]}")
        ok = (
            cap2 is not None
            and cap2["verification_state"] == "verified"
            and bool(rows)
            and rows[0]["state_after"]["verification_state"] == "verified"
            and repeat["outcome"] == "already_synced"
            and vr["effective_state"] == "verified"
        )
        detail = (
            f"verificationes persistidas={len(rows)}; "
            f"repeticion={repeat['outcome']}; estado={cap2 and cap2.get('verification_state')}"
        )
        return _res(name, ok, detail)

    def t_capability_verification_append_only():
        name = "TEST_CAPABILITY_VERIFICATION_APPEND_ONLY"
        rows = service.list_capabilities(filters={"name": "selftest_capability"}, limit=1)
        if not rows:
            return _res(name, False, "fixture selftest_capability no existe")
        cap = rows[0]
        verifications = service.get_capability_verifications(cap["id"], limit=10)
        if not verifications: