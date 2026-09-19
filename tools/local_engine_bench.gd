extends Node

# Local research harness. All choices go through the existing BattleSetup owner factory.
const Loader = preload("res://scripts/ai/ptcgdap/packages/AuthorStrategyPackageLoader.gd")
const DeckGate = preload("res://scripts/ai/ptcgdap/packages/AuthorStrategyDeckGate.gd")
const Handle = preload("res://scripts/ai/ptcgdap/packages/AuthorStrategyPackageHandle.gd")
const Materializer = preload("res://scripts/ai/ptcgdap/packages/AuthorStrategyDeckMaterializer.gd")
const Factory = preload("res://scripts/ui/battle/ai/BattleDecisionOwnerFactory.gd")
const Bridge = preload("res://scripts/ai/HeadlessMatchBridge.gd")
const NpcPort = preload("res://scripts/ai/ptcgdap/host/godot/PlatformNpcRuleDecisionPort.gd")
const NpcOwner = preload("res://scripts/ai/ptcgdap/host/godot/PtcgDAPAuthorDevelopmentBattleOwner.gd")
const ResearchIO = preload("res://research_io.gd")
var config: Dictionary

func _ready() -> void:
	call_deferred("run")

func run() -> void:
	config = JSON.parse_string(FileAccess.get_file_as_string(OS.get_cmdline_user_args()[0]))
	var rows: Array = []
	for spec: Dictionary in config["games"]:
		var result := run_game(spec)
		rows.append(result)
		if not ResearchIO.write_json(config["output"].path_join("engine-summary.json"), {"games": rows}):
			push_error("bench_summary_write_failed")
			get_tree().quit(3)
			return
		print("BENCH_GAME=" + JSON.stringify(result))
		if not result.get("failure_code", "").is_empty():
			get_tree().quit(2)
			return
	get_tree().quit(0)

func load_package(spec: Dictionary) -> Dictionary:
	var bytes := FileAccess.get_file_as_bytes(spec["path"])
	if sha(bytes) != spec["sha256"]:
		return {"ok": false, "error_code": "bench_archive_mismatch"}
	var loader := Loader.new()
	var inspected: Dictionary = loader.inspect_match_bytes(bytes, spec["sha256"]) if spec["mode"] == "development_exact_fixture" else loader.inspect_control_distributed_player_match_bytes(bytes, spec["sha256"])
	if not inspected.get("ok", false):
		return inspected
	var deck_gate: Dictionary = DeckGate.build(inspected["payloads"])
	if not deck_gate.get("ok", false):
		return deck_gate
	var built: Dictionary = Handle.create(inspected["metadata"], inspected["payloads"], deck_gate["local_deck"])
	if not built.get("ok", false):
		return built
	var materialized: Dictionary = Materializer.build(built["handle"])
	if not materialized.get("ok", false):
		return materialized
	return {"ok": true, "handle": built["handle"], "deck": materialized["deck"]}

