
def _validate_self_model_repairs(value):
    allowed = {
        "id", "target", "reason", "status", "stage", "action_type",
        "owner_scope", "proposed_at", "started_at", "completed_at",
        "evidence", "result", "diagnosis", "proposal", "sandbox",
        "tests", "evaluation",
    }
    items = _self_model_record_list("repairs", value, allowed)
    out = []
    v1_fields = {"stage", "action_type", "owner_scope", "diagnosis", "proposal", "sandbox", "tests", "evaluation"}

    for item in items:
        status = _self_model_text("repairs.status", item.get("status"), 32)
        if status not in _SELF_MODEL_REPAIR_STATUSES:
            raise ValidationError(f"repairs.status invalido: {status!r}")

        # Legacy repair records remain readable. New Repair Engine v1 records
        # must carry the complete explicit lifecycle/action contract.
        has_v1_fields = bool(v1_fields.intersection(item))
        if not has_v1_fields:
            normalized = {
                "id": _self_model_text("repairs.id", item.get("id"), 128),
                "target": _self_model_text("repairs.target", item.get("target"), 256),
                "reason": _self_model_text("repairs.reason", item.get("reason"), 2000),
                "status": status,
                "proposed_at": _self_model_iso("repairs.proposed_at", item.get("proposed_at")),
                "evidence": item.get("evidence", []),
                "result": _self_model_text("repairs.result", item.get("result", ""), 2000, allow_empty=True),
            }
            if status in ("running", "completed", "failed") and item.get("started_at") is None:
                raise ValidationError("repairs.started_at requerido para status activo/final")
            if status == "completed" and item.get("completed_at") is None:
                raise ValidationError("repairs.completed_at requerido cuando status=completed")
            if status not in ("completed", "failed", "cancelled") and item.get("completed_at") is not None:
                raise ValidationError("repairs.completed_at solo aplica a estados finalizados")
            for key in ("started_at", "completed_at"):
                if key in item and item.get(key) is not None:
                    normalized[key] = _self_model_iso(f"repairs.{key}", item[key])
            if not isinstance(normalized["evidence"], list) or len(normalized["evidence"]) > 10:
                raise ValidationError("repairs.evidence debe ser lista de maximo 10 elementos")
            normalized["evidence"] = [_self_model_text("repairs.evidence", e, 500) for e in normalized["evidence"]]
            out.append(normalized)
            continue

        required_v1 = {"stage", "action_type", "owner_scope"}
        missing_v1 = sorted(required_v1 - set(item))
        if missing_v1:
            raise ValidationError(f"repair v1 incompleta: {missing_v1}")

        stage = _self_model_text("repairs.stage", item.get("stage"), 32)
        if stage not in _SELF_MODEL_REPAIR_STAGES:
            raise ValidationError(f"repairs.stage invalido: {stage!r}")
        action_type = _self_model_text("repairs.action_type", item.get("action_type"), 64)
        if action_type not in _SELF_MODEL_REPAIR_ACTIONS:
            raise ValidationError(f"repairs.action_type invalido: {action_type!r}")
        owner_scope = _self_model_text("repairs.owner_scope", item.get("owner_scope"), 128)
        normalized = {
            "id": _self_model_text("repairs.id", item.get("id"), 128),
            "target": _self_model_text("repairs.target", item.get("target"), 256),
            "reason": _self_model_text("repairs.reason", item.get("reason"), 2000),
            "status": status,
            "stage": stage,
            "action_type": action_type,
            "owner_scope": owner_scope,
            "proposed_at": _self_model_iso("repairs.proposed_at", item.get("proposed_at")),
            "evidence": item.get("evidence", []),
            "result": _self_model_text("repairs.result", item.get("result", ""), 2000, allow_empty=True),
        }
        for field in ("diagnosis", "proposal", "sandbox", "tests", "evaluation"):
            if field in item:
                value_obj = item[field]
                if not isinstance(value_obj, (dict, list, str)):
                    raise ValidationError(f"repairs.{field} debe ser objeto, lista o texto")
                normalized[field] = value_obj
        if status in ("running", "completed", "failed") and item.get("started_at") is None:
            raise ValidationError("repairs.started_at requerido para status activo/final")
        if status == "completed" and item.get("completed_at") is None:
            raise ValidationError("repairs.completed_at requerido cuando status=completed")
        if status not in ("completed", "failed", "cancelled") and item.get("completed_at") is not None:
            raise ValidationError("repairs.completed_at solo aplica a estados finalizados")
        for key in ("started_at", "completed_at"):
            if key in item and item.get(key) is not None:
                normalized[key] = _self_model_iso(f"repairs.{key}", item[key])
        if not isinstance(normalized["evidence"], list) or len(normalized["evidence"]) > 10:
            raise ValidationError("repairs.evidence debe ser lista de maximo 10 elementos")
        normalized["evidence"] = [_self_model_text("repairs.evidence", e, 500) for e in normalized["evidence"]]
        out.append(normalized)
    return out

def _validate_self_model_evolution(value):
    allowed = {"id", "proposal", "rationale", "status", "proposed_at", "implemented_at", "evidence"}
    items = _self_model_record_list("evolution", value, allowed)
    out = []
    for item in items: