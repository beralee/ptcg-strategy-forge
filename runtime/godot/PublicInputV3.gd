extends "res://scripts/ai/ptcgdap/public/PublicInputV2.gd"
## Engine-owned public receipts. Private identities exist only inside _scan.
## They are never emitted, hashed into event IDs, or used for event ordering.

var _owner: Variant
var _previous: Dictionary = {}
var _journal: Array = []
var _journal_cursor := 0
var _checkpoint := 0
var _shuffle_counts: Array = []
var _effect_instances: Array = []
var _effect_counter := 0
var _uses: Dictionary = {}
var _public_source: Dictionary = {}
var _information_signature := ""
var _coin_waiting_for_log := false
var _completed_coin_result := false

const REVIEWED_ATTACKERS := ["CSV8C_159", "CSV8C_158", "CS4DaC_137", "CSV8C_094", "CSV3C_042", "CSV7C_059"]
const REVIEWED_BOARD_SOURCES := ["CSV8C_159", "CSV8C_158", "CS4DaC_137", "CSV8C_094", "CSV3C_042", "CSV7C_059", "CSV8C_135", "CS6.5C_066", "CSV1C_118", "CSV2C_127", "CSV8C_203"]
const REVIEWED_MARKERS := ["reduce_damage_next_turn", "retreat_lock", "ability_disabled", "prevent_attack_damage_and_effects", "attack_lock_until_leave_active", "defender_attack_lock"]

static func _window_card_aliases(value: Variant, aliases: Dictionary) -> Variant:
	if value is Dictionary:
		var result := {}
		var keys: Array = value.keys()
		keys.sort()
		for key: String in keys:
			if key in ["serial", "card_serial", "source_serial", "target_serial"] and value[key] != null:
				if not aliases.has(value[key]): aliases[value[key]] = aliases.size() + 1
				result[key] = aliases[value[key]]
			else: result[key] = _window_card_aliases(value[key], aliases)
		return result
	if value is Array:
		var result: Array = []
		for child: Variant in value: result.append(_window_card_aliases(child, aliases))
		return result
	return value

func make_observation(frame: Dictionary, payload: Dictionary) -> Dictionary:
	# Legacy registry card serials are internal current-window join keys. They
	# must never become stable card tracking identities in the v3 transport.
	var public_frame: Dictionary = _window_card_aliases(frame, {})
	public_frame.source = {"window_id": ("%s:v3:%d:%d" % [_match, _seat, frame.sequence]).sha256_text().to_upper(), "public_observation_hash": ""}
	public_frame.source.public_observation_hash = JSON.stringify(public_frame).sha256_text().to_upper()
	var public_payload := payload.duplicate(true)
	public_payload.binding = public_frame.source.duplicate(true)
	public_payload.binding.sequence = public_frame.sequence
	public_payload.binding.seat = public_frame.seat
	return {"profile": "ptcg-public-input-v3", "frame": public_frame, "input": public_payload}

