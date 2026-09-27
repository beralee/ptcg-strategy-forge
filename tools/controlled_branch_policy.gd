extends RefCounted
# Research harness only: not packaged, not registered as production authority.
# Preserve the original rule audit; intervention labels use a separate qualifier.
var inner: Variant
var request: Dictionary = {}
var applied := 0
var failure := ""

func requires_competitive_frame_v2() -> bool:
	return inner.requires_competitive_frame_v2()

func expected_selection_source() -> String:
	return str(inner.expected_selection_source()) if inner.has_method("expected_selection_source") else "restricted_ir_same_window"

func audit_snapshot() -> Dictionary:
	return inner.audit_snapshot()

func enable_turn_program_shadow(enabled: bool) -> void:
	if inner.has_method("enable_turn_program_shadow"):
		inner.enable_turn_program_shadow(enabled)

func close() -> void:
	inner.close()

static func normalized(value: Variant) -> Variant:
	if value is float and is_finite(value) and value == int(value):
		return int(value)
	if value is Dictionary:
		var result := {}
		for key: Variant in value:
			result[key] = normalized(value[key])
		return result
	if value is Array:
		var result: Array = []
		for item: Variant in value:
			result.append(normalized(item))
		return result
	return value

static func semantic(option: Dictionary) -> Dictionary:
	var value: Dictionary = normalized(option)
	value.erase("index")
	value.erase("option_fingerprint")
	return value

static func bind(frame: Dictionary, response: Dictionary, target: Dictionary) -> int:
	var frontier: Dictionary = response.get("decision_audit", {}).get("model_frontier", {})
	var source: Dictionary = frame.get("source", {})
	var counts: Dictionary = frame.get("select_semantics", {})
	var rule: Array = response.get("selected_indexes", [])
	if not response.get("ok", false) or not frontier.get("enabled", false) or frontier.get("profile_id") != "ptcgdap-base-model-frontier-v1" or counts.get("min_count") != 1 or counts.get("max_count") != 1 or rule.size() != 1:
		return -1
	for key: String in ["public_observation_hash", "window_id"]:
		if not source.has(key) or source[key] != frontier.get(key) or source[key] != target.get(key):
			return -1
	var options: Array = frame.get("options", [])
	var indexes: Array = frontier.get("indexes", [])
	if indexes.size() < 2 or not rule[0] in indexes:
		return -1
	var seen := {}
	for value: Variant in indexes:
		if not (value is int or value is float) or float(value) != int(value) or value < 0 or value >= options.size() or seen.has(value):
			return -1
		seen[value] = true
	var found := -1
	for n: int in options.size():
		if semantic(options[n]) == semantic(target.get("option", {})):
			if found != -1:
				return -1
			found = n
	return found if found in indexes else -1

func select(frame: Dictionary) -> Dictionary:
	var response: Dictionary = inner.select(frame)
	if request.is_empty() or applied > 0:
		return response
	var source: Dictionary = frame.get("source", {})
	if source.get("window_id") != request.get("window_id"):
		return response
	var index := bind(frame, response, request)
	if index < 0:
		failure = "branch_semantic_binding_failed"
		return {"ok": false, "error_code": failure}
	applied += 1
	response["selected_indexes"] = [index]
	response["decision_audit"]["research_intervention"] = {"ordinal": applied, "request": request.duplicate(true)}
	return response
