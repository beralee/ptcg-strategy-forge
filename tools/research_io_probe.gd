extends SceneTree

const ResearchIO = preload("res://research_io.gd")

func _initialize() -> void:
	var root := ProjectSettings.globalize_path("res://probe-output")
	DirAccess.make_dir_recursive_absolute(root)
	var path := root.path_join("report.json")
	var checks := []
	checks.append(ResearchIO.write_json(path, {"value": "完整一"}))
	var original := FileAccess.get_file_as_bytes(path)
	DirAccess.make_dir_absolute(path + ".tmp")
	checks.append(not ResearchIO.write_json(path, {"value": "不能覆盖"}))
	checks.append(FileAccess.get_file_as_bytes(path) == original)
	DirAccess.remove_absolute(path + ".tmp")
	checks.append(ResearchIO.write_json(path, {"value": "完整二"}))
	checks.append(JSON.parse_string(FileAccess.get_file_as_string(path))["value"] == "完整二")
	checks.append(not ResearchIO.write_json(root.path_join("absent/report.json"), {}))
	var trace := FileAccess.open(root.path_join("trace.jsonl"), FileAccess.WRITE)
	checks.append(ResearchIO.append_line(trace, "中文 utf8"))
	checks.append(ResearchIO.append_line(trace, "second"))
	trace.close()
	checks.append(FileAccess.get_file_as_string(root.path_join("trace.jsonl")) == "中文 utf8\nsecond\n")
	checks.append(not ResearchIO.append_line(null, "failed"))
	print("RESEARCH_IO_PROBE=" + JSON.stringify({"cases": checks.size(), "passed": checks.count(true)}))
	quit(0 if checks.count(false) == 0 else 1)