static func validate_receipt(frame: Dictionary, payload: Dictionary, schema: Dictionary) -> String:
	var frame_error: String = preload("res://scripts/ai/ptcgdap/public/CompetitivePolicyV2.gd")._frame_error(frame)
	if frame_error != "": return frame_error
	var error: String = preload("res://scripts/ai/ptcgdap/public/PublicInputV2.gd").validate_receipt(frame, payload, schema)
	if error != "": return error
	var history: Dictionary = payload.history
	if history.seat != frame.seat: return "public_input_v3_visibility"
	if history.snapshot_cursor != history.cursor or history.first_available > history.cursor + 1: return "public_input_v3_snapshot_cursor"
	var last := 0
	for event: Dictionary in history.events:
		if event.seq <= last or event.seq < history.first_available or event.seq > history.cursor: return "public_input_v3_history_sequence"
		if history.complete and event.seq != last + 1: return "public_input_v3_false_complete_history"
		last = int(event.seq)
		if (event.visibility == "all" and event.visible_to != null) or (event.visibility == "seat" and event.visible_to != history.seat): return "public_input_v3_visibility"
		if event.type in ["draw_card", "take_prize"] and event.player != history.seat and event.cards.status == "known": return "public_input_v3_hidden_cards"
		if event.type == "move" and event.cards.status == "known":
			var visible := false
			for key: String in ["from_zone", "to_zone"]:
				if event[key].status == "known":
					var zone: String = event[key].value
					visible = visible or zone not in ["deck", "prizes", "hand", "outside"] or (zone == "hand" and event.player == history.seat)
			if not visible: return "public_input_v3_hidden_move_identity"
	if history.complete and (history.first_available != 1 or last != history.cursor): return "public_input_v3_false_complete_history"
	var zones := {}
	for zone: Dictionary in history.snapshot:
		var key := "%d/%s" % [zone.player, zone.zone]
		if zones.has(key): return "public_input_v3_duplicate_zone"
		zones[key] = true
		var hidden: bool = zone.zone in ["deck", "prizes"] or (zone.zone == "hand" and zone.player != history.seat)
		if hidden and zone.cards.status == "known": return "public_input_v3_hidden_cards"
		if zone.cards.status == "known" and zone.cards.value.size() != zone.count: return "public_input_v3_zone_count"
	for player: int in [0, 1]:
		for zone: String in ["deck", "hand", "prizes", "discard", "lost", "active", "bench", "stadium"]:
			if not zones.has("%d/%s" % [player, zone]): return "public_input_v3_missing_zone_snapshot"
	if zones.size() != 16: return "public_input_v3_missing_zone_snapshot"
	for zone: Dictionary in history.snapshot:
		var side: Dictionary = frame.public_state["self" if zone.player == frame.seat else "opponent"]
		var expected := -1
		match zone.zone:
			"deck": expected = int(side.deck_count)
			"prizes": expected = int(side.prizes_remaining)
			"hand": expected = side.hand.size() if zone.player == frame.seat else int(side.hand_count)
			"discard": expected = side.discard.size()
		if expected >= 0 and zone.count != expected: return "public_input_v3_snapshot_frame_mismatch"
	var entities := {}
	var board_count := 0
	for row: Dictionary in payload.entities:
		if entities.has(row.entity): return "public_input_v3_duplicate_entity"
		entities[row.entity] = row
	for side: String in ["self", "opponent"]:
		for zone: String in ["active", "bench"]:
			for slot: Dictionary in frame.public_state[side][zone]:
				board_count += 1
				if not entities.has(slot.entity_serial): return "public_input_v3_entity"
				var row: Dictionary = entities[slot.entity_serial]
				if row.source_uid != slot.local_card_uid or row.zone != zone or row.player != (frame.seat if side == "self" else 1-frame.seat): return "public_input_v3_entity"
	if board_count != entities.size(): return "public_input_v3_entity"
	for section: String in ["abilities", "quotas", "effects"]:
		var ids := {}
		for row: Dictionary in payload[section]:
			if ids.has(row.id): return "public_input_v3_duplicate_identity"
			ids[row.id] = true
	for a: Dictionary in payload.abilities:
		if not entities.has(a.entity): return "public_input_v3_ability_entity"
		var e: Dictionary = entities[a.entity]
		if a.player != e.player or a.id != "%d/%s/ability/%d" % [a.entity, a.source_uid, a.index]: return "public_input_v3_ability_source"
		if a.source_uid != e.source_uid and (e.tools.status != "known" or a.source_uid not in e.tools.value): return "public_input_v3_ability_source"
		if a.main_availability.status == "known" and a.main_availability.value in ["offered", "not_offered"]:
			var offered := false
			for option: Dictionary in frame.options:
				if option.kind == "ability" and option.get("source_entity_serial") == a.entity and option.ability_index == a.index: offered = true
			if offered != (a.main_availability.value == "offered"): return "public_input_v3_availability_frontier"
	for row: Dictionary in payload.effects:
		if row.target_entity != null and not entities.has(row.target_entity): return "public_input_v3_effect_target"
	var evaluations := {}
	for row: Dictionary in payload.evaluations:
		var key := "%d/%d/%d" % [row.attacker, row.attack_index, row.target]
		if evaluations.has(key) or not entities.has(row.attacker) or not entities.has(row.target): return "public_input_v3_evaluation_identity"
		evaluations[key] = true
		if row.kind == "exact" and (row.damage_hp.status != "known" or not row.unresolved.is_empty()): return "public_input_v3_false_exact"
	return ""

func bind(gsm: Variant, match_id: String, seat: int) -> void:
	super.bind(gsm, match_id, seat)
	gsm.coin_flipper.coin_flipped.connect(_on_public_coin)

