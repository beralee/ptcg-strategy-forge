extends SceneTree
const ModelInput = preload("res://scripts/ai/ptcgdap/host/godot/SemanticModelInput.gd")
const Base = preload("res://scripts/ai/ptcgdap/public/CompetitivePolicyV2.gd")
const Actor = preload("res://scripts/ai/ptcgdap/host/godot/PtcgDAPModelActor.gd")
const Loader = preload("res://scripts/ai/ptcgdap/packages/AuthorStrategyPackageLoader.gd")

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
	var uids := {}
	for uid: String in data.uids: uids[uid]=true
	var failures: Array = []
	for c: Dictionary in data.cases:
		var result := ModelInput.project(c.frame,uids)
		if not result.get("ok",false): failures.append({"case":c.id,"error":result}); continue
		for key: String in c.expected:
			var actual: Variant=result[key]
			if actual is PackedInt32Array: actual=Array(actual)
			if key in ["option_i32","option_presence_i32","option_mask_i32"]: actual=actual.slice(0,c.expected[key].size())
			if actual != c.expected[key]: failures.append({"case":c.id,"field":key,"actual":actual.slice(0,140) if actual is Array else actual}); break
		var tiers := {}
		for i: int in c.frame.options.size(): tiers[i]=[0]
		var frontier := Base._base_model_frontier(c.frame,c.selected,tiers,[],[],[],{},c.audit)
		if frontier != c.frontier: failures.append({"case":c.id,"frontier":frontier})
	print(JSON.stringify({"cases":data.cases.size(),"failures":failures}))
	quit(0 if failures.is_empty() else 1)
