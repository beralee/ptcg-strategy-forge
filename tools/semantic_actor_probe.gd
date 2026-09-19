extends SceneTree
const Actor = preload("res://scripts/ai/ptcgdap/host/godot/PtcgDAPModelActor.gd")

func ints(v: Variant) -> Variant:
	if v is float: return int(v)
	if v is Array:
		var a: Array=[]
		for item: Variant in v: a.append(ints(item))
		return a
	if v is Dictionary:
		var d := {}
		for key: Variant in v: d[key]=ints(v[key])
		return d
	return v

func _initialize() -> void:
	var data: Dictionary = ints(JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0])))
	var actor := Actor.new()
	actor._policy_mode="rules_with_model"
	actor._tensor_profile_id="ptcgdap_local_semantic_actor_i32_v1"
	for uid: String in data.uids: actor._allowed_uids[uid]=true
	actor._native=ClassDB.instantiate("PtcgOrtActor")
	var loaded: Dictionary=actor._native.load_actor(FileAccess.get_file_as_bytes(data.actor))
	if not loaded.get("ok",false): print(JSON.stringify(loaded)); quit(1); return
	var failures: Array=[]; var calls:=0; var latencies: Array=[]
	for c: Dictionary in data.cases:
		var result:=actor.decide_development_frame(c.frame,c.selected,[],c.frontier)
		if result.model_used: calls+=1;latencies.append(result.elapsed_us)
		if result.selected_indexes!=c.expected_indexes or result.model_used!=c.expected_used:
			failures.append({"id":c.id,"result":result,"expected":c.expected_indexes})
	# Cardinality, stale binding and invalid authority cannot become model input.
	if not data.cases.is_empty():
		var c: Dictionary=data.cases[0].duplicate(true)
		var stale: Dictionary=c.frontier.duplicate(true);stale.window_id="0".repeat(64)
		var bad:=actor.decide_development_frame(c.frame,c.selected,[],stale)
		if bad.model_used or bad.selected_indexes!=c.selected: failures.append({"stale":bad})
		for indexes: Array in [[c.selected[0],c.selected[0]],[c.selected[0],true],[c.selected[0],0.5],[c.selected[0],999999]]:
			var invalid: Dictionary=c.frontier.duplicate(true);invalid.indexes=indexes
			var rejected:=actor.decide_development_frame(c.frame,c.selected,[],invalid)
			if rejected.model_used or rejected.selected_indexes!=c.selected or rejected.diagnostic_code!="model_authority_input_invalid":
				failures.append({"invalid_frontier":indexes,"result":rejected})
	print(JSON.stringify({"cases":data.cases.size(),"calls":calls,"latencies_usec":latencies,"failures":failures}))
	quit(0 if failures.is_empty() and calls>0 else 1)