func close() -> void:
	if _gsm != null and _gsm.coin_flipper != null and _gsm.coin_flipper.coin_flipped.is_connected(_on_public_coin):
		_gsm.coin_flipper.coin_flipped.disconnect(_on_public_coin)
	_owner = null
	_effect_instances.clear()
	super.close()

func _on_public_coin(result: bool) -> void:
	# This signal contains only the completed public outcome, no RNG state.
	var e := _event("coin_flip", null, "engine_coin")
	e.count = known(1)
	e.random_outcome = known("heads" if result else "tails", "CoinFlipper.coin_flipped_completed")
	e.knowledge = "invalidate_hidden_associations"
	_append(e)
	_coin_waiting_for_log = true
	_completed_coin_result = result

func _ability(owner: Variant, frame: Dictionary, slot: Variant, index: int, source: Variant, effect: Variant) -> Dictionary:
	var row := super._ability(owner, frame, slot, index, source, effect)
	var path: String = effect.get_script().resource_path.get_file() if effect != null else ""
	if source == slot.get_top_card() and slot.get_card_data().abilities.size() > 1: path = ""
	row.resolution = absent("ability_resolution_not_reviewed")
	if path in ["AbilityDrawIfActive.gd", "AbilityDrawIfKnockoutLastTurn.gd"]:
		row.resolution = known("immediate", "reviewed_engine_rule/" + path)
	elif path in ["AbilityLookTopToHand.gd", "AbilityAttachBasicEnergyFromHandDraw.gd", "AbilityMoveDamageCountersToOpponent.gd", "AbilityDiscardDrawAny.gd", "AbilityVSTARSearch.gd", "AbilityAttachBasicWaterEnergyFromHand.gd", "AbilityPsychicEmbrace.gd"]:
		row.resolution = known("requires_interaction", "reviewed_engine_rule/" + path)
	return row

func _event(type: String, pi: Variant, origin: String = "public_boundary") -> Dictionary:
	return {"seq": 0, "turn": _gsm.game_state.turn_number, "player": pi, "phase": int(_gsm.game_state.phase),
		"type": type, "visibility": "all", "visible_to": null, "count": absent("not_a_count", "not_applicable"),
		"cards": absent("no_card_identity", "not_applicable"), "knowledge": "snapshot_only",
		"from_zone": absent("not_a_move", "not_applicable"), "to_zone": absent("not_a_move", "not_applicable"),
		"source_entity": absent("source_not_recorded", "unknown"), "target_entity": absent("target_not_recorded", "unknown"),
		"amount_hp": absent("not_damage", "not_applicable"), "origin": origin,
		"random_outcome": absent("not_random", "not_applicable")}

func _append(event: Dictionary) -> void:
	_journal_cursor += 1
	event.seq = _journal_cursor
	_journal.append(event)
	if _journal.size() > 512: _journal.pop_front()
	if event.type in ["draw_card", "take_prize", "public_reveal", "shuffle_deck", "coin_flip", "move"]: _checkpoint += 1

func _visible(zone: String, pi: int) -> bool:
	return zone not in ["deck", "prizes", "outside"] and (zone != "hand" or pi == _seat)

func _put_cards(map: Dictionary, cards: Array, zone: String, pi: int, entity: int = 0) -> void:
	for card: Variant in cards:
		map[card.instance_id] = {"zone": zone, "player": pi, "uid": uid(card) if _visible(zone, pi) else "", "entity": entity}

func _scan() -> Dictionary:
	var map := {}
	var board := {}
	var state: Variant = _gsm.game_state
	_owner._sync_public_pokemon_entities()
	for pi: int in [0, 1]:
		var p: Variant = state.players[pi]
		for pair: Array in [["hand", p.hand], ["deck", p.deck], ["prizes", p.prizes], ["discard", p.discard_pile], ["lost", p.lost_zone]]:
			_put_cards(map, pair[1], pair[0], pi)
		for slot: Variant in p.get_all_pokemon():
			var entity: int = _owner._entity_serial_for_slot(slot)
			var zone := "active" if p.active_pokemon == slot else "bench"
			_put_cards(map, slot.pokemon_stack, zone, pi, entity)
			_put_cards(map, slot.attached_energy, zone, pi, entity)
			_put_cards(map, slot.get_attached_tools(), zone, pi, entity)
			board[entity] = {"player": pi, "damage": slot.damage_counters, "status": slot.status_conditions.duplicate(true)}
	if state.stadium_card != null:
		_put_cards(map, [state.stadium_card], "stadium", state.stadium_owner_index)
	return {"cards": map, "board": board}

