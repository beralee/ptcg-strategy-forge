extends RefCounted
## Called by Base only after its closed public-frame validator has accepted.
## Shares the generated contract and public card bytes with the Python path.

static func canonical(value: Variant) -> String:
	return JSON.stringify(integer_numbers(value), "", true, true)

static func integer_numbers(value: Variant) -> Variant:
	if value is float and value == floor(value): return int(value)
	if value is Dictionary:
		var out: Dictionary = {}
		for key: Variant in value: out[key] = integer_numbers(value[key])
		return out
	if value is Array:
		var out: Array = []
		for child: Variant in value: out.append(integer_numbers(child))
		return out
	return value

static func paths(value: Variant, path: String = "") -> Array:
	var out: Array = [path]
	if value is Dictionary:
		var keys: Array = value.keys(); keys.sort()
		for key: String in keys: out.append_array(paths(value[key], path + "/" + key))
	elif value is Array:
		for index: int in range(value.size()): out.append_array(paths(value[index], path + "/" + str(index)))
	return out

static func uids(value: Variant, found: Dictionary) -> void:
	if value is Dictionary:
		for key: String in value:
			var child: Variant = value[key]
			if key.ends_with("_uid") and child is String: found[child] = true
			elif key.ends_with("_uids") and child is Array:
				for uid: Variant in child:
					if uid is String: found[uid] = true
			else: uids(child, found)
	elif value is Array:
		for child: Variant in value: uids(child, found)

static func capture_validated(frame: Dictionary, contract: Dictionary, card_root: String, plan: Variant = null) -> Dictionary:
	if plan != null:
		if not plan is Dictionary: return {"accepted":false,"error_code":"base_input_plan_invalid"}
		for key: String in plan:
			if key not in contract.plan_keys or typeof(plan[key]) not in [TYPE_STRING,TYPE_INT,TYPE_NIL]:
				return {"accepted":false,"error_code":"base_input_plan_invalid"}
		if plan.has("turn") and typeof(plan.turn) != TYPE_INT: return {"accepted":false,"error_code":"base_input_plan_invalid"}
		if plan.has("target_entity") and typeof(plan.target_entity) not in [TYPE_INT,TYPE_NIL]: return {"accepted":false,"error_code":"base_input_plan_invalid"}
	var state: Dictionary = frame.public_state.duplicate(true)
	var missing: Array = []
	if not state.has("decision"): missing.append("/public_state/decision")
	if not state.self.has("turn"): missing.append("/public_state/self/turn")
	for side: String in ["self", "opponent"]:
		for zone: String in ["active", "bench"]:
			for index: int in range(state[side][zone].size()):
				for key: String in contract.slot_allowed:
					if not state[side][zone][index].has(key):
						missing.append("/public_state/%s/%s/%s/%s" % [side,zone,index,key])
	var found: Dictionary = {}; uids(frame, found)
	var identities: Array = found.keys(); identities.sort()
	var cards: Array = []; var unknown: Array = []
	for uid: String in identities:
		var path: String = card_root.path_join(uid + ".json")
		if not FileAccess.file_exists(path):
			cards.append({"card_uid":uid,"known":false,"source_sha256":null,"facts":null})
			unknown.append(uid); continue
		var file := FileAccess.open(path,FileAccess.READ)
		if file == null: return {"accepted":false,"error_code":"base_input_card_read"}
		var bytes := file.get_buffer(file.get_length()); file.close()
		var card: Variant = JSON.parse_string(bytes.get_string_from_utf8())
		if not card is Dictionary or str(card.get("set_code")) + "_" + str(card.get("card_index")) != uid:
			return {"accepted":false,"error_code":"base_input_card_identity"}
		var hash_context := HashingContext.new(); hash_context.start(HashingContext.HASH_SHA256)
		hash_context.update(bytes)
		var facts: Dictionary = {}
		for key: String in contract.printed_keys:
			if card.has(key): facts[key] = card[key]
		cards.append({"card_uid":uid,"known":true,"source_sha256":hash_context.finish().hex_encode().to_upper(),"facts":integer_numbers(facts)})
	var options: Array = []
	for option: Dictionary in frame.options:
		var semantic := option.duplicate(true); semantic.erase("index")
		options.append({"semantic":semantic,"key":canonical(semantic),"index":option.index})
	options.sort_custom(func(a: Dictionary,b: Dictionary) -> bool:
		return a.key < b.key if a.key != b.key else a.index < b.index)
	var semantic_options: Array = []; var indexes: Array = []
	for option: Dictionary in options:
		semantic_options.append(option.semantic); indexes.append(option.index)
	var contract_hash := canonical(contract).sha256_text().to_upper()
	var model: Dictionary = {"profile":contract.profile,"contract_sha256":contract_hash,
		"seat":frame.seat,"prompt_kind":frame.prompt_kind,"public_state":state,
		"select_semantics":frame.select_semantics.duplicate(true),"options":semantic_options,"printed_cards":cards,"plan":plan}
	model["presence"] = paths(model)
	var coverage: Dictionary = {"profile":contract.profile,"contract_sha256":contract_hash,
		"ready":missing.is_empty() and unknown.is_empty(),"missing":missing,"unknown_card_uids":unknown,
		"scope":"all admitted fields and printed card metadata; not complete game semantics",
		"limitations":contract.limitations.duplicate(true)}
	return {"accepted":true,"error_code":"","model":model,"coverage":coverage,
		"option_indexes":indexes,"input_sha256":canonical(model).sha256_text().to_upper(),
		"binding":{"public_observation_hash":frame.source.public_observation_hash,
			"window_id":frame.source.window_id,"sequence":frame.sequence,"seat":frame.seat}}