func run_game(spec: Dictionary) -> Dictionary:
	var candidate: Dictionary = config["candidate"]
	var opponent: Dictionary = spec["opponent"]
	var row := {"seed": spec["seed"], "candidate_seat": spec["seat"], "candidate_sha256": candidate["sha256"], "opponent_sha256": opponent["sha256"], "opponent_id": opponent["id"], "failure_code": "", "terminal": false}
	row["candidate_requires_model"] = candidate.get("requires_model", false)
	row["opponent_requires_model"] = opponent.get("requires_model", false)
	var c := load_package(candidate)
	var o := load_package(opponent) if opponent.has("path") else {"ok": true, "deck": get_tree().root.get_node("CardDatabase").call("get_ai_deck", int(opponent["npc"]))}
	if not c.get("ok", false) or not o.get("ok", false):
		row["failure_code"] = "load:" + str(c.get("error_code", "")) + ":" + str(o.get("error_code", ""))
		return row
	var seat := int(spec["seat"])
	var seed_owner := PlayerState.new()
	seed_owner.set_forced_shuffle_seed(int(spec["seed"]))
	var gsm := GameStateMachine.new()
	if gsm.coin_flipper != null:
		var rng: Variant = gsm.coin_flipper.get("_rng")
		if rng is RandomNumberGenerator:
			rng.seed = int(spec["seed"])
	gsm.start_game(c["deck"] if seat == 0 else o["deck"], o["deck"] if seat == 0 else c["deck"], 0)
	var match_id := "bench-%s-%d-%d" % [str(opponent["sha256"]).left(8).to_lower(), spec["seed"], seat]
	var cb: Dictionary = Factory.build_windows_author_owner(c["handle"], gsm, seat, match_id, candidate["mode"])
	var ob: Dictionary = Factory.build_windows_author_owner(o["handle"], gsm, 1-seat, match_id, opponent["mode"]) if o.has("handle") else build_npc(gsm, 1-seat, match_id, opponent)
	var co: Variant = cb.get("owner")
	var oo: Variant = ob.get("owner")
	if co == null or oo == null:
		row["failure_code"] = "owner:" + str(cb.get("error_code", "")) + ":" + str(ob.get("error_code", ""))
		seed_owner.clear_forced_shuffle_seed()
		gsm.prepare_for_disposal()
		return row
	co.enable_developer_decision_trace(true)
	oo.enable_developer_decision_trace(true)
	var bridge := Bridge.new()
	bridge.bind(gsm)
	bridge.set_ai_controllers(co if seat == 0 else oo, oo if seat == 0 else co)
	bridge.bootstrap_pending_setup()
	var trace_name := match_id + ".jsonl"
	var trace := FileAccess.open(config["output"].path_join(trace_name), FileAccess.WRITE)
	if trace == null:
		row["failure_code"] = "bench_trace_open_failed"
		co.close_match()
		oo.close_match()
		bridge.bind(null)
		bridge.free()
		seed_owner.clear_forced_shuffle_seed()
		gsm.prepare_for_disposal()
		return row
	var chain := "0".repeat(64)
	var count := 0
	var steps := 0
	while not gsm.game_state.is_game_over() and steps < int(config.get("max_steps", 1200)):
		var acting := int(gsm.game_state.current_player_index)
		if bridge.has_pending_prompt() and int(bridge.get_pending_prompt_owner()) in [0, 1]:
			acting = int(bridge.get_pending_prompt_owner())
		var owner: Variant = co if acting == seat else oo
		var before: Dictionary = owner.audit_snapshot()
		var progressed: bool = owner.run_single_step(bridge, gsm)
		var after: Dictionary = owner.audit_snapshot()
		var records: Array = owner.drain_developer_decision_records()
		for record: Dictionary in records:
			count += 1
			var payload := JSON.stringify({"step": steps, "seat": acting, "decision": record,
				"step_decision_count": records.size(),
				"engine_commit_delta": int(after.get("engine_commits", 0)) - int(before.get("engine_commits", 0)),
				"engine_rejection_delta": int(after.get("engine_rejections", 0)) - int(before.get("engine_rejections", 0))})
			chain = (chain + "\n" + payload).sha256_text().to_upper()
			if not ResearchIO.append_line(trace, JSON.stringify({"payload": payload, "chain_sha256": chain})):
				row["failure_code"] = "bench_trace_write_failed"
				break
		if not row["failure_code"].is_empty():
			break
		if not progressed:
			row["failure_code"] = "no_progress:" + bridge.get_pending_prompt_type()
			break
		steps += 1
	trace.close()
	row["terminal"] = gsm.game_state.is_game_over()
	row["winner_index"] = int(gsm.game_state.winner_index)
	row["win_reason"] = str(gsm.game_state.win_reason)
	row["turn_number"] = int(gsm.game_state.turn_number)
	row["steps"] = steps
	row["candidate_audit"] = compact(co.audit_snapshot())
	row["opponent_audit"] = compact(oo.audit_snapshot())
	row["trace_path"] = trace_name
	row["trace_count"] = count
	row["trace_root_sha256"] = chain
	row["trace_file_sha256"] = sha(FileAccess.get_file_as_bytes(config["output"].path_join(trace_name)))
	if not row["terminal"] and row["failure_code"].is_empty():
		row["failure_code"] = "step_cap"
	co.close_match()
	oo.close_match()
	bridge.bind(null)
	bridge.free()
	seed_owner.clear_forced_shuffle_seed()
	gsm.prepare_for_disposal()
	return row

func build_npc(gsm: GameStateMachine, seat: int, match_id: String, spec: Dictionary) -> Dictionary:
	var semantic: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://scripts/ai/v18_cpg/profiles/generated_semantic_manifests/%s.json" % spec["npc"]))
	var port: Dictionary = NpcPort.create(spec["npc"], spec["id"], semantic, spec["sha256"])
	if not port.get("ok", false):
		return port
	return NpcOwner.create_platform_npc(gsm, seat, match_id, port["port"], {"owner_kind": "platform_npc", "owner_id": spec["npc"], "competition_conflict_group": "platform_npc:" + spec["npc"], "release_id": spec["id"], "archive_sha256": spec["sha256"], "manifest_canonical_sha256": spec["sha256"], "deck_manifest_sha256": spec["sha256"], "card_catalog_sha256": spec["sha256"], "execution_trusted": false})

func compact(audit: Dictionary) -> Dictionary:
	var result := {}
	for key: String in ["policy_calls", "policy_successes", "policy_errors", "invalid_outputs", "same_window_fallbacks", "classic_fallbacks", "engine_commits", "engine_rejections", "external_process_attempts", "developer_trace_dropped_records"]:
		result[key] = int(audit.get(key, -1))
	for key: String in ["model_decision_windows", "model_inference_successes", "model_fallbacks", "model_changed_selections"]:
		result[key] = int(audit.get(key, 0))
	result["model_diagnostic_counts"] = audit.get("model_diagnostic_counts", {}).duplicate(true)
	result["model_elapsed_usec"] = audit.get("model_elapsed_usec", []).duplicate()
	return result

func sha(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	if not bytes.is_empty():
		context.update(bytes)
	return context.finish().hex_encode().to_upper()