func _reconcile() -> void:
	if _owner == null: return
	var current := _scan()
	if _previous.is_empty():
		_previous = current
		_shuffle_counts = [_gsm.game_state.players[0].shuffle_count, _gsm.game_state.players[1].shuffle_count]
		return
	var groups := {}
	var ids: Dictionary = _previous.cards.duplicate()
	ids.merge(current.cards, true)
	for identity: Variant in ids:
		var old: Dictionary = _previous.cards.get(identity, {"zone": "outside", "player": ids[identity].player, "uid": "", "entity": 0})
		var now: Dictionary = current.cards.get(identity, {"zone": "outside", "player": old.player, "uid": "", "entity": 0})
		if old.zone == now.zone and old.entity == now.entity and old.uid == now.uid: continue
		var printing: String = now.uid if now.uid != "" else old.uid
		var public_key := JSON.stringify([old.player, old.zone, now.zone, old.entity, now.entity, printing])
		if not groups.has(public_key): groups[public_key] = {"old": old, "now": now, "uid": printing, "count": 0}
		groups[public_key].count += 1
	var keys: Array = groups.keys()
	keys.sort() # only public semantic values; no hidden card serial ordering
	for key: String in keys:
		var g: Dictionary = groups[key]
		var e := _event("move", g.old.player)
		e.from_zone = known(g.old.zone)
		e.to_zone = known(g.now.zone)
		e.count = known(g.count)
		if g.uid != "":
			var printings: Array = []
			for i: int in g.count: printings.append(g.uid)
			e.cards = known(printings, "visible_endpoint_printing_multiset")
		else: e.cards = absent("hidden_endpoints", "unknown")
		if g.old.entity > 0: e.source_entity = known(g.old.entity)
		if g.now.entity > 0: e.target_entity = known(g.now.entity)
		if g.old.zone in ["hand", "deck", "prizes"] or g.now.zone in ["hand", "deck", "prizes"]:
			e.knowledge = "invalidate_hidden_associations"
		if g.old.player == _seat and (g.old.zone == "hand" or g.now.zone == "hand") and g.old.zone not in ["active", "bench", "discard", "lost", "stadium"] and g.now.zone not in ["active", "bench", "discard", "lost", "stadium"]:
			e.visibility = "seat"
			e.visible_to = _seat
		_append(e)
	for entity: Variant in current.board:
		if not _previous.board.has(entity): continue
		var now: Dictionary = current.board[entity]
		var old: Dictionary = _previous.board[entity]
		if now.damage != old.damage:
			var e := _event("damage_change", now.player)
			e.target_entity = known(entity)
			e.amount_hp = known(now.damage - old.damage)
			_append(e)
		if now.status != old.status:
			var e := _event("status_change", now.player)
			e.target_entity = known(entity)
			_append(e)
	for pi: int in [0, 1]:
		var count: int = _gsm.game_state.players[pi].shuffle_count
		if count != _shuffle_counts[pi]:
			var e := _event("shuffle_deck", pi, "engine_shuffle")
			e.count = known(count - _shuffle_counts[pi])
			e.knowledge = "invalidate_hidden_associations"
			_append(e)
		_shuffle_counts[pi] = count
	_previous = current

func _snapshot() -> Array:
	var result: Array = []
	for pi: int in [0, 1]:
		for zone: String in ["hand", "deck", "prizes", "discard", "lost", "active", "bench", "stadium"]:
			var cards: Array = []
			var count := 0
			for row: Dictionary in _previous.cards.values():
				if row.player == pi and row.zone == zone:
					count += 1
					if row.uid != "": cards.append(row.uid)
			cards.sort()
			result.append({"player": pi, "zone": zone, "count": count, "cards": known(cards) if _visible(zone, pi) else absent("hidden_zone", "unknown")})
	return result

