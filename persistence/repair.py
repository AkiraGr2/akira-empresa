"""F12 Repair Engine v1: state machine and safe action catalog.

This module defines the lifecycle contract only. Persistence is handled by
PersistenceService so repair state remains authoritative and versioned.
"""

REPAIR_STAGES = (
    "detected",
    "diagnosed",
    "isolated",
    "proposed",
    "sandboxed",
    "tested",
    "evaluated",
    "approved",
    "applied",
    "discarded",
    "failed",
)

REPAIR_STAGE_TRANSITIONS = {
    "detected": {"diagnosed", "failed", "discarded"},
    "diagnosed": {"isolated", "failed", "discarded"},
    "isolated": {"proposed", "failed", "discarded"},
    "proposed": {"sandboxed", "failed", "discarded"},
    "sandboxed": {"tested", "failed", "discarded"},
    "tested": {"evaluated", "failed", "discarded"},
    "evaluated": {"approved", "discarded", "failed"},
    "approved": {"applied", "discarded", "failed"},
    "applied": set(),
    "discarded": set(),
    "failed": set(),
}

REPAIR_ACTIONS = {
    "disable_selftest_agent": {
        "description": "Deshabilita el agente reservado de autopruebas.",
        "mutating": True,
        "safe_scope": "system",
    },
    "detach_orphan_selftest_task": {
        "description": "Retira mission_id de una task sintética selftest con misión inexistente.",
        "mutating": True,
        "safe_scope": "system",
    },
    "recover_stale_selftest_task": {
        "description": "Marca como failed una task selftest que quedó running sin actividad.",
        "mutating": True,
        "safe_scope": "system",
    },
}

def repair_action_allowed(action_type):
    return action_type in REPAIR_ACTIONS

def validate_stage_transition(current, new):
    allowed = REPAIR_STAGE_TRANSITIONS.get(current)
    if allowed is None or new not in allowed:
        raise ValueError(f"transición de repair inválida: {current} -> {new}")
