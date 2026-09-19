extends RefCounted

# A completed filename is published only after a flushed, byte-exact readback.
static func write_json(path: String, value: Variant) -> bool:
	var bytes := (JSON.stringify(value, "\t") + "\n").to_utf8_buffer()
	var temporary := path + ".tmp"
	var file := FileAccess.open(temporary, FileAccess.WRITE)
	if file == null:
		return false
	file.store_buffer(bytes)
	file.flush()
	var good := file.get_error() == OK and file.get_position() == bytes.size() and file.get_length() == bytes.size()
	file.close()
	if not good or FileAccess.get_file_as_bytes(temporary) != bytes:
		return false
	return DirAccess.rename_absolute(temporary, path) == OK

static func append_line(file: FileAccess, line: String) -> bool:
	if file == null:
		return false
	var expected := file.get_position() + (line + "\n").to_utf8_buffer().size()
	file.store_line(line)
	file.flush()
	return file.get_error() == OK and file.get_position() == expected and file.get_length() == expected