func _on_action(action: Variant) -> void:
	super._on_action(action)
	if _owner == null: return
	_public_source = {}
	var pi: int = action.player_index
	if pi in [0, 1]:
		for slot: Variant in _gsm.game_state.players[pi].get_all_pokemon():
			if int(action.data.get("source_slot_runtime_id", -1)) == slot.get_instance_id():
				_public_source = {"entity": _owner._entity_serial_for_slot(slot), "uid": uid(slot.get_top_card()), "player": pi}
	_reconcile()
	var e: Dictionary = _events.back().duplicate(true)
	if e.type == "coin_flip" and _coin_waiting_for_log and action.data.get("result") == _completed_coin_result:
		_coin_waiting_for_log = false
		return # The same completed flip already has one stable public event.
	var extra := _event(e.type, e.player, "engine_action")
	for key: String in e: extra[key] = e[key]
	if e.type == "coin_flip" and typeof(action.data.get("result")) == TYPE_BOOL:
		extra.random_outcome = known("heads" if action.data.result else "tails", "GameAction.completed_public_coin_flip")
	if e.type == "damage_dealt" and typeof(action.data.get("damage")) == TYPE_INT:
		extra.amount_hp = known(action.data.damage, "GameAction.damage")
	if not _public_source.is_empty(): extra.source_entity = known(_public_source.entity)
	if e.type == "use_ability" and not _public_source.is_empty() and action.data.has("public_ability_index"):
		var key := "%d/%d/%d" % [_public_source.entity, action.data.public_ability_index, _gsm.game_state.turn_number]
		_uses[key] = int(_uses.get(key, 0)) + 1
	_append(extra)
	_sync_effect_instances()
	_public_source = {}

func _sync_effect_instances() -> void:
	for record: Dictionary in _effect_instances: record.seen = false
	for pi: int in [0, 1]:
		for slot: Variant in _gsm.game_state.players[pi].get_all_pokemon():
			for marker: Dictionary in slot.effects:
				if marker.get("type", "") not in REVIEWED_MARKERS: continue
				var found := false
				for record: Dictionary in _effect_instances:
					if record.active and is_same(record.marker, marker):
						record.seen = true
						found = true
						break
				if not found:
					_effect_counter += 1
					_effect_instances.append({"marker": marker, "id": "effect:%d" % _effect_counter,
						"entity": _owner._entity_serial_for_slot(slot), "player": pi, "source": _public_source.duplicate(true), "seen": true, "active": true})
	for record: Dictionary in _effect_instances:
		if not record.seen: record.active = false

func _enhance_effects(result: Dictionary) -> void:
	_sync_effect_instances()
	var used_records := {}
	for e: Dictionary in result.effects:
		e.source_kind = known("rule") if e.combination == "engine_resolved" else absent("origin_not_recorded", "unknown")
		e.source_entity = absent("origin_not_recorded", "unknown")
		e.source_player = absent("origin_not_recorded", "unknown")
		e.identity_scope = "resolved_rule"
		e.lifecycle = known("while_present") if e.combination == "engine_resolved" else known("next_turn" if e.type != "ability_disabled" else "current_turn")
		if e.combination != "engine_resolved":
			for record: Dictionary in _effect_instances:
				if record.active and record.entity == e.target_entity and record.marker.type == e.type and not used_records.has(record.id) and int(record.marker.get("turn", -1)) == int(e.starts_turn.value) and (e.type != "reduce_damage_next_turn" or int(record.marker.get("amount", 0)) == int(e.parameters[0].value)):
					e.id = record.id
					e.identity_scope = "engine_instance"
					used_records[record.id] = true
					if not record.source.is_empty():
						e.source_kind = known("entity")
						e.source_entity = known(record.source.entity)
						e.source_player = known(record.source.player)
						e.source_uid = known(record.source.uid)
					break
		if e.expires_turn.status == "known" and e.expires_turn.value == _gsm.game_state.turn_number:
			e.expiry_player = known(_gsm.game_state.current_player_index, "engine_current_turn_owner")

