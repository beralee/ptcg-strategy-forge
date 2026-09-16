"""Thread-local observation of predicate calls made by the pinned policy owner.

This does not replace policy functions, alter decisions, or re-evaluate a window.
Only public scalar facts from validated predicate calls are retained.
"""
from contextlib import contextmanager
import copy
import sys
import threading


@contextmanager
def capture_predicates(adapter):
    from scripts.ai.ptcgdap import public_deck_adapter as raw_owner
    from scripts.ai.ptcgdap import competitive_policy_v2 as competitive_owner
    rows = []
    thread_id = threading.get_ident()
    raw_code = raw_owner._matches.__code__
    competitive_code = competitive_owner._matches.__code__
    def observe(frame, event, result):
        if threading.get_ident() != thread_id:
            return
        local = frame.f_locals
        if frame.f_code is raw_code:
            predicate = local["predicate"]
            rules = [(i, r) for i, r in enumerate(adapter.get("rules", [])) if r.get("predicate") == predicate]
            public = local["context"]
            option = local["option"]
            bound = raw_owner._thaw(local["adapter"]._local_context)
            if bound is None:
                return
            actual = {"select_type_raw": public["select_semantics"]["select_type_raw"],
                      "select_context_raw": public["select_semantics"]["select_context_raw"],
                      "option_type_raw": option["raw"].get("type"), "option_player_index": option["raw"].get("playerIndex"),
                      "option_card_id": bound["options"][option["index"]]["local_card_uid"],
                      "acting_hand_card_id": sorted({r["local_card_uid"] for r in bound["acting_hand"]}),
                      "acting_active_card_id": sorted({r["local_card_uid"] for r in bound["acting_active"]})}
            conditions = [{"field": key, "expected": value, "actual": actual[key],
                           "matched": value in actual[key] if key in {"acting_hand_card_id", "acting_active_card_id"} else value == actual[key]}
                          for key, value in predicate.items() if value is not None]
        else:
            rules = [(i, r) for i, r in enumerate(adapter.get("rules", [])) if r.get("when") == local["conditions"]]
            option = local["option"]
            conditions = []
            for condition in local["conditions"]:
                actual = competitive_owner._fact(condition["fact"], local["frame"], option,
                                                 local["goal"], local["threat"], condition["card_uid"])
                conditions.append({"field": condition["fact"], "operator": condition["op"],
                                   "expected": copy.deepcopy(condition["value"]), "actual": copy.deepcopy(actual),
                                   "matched": competitive_owner._compare(actual, condition["op"], condition["value"])})
        for index, rule in rules:
            rows.append({"rule_id": rule["rule_id"], "json_pointer": f"/rules/{index}",
                         "option_index": option["index"] if option is not None else None,
                         "matched": bool(result), "conditions": conditions})
    monitoring = sys.monitoring
    tool_id = None
    for candidate in (5, 4):
        try:
            monitoring.use_tool_id(candidate, "forge-predicate-diagnostics")
            tool_id = candidate
            break
        except ValueError:
            continue
    if tool_id is None:
        raise ValueError("diagnostic_monitor_unavailable")
    def returned(code, offset, value):
        observe(sys._getframe(1), "return", value)
    try:
        monitoring.register_callback(tool_id, monitoring.events.PY_RETURN, returned)
        monitoring.set_local_events(tool_id, raw_code, monitoring.events.PY_RETURN)
        monitoring.set_local_events(tool_id, competitive_code, monitoring.events.PY_RETURN)
        yield rows
    finally:
        monitoring.set_local_events(tool_id, raw_code, 0)
        monitoring.set_local_events(tool_id, competitive_code, 0)
        monitoring.register_callback(tool_id, monitoring.events.PY_RETURN, None)
        monitoring.free_tool_id(tool_id)
