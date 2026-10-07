extends SceneTree
const BaseInputScript = preload("res://BaseInputV1.gd")

func ints(value: Variant) -> Variant:
	if value is float and value == floor(value): return int(value)
	if value is Dictionary:
		var out: Dictionary = {}
		for key: Variant in value: out[key] = ints(value[key])
		return out
	if value is Array:
		var out: Array = []
		for child: Variant in value: out.append(ints(child))
		return out
	return value

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var payload: Dictionary = ints(JSON.parse_string(FileAccess.get_file_as_string(args[0])))
	var rows: Array = []; var failures: Array = []
	for case: Dictionary in payload.cases:
		var result := BaseInputScript.capture_validated(case.frame,payload.contract,payload.card_root,case.get("plan"))
		# Equality includes all fields, presence, masks, binding and digests.
		if result != case.expected: failures.append(case.id)
		var row: Dictionary = {"id":case.id,"passed":result==case.expected,"result":result}
		if result != case.expected: row["canonical_model"] = BaseInputScript.canonical(result.model)
		rows.append(row)
	var file := FileAccess.open(args[1],FileAccess.WRITE)
	file.store_string(JSON.stringify({"rows":rows,"failures":failures},"  "));file.close()
	print(JSON.stringify({"cases":rows.size(),"failures":failures}))
	quit(0 if failures.is_empty() else 1)