func _enhance_interaction(owner: Variant, result: Dictionary) -> void:
	var ctx: Dictionary = result.interaction
	var bridge: Variant = owner.get("_public_input_bridge")
	if bridge == null or bridge.get_script().resource_path.get_file() != "HeadlessMatchBridge.gd":
		result.capabilities.interaction = known("partial")
		return
	if bridge._pending_effect_kind == "": return
	var step: Dictionary = bridge._pending_effect_steps[bridge._pending_effect_step_index]
	# Headless bridge has no abort dispatch. An empty choice is a step result,
	# never an action rollback. Commit follows the final validated step.
	ctx.cancel_allowed = known(false, "HeadlessMatchBridge.no_abort_dispatch")
	ctx.cancel_semantics = absent("no_abort_action", "not_applicable")
	ctx.parent_committed = known(false, "HeadlessMatchBridge.commit_after_all_steps")
	ctx.commit_stage = known("declared_pending_resolution" if bridge._pending_effect_kind in ["attack", "granted_attack"] else "collecting_choices", "HeadlessMatchBridge.action_lifecycle")
	if int(step.get("min_select", 1)) == 0:
		ctx.cancel_semantics = known("decline_optional", "empty_selection_advances_step")
	var mode: String = str(step.get("ui_mode", ""))
	if mode in ["counter_distribution", "field_assignment", "card_assignment"]:
		ctx.stage = known("allocation", "compiled_step_ui_mode")
	elif str(step.get("zone", "")) == "deck" or str(step.get("id", "")) in ["search_pokemon", "search_cards", "look_top_pick"]: ctx.stage = known("search")
	elif str(step.get("id", "")) in ["discard_cards", "discard_card"]: ctx.stage = known("payment")
	if mode == "counter_distribution":
		ctx.remaining_damage_counters = known(maxi(0, int(step.get("total_counters", 0)) - bridge._get_counter_distribution_assigned_total()), "HeadlessMatchBridge.remaining_counter_budget")
		ctx.allow_partial = known(bool(step.get("allow_partial", false)))
		for key: String in ["max_assignments", "max_assignments_per_target"]:
			ctx[key] = known(int(step[key])) if step.has(key) else absent("unbounded_assignment_count", "not_applicable")
	var signature := str(ctx.action_id.value) + "/" + str(bridge._pending_effect_step_index)
	if ctx.stage.status == "known" and ctx.stage.value == "search" and signature != _information_signature:
		_information_signature = signature
		_checkpoint += 1
		var e := _event("information_checkpoint", _seat)
		e.visibility = "seat"
		e.visible_to = _seat
		e.knowledge = "invalidate_hidden_associations"
		_append(e)
	ctx.checkpoint = _checkpoint

func _resolved_effect(type: String, entity: int, pi: int, parameters: Array, rule: String) -> Dictionary:
	return {"id": "resolved/%d/%s" % [entity, type], "type": type, "target_entity": entity, "target_player": pi,
		"source_uid": absent("multiple_public_sources", "not_applicable"), "source_kind": known("rule"),
		"source_entity": absent("aggregate", "not_applicable"), "source_player": absent("aggregate", "not_applicable"),
		"identity_scope": "resolved_rule", "lifecycle": known("while_present"), "parameters": parameters,
		"condition": "current_public_board", "condition_met": known(true),
		"starts_turn": absent("aggregate", "not_applicable"), "expires_turn": absent("reobserve_on_change", "unknown"),
		"expiry_boundary": "while_source_present", "expiry_player": absent("board_dependent", "not_applicable"),
		"combination": "engine_resolved", "rule": rule}

func _resolved_attributes(frame: Dictionary, result: Dictionary) -> void:
	for entity: Dictionary in result.entities:
		var detail: Dictionary = {}
		for e: Dictionary in frame.public_state.decision.entities:
			if e.entity_serial == entity.entity: detail = e
		var supply := 0
		for energy: Dictionary in detail.energies: supply += int(energy.units)
		for spec: Array in [["hp_modifier", "hp", entity.effective_max_hp.value - entity.printed_hp.value, "EffectProcessor.get_effective_max_hp minus printed HP"],
			["retreat_cost", "energy_units", detail.effective_retreat_cost, "EffectProcessor.get_effective_retreat_cost"],
			["energy_supply", "energy_units", supply, "EffectProcessor public effective energy units"],
			["early_evolution", "boolean", detail.early_evolution_allowed, "Engine early evolution predicate; not complete evolve legality"]]:
			result.effects.append(_resolved_effect(spec[0], entity.entity, entity.player, [{"name": "effective", "unit": spec[1], "value": spec[2]}], spec[3]))

func _additional_markers(result: Dictionary) -> void:
	var state: Variant = _gsm.game_state
	for record: Dictionary in _effect_instances:
		if not record.active or record.marker.type in MARKER_EFFECTS: continue
		var m: Dictionary = record.marker
		var e := _resolved_effect(m.type, record.entity, record.player, [], "Reviewed engine marker; RuleValidator owns action legality.")
		e.id = record.id
		e.identity_scope = "engine_instance"
		e.combination = "any"
		e.source_kind = absent("origin_not_recorded", "unknown")
		e.source_uid = absent("origin_not_recorded", "unknown")
		e.source_entity = absent("origin_not_recorded", "unknown")
		e.source_player = absent("origin_not_recorded", "unknown")
		e.parameters = [{"name": "blocked_action", "unit": "rule", "value": "attack"}]
		if m.type == "attack_lock_until_leave_active":
			e.parameters.append({"name": "attack_index", "unit": "count", "value": int(m.get("attack_index", 0))})
			e.parameters.append({"name": "attack_name", "unit": "rule", "value": str(m.get("attack_name", ""))})
			e.condition = "matching_printed_attack_name_while_marker_retained"
			e.condition_met = known(true)
			e.lifecycle = known("until_leave_active")
			e.expiry_boundary = "unknown" # v2 boundary enum cannot represent leave-active alone
			e.expires_turn = absent("until_leave_active", "not_applicable")
		else:
			var turn: int = int(m.get("turn", -1))
			if turn < 0: continue
			e.starts_turn = known(turn)
			e.expires_turn = known(turn + 1)
			e.expiry_boundary = "leave_active_or_after_turn_end"
			e.expiry_player = known(state.current_player_index) if state.turn_number == turn + 1 else absent("future_turn_owner_not_recorded", "unknown")
			e.lifecycle = known("next_turn")
			e.condition = "global_turn_equals_expiry_and_marker_retained"
			e.condition_met = known(state.turn_number == turn + 1)
			if m.type == "prevent_attack_damage_and_effects":
				e.parameters = [{"name": "prevent_damage", "unit": "boolean", "value": true}, {"name": "prevent_attack_effects", "unit": "boolean", "value": true}]
			else:
				e.parameters.append({"name": "mode", "unit": "rule", "value": str(m.get("mode", ""))})
				e.parameters.append({"name": "attack_name", "unit": "rule", "value": str(m.get("attack_name", ""))})
				for s: Variant in state.players[record.player].get_all_pokemon():
					if _owner._entity_serial_for_slot(s) == record.entity:
						e.condition_met = known(state.turn_number == turn + 1 and _gsm.rule_validator._defender_attack_lock_applies(s, m))
		result.effects.append(e)

func _evaluation_board_reviewed() -> bool:
	# Do not dispatch arbitrary card scripts with hidden state from a public query.
	var state: Variant = _gsm.game_state
	if state.stadium_card != null and uid(state.stadium_card) not in REVIEWED_BOARD_SOURCES: return false
	for p: Variant in state.players:
		for s: Variant in p.get_all_pokemon():
			if uid(s.get_top_card()) not in REVIEWED_BOARD_SOURCES: return false
			for t: Variant in s.get_attached_tools():
				if uid(t) not in REVIEWED_BOARD_SOURCES: return false
			for energy: Variant in s.attached_energy:
				if energy.card_data.card_type != "Basic Energy": return false
	return true

func _evaluate(owner: Variant, frame: Dictionary, result: Dictionary) -> void:
	var state: Variant = _gsm.game_state
	var processor: Variant = _gsm.effect_processor
	var reviewed_board := _evaluation_board_reviewed()
	var facts: Dictionary = {}
	for row: Dictionary in frame.public_state.decision.entities: facts[row.entity_serial] = row
	for pi: int in [0, 1]:
		for attacker: Variant in state.players[pi].get_all_pokemon():
			var entity: int = owner._entity_serial_for_slot(attacker)
			for attack_fact: Dictionary in facts[entity].attacks:
				for defender: Variant in state.players[1-pi].get_all_pokemon():
					var target: int = owner._entity_serial_for_slot(defender)
					var row := {"attacker": entity, "target": target, "attack_index": attack_fact.attack_index,
						"damage_hp": absent("attack_source_not_qualified"), "minimum_hp": absent("range_not_qualified"), "maximum_hp": absent("range_not_qualified"),
						"kind": "unknown", "unresolved": ["unreviewed_attack_effect"],
						"damage_prevented": known(processor.is_damage_prevented_by_defender_ability(attacker, defender, state)) if reviewed_board else absent("board_sources_not_qualified"),
						"effects_prevented": known(processor.is_attack_effect_prevented_by_defender_ability(attacker, defender, state)) if reviewed_board else absent("board_sources_not_qualified"),
						"attacker_modifier_hp": known(processor.get_attacker_modifier(attacker, state, defender)) if reviewed_board else absent("board_sources_not_qualified"),
						"defender_modifier_hp": known(processor.get_defender_modifier(defender, state, attacker)) if reviewed_board else absent("board_sources_not_qualified"),
						"weakness_value": known(processor.get_weakness_value_override(attacker, defender, state)) if reviewed_board else absent("board_sources_not_qualified"),
						"weakness_type": known(processor.get_weakness_energy_override(attacker, defender, state)) if reviewed_board else absent("board_sources_not_qualified"),
						"resistance_value": known(str(defender.get_card_data().resistance_value), "CardData.resistance_value; engine has no dynamic override hook"),
						"cost_satisfied": known(attack_fact.energy_ready), "cost_candidates": known(attack_fact.cost_candidates),
						"restrictions": ["not_legality_proof"]}
					if row.weakness_value.value == "": row.weakness_value = known(defender.get_card_data().weakness_value, "CardData.weakness_value_no_override")
					if row.weakness_type.value == "": row.weakness_type = known(defender.get_card_data().weakness_energy, "CardData.weakness_energy_no_override")
					if reviewed_board and uid(attacker.get_top_card()) in REVIEWED_ATTACKERS:
						var attack: Dictionary = attacker.get_card_data().attacks[attack_fact.attack_index]
						var amount: int = _gsm._calculate_attack_damage(attacker, defender, attack, attack_fact.attack_index)
						row.damage_hp = known(maxi(0, amount), "GameStateMachine._calculate_attack_damage")
						row.kind = "conditional"
						row.unresolved = ["attack_must_resolve", "followup_interaction"]
						row.minimum_hp = known(0)
						row.maximum_hp = known(maxi(0, amount))
						if attacker.status_conditions.get("confused", false): row.unresolved.append("confusion_coin_flip")
					if state.players[pi].active_pokemon != attacker: row.restrictions.append("attacker_not_active")
					if state.players[1-pi].active_pokemon != defender: row.restrictions.append("target_not_opponent_active")
					result.evaluations.append(row)

func capture(owner: Variant, frame: Dictionary) -> Dictionary:
	_owner = owner
	_reconcile()
	var result: Dictionary = super.capture(owner, frame)
	result.version = 3
	result.interaction.commit_stage = known("idle") if result.interaction.in_progress.status == "known" and not result.interaction.in_progress.value else absent("bridge_context_not_available", "unknown")
	result.evaluations = []
	result.capabilities = {"snapshot": known("supported"), "ability_quotas": known("supported"),
		"effects": known("partial"), "event_stream": known("supported"), "interaction": known("supported"), "attack_evaluation": known("partial")}
	result.gaps = ["unreviewed_effect_types_explicit", "arbitrary_attack_sources_not_all_qualified", "intermediate_unobserved_states_not_a_replay"]
	for a: Dictionary in result.abilities:
		a.availability_reason = absent("not_current_own_main_window", "unknown")
		if a.kind.status == "known" and a.kind.value == "passive": a.resolution = known("passive")
		if a.quota.remaining.status == "unlimited" and _started_before_actions:
			var key := "%d/%d/%d" % [a.entity, a.index, _gsm.game_state.turn_number]
			a.quota.used = known(int(_uses.get(key, 0)), "engine_committed_ability_events")
			a.quota.reset = known("turn", "accounting_period_not_limit")
		if a.quota.remaining.status in ["unsupported", "history_incomplete"]: result.capabilities.ability_quotas = known("partial")
		if a.main_availability.status == "known":
			a.availability_reason = known("current_window_offers_entry" if a.main_availability.value == "offered" else "current_window_has_no_entry")
	_enhance_effects(result)
	_additional_markers(result)
	_resolved_attributes(frame, result)
	_enhance_interaction(owner, result)
	_evaluate(owner, frame, result)
	result.history = {"stream": _match + ":view:" + str(_seat), "match": _match, "seat": _seat,
		"cursor": _journal_cursor, "first_available": _journal[0].seq if not _journal.is_empty() else _journal_cursor + 1,
		"complete": _started_before_actions and _journal_cursor <= 512, "scope": "public_boundaries_and_actions",
		"events": _journal.duplicate(true), "snapshot": _snapshot(), "snapshot_cursor": _journal_cursor, "checkpoint": _checkpoint}
	return result
