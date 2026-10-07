extends RefCounted
## Engine-side public allow-list. Never copy effects, action.data or shared flags.
## Capture is synchronous with the owning Host's freshly generated v1 frame.

const MARKERS := {
	"AbilityLookTopToHand.gd": "ability_look_top_to_hand_used",
	"AbilityAttachBasicEnergyFromHandDraw.gd": "ability_attach_basic_energy_from_hand_draw_used",
	"AbilityMoveDamageCountersToOpponent.gd": "ability_move_counters_to_opp_used",
	"AbilityDiscardDrawAny.gd": "ability_discard_draw_any_used",
	"AbilityDrawIfActive.gd": "ability_draw_if_active_used",
	"AbilityThunderousCharge.gd": "ability_used_thunderous",
}
const MARKER_EFFECTS := ["reduce_damage_next_turn", "retreat_lock", "ability_disabled"]
var _gsm: Variant
var _match := ""
var _seat := 0
var _events: Array = []
var _cursor := 0
var _started_before_actions := false
var _interaction_generation := -1
var _public_action_number := 0

static func known(value: Variant, source: String = "engine") -> Dictionary:
	return {"status": "known", "value": value, "reason": "", "source": source}

static func absent(reason: String, status: String = "unsupported") -> Dictionary:
	return {"status": status, "value": null, "reason": reason, "source": "engine_projection"}

static func validate_receipt(frame: Dictionary, payload: Dictionary, contract: Dictionary) -> String:
	if preload("res://scripts/ai/ptcgdap/public/PublicDecisionFacts.gd").schema_error(payload, contract.payload_schema):
		return "public_input_v2_shape"
	if not _tags_valid(payload): return "public_input_v2_fact"
	var expected: Dictionary = frame.source.duplicate(true)
	expected.sequence = frame.sequence
	expected.seat = frame.seat
	if payload.binding != expected: return "public_input_v2_binding"
	for row: Dictionary in payload.abilities + payload.quotas:
		var q: Dictionary = row.quota
		if q.used.status == "known" and q.limit.status == "known" and q.remaining.status == "known":
			if q.remaining.value != maxi(0, int(q.limit.value) - int(q.used.value)): return "public_input_v2_quota_arithmetic"
	for row: Dictionary in payload.abilities:
		if row.player != frame.seat and row.main_availability.status == "known": return "public_input_v2_opponent_availability"
		if frame.select_semantics.select_type_raw != 0 and row.main_availability.status == "known": return "public_input_v2_nonmain_availability"
	return ""

static func _tags_valid(value: Variant) -> bool:
	if value is Dictionary:
		if value.has("status") and value.has("value") and value.has("reason") and value.has("source"):
			if (value.status == "known") != (value.value != null): return false
			if value.status != "known" and value.reason == "": return false
		for child: Variant in value.values():
			if not _tags_valid(child): return false
	elif value is Array:
		for child: Variant in value:
			if not _tags_valid(child): return false
	return true

func bind(gsm: Variant, match_id: String, seat: int) -> void:
	assert(_gsm == null and seat in [0, 1])
	_gsm = gsm
	_match = match_id
	_seat = seat
	_started_before_actions = gsm.action_log.is_empty()
	gsm.action_logged.connect(_on_action)

func close() -> void:
	if _gsm != null and _gsm.action_logged.is_connected(_on_action):
		_gsm.action_logged.disconnect(_on_action)
	_gsm = null

static func uid(card: Variant) -> String:
	return str(card.card_data.set_code) + "_" + str(card.card_data.card_index)

func _on_action(action: Variant) -> void:
	# Action descriptions and runtime IDs contain private identities. Never export.
	var name: String = GameAction.ActionType.keys()[int(action.action_type)].to_lower()
	var pi: int = action.player_index
	var cards := absent("event_card_identity_not_projected")
	var count := absent("event_count_not_recorded", "unknown")
	if typeof(action.data.get("count")) == TYPE_INT and action.data.count >= 0:
		count = known(action.data.count, "GameAction.count")
	if name in ["draw_card", "take_prize", "public_reveal", "discard"]:
		if name in ["public_reveal", "discard"] or pi == _seat:
			var identities: Array = action.data.get("card_instance_ids", [])
			var permitted: Array = []
			if pi in [0, 1]:
				var player: Variant = _gsm.game_state.players[pi]
				permitted = player.discard_pile.duplicate() if name == "discard" else player.hand.duplicate()
			var resolved: Array = []
			for identity: Variant in identities:
				for card: Variant in permitted:
					if card.instance_id == identity:
						resolved.append(uid(card))
			# Only printing multiset, no hidden instance association or draw order.
			resolved.sort()
			if resolved.size() == identities.size() and not identities.is_empty():
				cards = known(resolved, "GameAction.visible_cards_at_event")
		else:
			cards = absent("opponent_hidden_cards", "unknown")
	_cursor += 1
	_events.append({"seq": _cursor, "turn": action.turn_number, "player": pi if pi in [0, 1] else null,
		"phase": int(_gsm.game_state.phase), "type": name,
		"visibility": "seat" if name in ["draw_card", "take_prize"] and pi == _seat else "all",
		"visible_to": _seat if name in ["draw_card", "take_prize"] and pi == _seat else null,
		"count": count, "cards": cards,
		"knowledge": "public_reveal" if name == "public_reveal" else "invalidate_hidden_associations"})
	if _events.size() > 128: _events.pop_front()

func history() -> Dictionary:
	return {"stream": _match + ":view:" + str(_seat), "match": _match, "seat": _seat,
		"cursor": _cursor, "first_available": _events[0].seq if not _events.is_empty() else _cursor + 1,
		"complete": _started_before_actions and _cursor <= 128,
		"scope": "engine_logged_actions", "events": _events.duplicate(true)}

static func unknown_quota(reason: String = "unreviewed_ability_quota") -> Dictionary:
	var q := {}
	for key: String in ["scope", "group", "reset", "used", "limit", "remaining"]: q[key] = absent(reason)
	return q

static func quota(used: int, scope: String, group: Variant = null, reset: String = "turn") -> Dictionary:
	return {"scope": known(scope), "group": known(group) if group != null else absent("not_shared", "not_applicable"),
		"reset": known(reset), "used": known(used), "limit": known(1), "remaining": known(maxi(0, 1-used))}

func _ability(owner: Variant, frame: Dictionary, slot: Variant, index: int, source: Variant, effect: Variant) -> Dictionary:
	var state: Variant = _gsm.game_state
	var processor: Variant = _gsm.effect_processor
	var entity: int = owner._entity_serial_for_slot(slot)
	var pi: int = slot.get_top_card().owner_index
	var path: String = effect.get_script().resource_path.get_file() if effect != null else ""
	# This engine dispatches all native indexes to one script. Do not pretend
	# the first reviewed script proves independent counters for multiple natives.
	if source == slot.get_top_card() and slot.get_card_data().abilities.size() > 1: path = ""
	var q := unknown_quota()
	var kind := absent("ability_kind_not_reviewed")
	if MARKERS.has(path) or path in ["AbilityDrawIfKnockoutLastTurn.gd", "AbilityVSTARSearch.gd", "AbilityAttachBasicWaterEnergyFromHand.gd", "AbilityPsychicEmbrace.gd"]:
		kind = known("activated")
	elif effect != null:
		# Lacking a button method does not distinguish automatic/triggered/passive.
		kind = absent("passive_or_triggered_not_registered")
	if MARKERS.has(path):
		var used := 0
		for marker: Dictionary in slot.effects:
			if marker.get("type") == MARKERS[path] and marker.get("turn") == state.turn_number: used = 1
		q = quota(used, "entity")
	elif path == "AbilityDrawIfKnockoutLastTurn.gd" and effect.shared_flag_key == "fezandipiti":
		var key: String = "%s_%d" % [effect.shared_flag_key, pi]
		q = quota(int(state.shared_turn_flags.get(key, -1) == state.turn_number), "named_group", "player:%d:flip_the_script" % pi)
	elif path == "AbilityVSTARSearch.gd":
		q = quota(int(state.vstar_power_used[pi]), "player", "player:%d:vstar" % pi, "match")
	elif path in ["AbilityAttachBasicWaterEnergyFromHand.gd", "AbilityPsychicEmbrace.gd"]:
		q = {"scope": known("entity"), "group": absent("not_shared", "not_applicable"),
			"reset": absent("no_period_limit", "not_applicable"), "used": absent("engine_has_no_usage_counter", "history_incomplete"),
			"limit": absent("repeat_while_prerequisites_hold", "unlimited"), "remaining": absent("repeat_while_prerequisites_hold", "unlimited")}
	elif path == "AbilityFroslassFreezingShroud.gd":
		kind = known("passive")
		q = {}
		for key: String in ["scope", "group", "reset", "used", "limit", "remaining"]: q[key] = absent("passive_no_activation_quota", "not_applicable")
	for key: String in q:
		if q[key].status == "known": q[key].source = "reviewed_engine_rule/" + path
	var availability := absent("not_main_window", "unknown")
	if int(frame.select_semantics.select_type_raw) == 0 and pi == _seat and state.current_player_index == _seat:
		var offered := false
		for option: Dictionary in frame.options:
			if option.get("kind") == "ability" and option.get("source_entity_serial") == entity and option.get("ability_index") == index: offered = true
		availability = known("offered" if offered else "not_offered", "current_select_option")
	if pi != _seat: availability = absent("opponent_prerequisites_not_queried", "unknown")
	var disabled: bool = processor.is_ability_disabled(slot, state) if index < slot.get_card_data().abilities.size() else processor.is_tool_effect_suppressed(slot, state)
	var disabled_fact := known(disabled, "EffectProcessor.is_ability_disabled_or_tool_suppressed")
	if disabled: disabled_fact.reason = "public_effect_suppression; inspect resolved effect ledger"
	return {"id": "%d/%s/ability/%d" % [entity, uid(source), index], "entity": entity, "player": pi,
		"source_uid": uid(source), "index": index, "kind": kind, "quota": q,
		"disabled": disabled_fact, "main_availability": availability}

func _marker_effects(owner: Variant, slot: Variant, result: Dictionary) -> void:
	var state: Variant = _gsm.game_state
	var entity: int = owner._entity_serial_for_slot(slot)
	var pi: int = slot.get_top_card().owner_index
	var ordinal := {}
	for marker: Dictionary in slot.effects:
		var type: String = str(marker.get("type", ""))
		if type not in MARKER_EFFECTS:
			# Coverage is statically partial: even existence/order of an unreviewed
			# engine marker must not become a covert input feature.
			continue
		var turn: int = int(marker.get("turn", -1))
		if turn < 0:
			result.gaps.append("effect_missing_origin_turn")
			continue
		var offset := 0 if type == "ability_disabled" else 1
		var end_turn := turn + offset
		var parameters: Array = []
		if type == "reduce_damage_next_turn": parameters.append({"name": "damage_reduction", "unit": "hp", "value": int(marker.get("amount", 0))})
		else: parameters.append({"name": "blocked_action", "unit": "rule", "value": "ability" if type == "ability_disabled" else "retreat"})
		var signature := "%d/%s/%d/%s" % [entity, type, turn, JSON.stringify(parameters).sha256_text().left(12)]
		ordinal[signature] = int(ordinal.get(signature, 0)) + 1
		result.effects.append({"id": signature + "/" + str(ordinal[signature]), "type": type,
			"target_entity": entity, "target_player": pi, "source_uid": absent("engine_marker_has_no_public_source", "unknown"),
			"parameters": parameters, "condition": "global_turn_equals_expiry_and_marker_retained",
			"condition_met": known(state.turn_number == end_turn), "starts_turn": known(turn), "expires_turn": known(end_turn),
			"expiry_boundary": "leave_active_or_after_turn_end", "expiry_player": absent("numbered_turn_marker_does_not_record_player", "unknown"),
			"combination": "additive" if type == "reduce_damage_next_turn" else "any",
			"rule": "Engine marker semantics; leave-active cleanup owned by PokemonSlot; numbered-turn timing is not a future extra-turn prediction."})

func _checkup_damage(slot: Variant, pi: int, status: String) -> Dictionary:
	var state: Variant = _gsm.game_state
	var processor: Variant = _gsm.effect_processor
	var amount := 0
	if state.players[pi].active_pokemon == slot and bool(slot.status_conditions.get(status, false)) and not processor.prevents_special_status(slot, state) and not processor.prevents_special_status(slot, state, status):
		amount = 10 + processor.get_poison_damage_bonus(slot, state) if status == "poisoned" else 20 + processor.get_burn_damage_bonus(slot, state)
	return known(amount, "EffectProcessor.process_pokemon_check/current_board_only")

func capture(owner: Variant, frame: Dictionary) -> Dictionary:
	assert(_gsm != null and frame.seat == _seat)
	var state: Variant = _gsm.game_state
	var processor: Variant = _gsm.effect_processor
	var result := {"version": 2, "binding": frame.source.duplicate(true), "abilities": [], "quotas": [], "effects": [], "entities": [],
		"history": history(), "gaps": ["all_effect_types_not_registered", "unprojected_entity_effects_possible", "unlogged_zone_moves", "action_source_and_targets_incomplete", "cancellation_and_non_headless_context_incomplete", "dynamic_weakness_resistance_pair_dependent"]}
	result.binding.sequence = frame.sequence
	result.binding.seat = _seat
	for pi: int in [0, 1]:
		for slot: Variant in state.players[pi].get_all_pokemon():
			var entity: int = owner._entity_serial_for_slot(slot)
			var tools: Array = []
			for tool: Variant in slot.get_attached_tools(): tools.append(uid(tool))
			tools.sort()
			var stack: Array = []
			for card: Variant in slot.pokemon_stack: stack.append(uid(card))
			result.entities.append({"entity": entity, "player": pi, "zone": "active" if state.players[pi].active_pokemon == slot else "bench", "source_uid": uid(slot.get_top_card()),
				"tools": known(tools, "PokemonSlot.get_attached_tools"),
				"evolution_stack": known(stack, "PokemonSlot.pokemon_stack_bottom_to_top"),
				"printed_hp": known(slot.get_card_data().hp, "CardData.hp"),
				"effective_max_hp": known(processor.get_effective_max_hp(slot, state), "EffectProcessor.get_effective_max_hp"),
				"damage_hp": known(slot.damage_counters, "PokemonSlot.damage_counters_hp_units"),
				"remaining_hp": known(processor.get_effective_remaining_hp(slot, state), "EffectProcessor.get_effective_remaining_hp"),
				"poison_checkup_hp": _checkup_damage(slot, pi, "poisoned"),
				"burn_checkup_hp": _checkup_damage(slot, pi, "burned"),
				"weakness": absent("pair_dependent_effective_weakness"), "resistance": absent("effective_resistance_not_qualified")})
			for index: int in slot.get_card_data().abilities.size():
				result.abilities.append(_ability(owner, frame, slot, index, slot.get_top_card(), processor.get_ability_effect(slot, index, state)))
			# Enumerate Forest Seal Stone even after exhaustion (engine's granted list hides it).
			for tool: Variant in slot.get_attached_tools():
				if tool.card_data.effect_id == "9fa9943ccda36f417ac3cb675177c216" and slot.get_card_data().mechanic == "V":
					result.abilities.append(_ability(owner, frame, slot, slot.get_card_data().abilities.size(), tool, processor.get_effect(tool.card_data.effect_id)))
			_marker_effects(owner, slot, result)
			for pair: Array in [["ability_disabled", processor.is_ability_disabled(slot, state)], ["tool_suppressed", processor.is_tool_effect_suppressed(slot, state)]]:
				result.effects.append({"id": "resolved/%d/%s" % [entity, pair[0]], "type": "resolved_" + str(pair[0]),
					"target_entity": entity, "target_player": pi, "source_uid": absent("aggregate_multiple_sources", "unknown"),
					"parameters": [{"name": "effective", "unit": "boolean", "value": pair[1]}],
					"condition": "engine_resolved_current_public_board", "condition_met": known(pair[1]),
					"starts_turn": absent("aggregate_not_instance", "not_applicable"), "expires_turn": absent("reobserve_on_board_change", "unknown"),
					"expiry_boundary": "while_source_present", "expiry_player": absent("board_dependent", "not_applicable"),
					"combination": "engine_resolved", "rule": "Authoritative effective predicate from EffectProcessor; individual source attribution incomplete."})
		result.quotas.append({"id": "player:%d:vstar" % pi, "player": pi, "quota": quota(int(state.vstar_power_used[pi]), "player", "player:%d:vstar" % pi, "match")})
	var pi: int = state.current_player_index
	for pair: Array in [["manual_attachment", state.energy_attached_this_turn], ["supporter", state.supporter_used_this_turn], ["retreat", state.retreat_used_this_turn], ["stadium_play", state.stadium_played_this_turn]]:
		result.quotas.append({"id": "player:%d:%s" % [pi, pair[0]], "player": pi, "quota": quota(int(pair[1]), "player", "player:%d:%s" % [pi, pair[0]])})
	if state.stadium_card != null:
		var used: bool = state.stadium_effect_used_turn == state.turn_number and state.stadium_effect_used_player == pi and state.stadium_effect_used_effect_id == state.stadium_card.card_data.effect_id
		var stadium_effect: Variant = processor.get_effect(state.stadium_card.card_data.effect_id)
		var stadium_quota := quota(int(used), "stadium_effect", "player:%d:stadium-effect:%s" % [pi, state.stadium_card.card_data.effect_id])
		if stadium_effect == null: stadium_quota = unknown_quota("stadium_effect_missing")
		elif not stadium_effect.can_use_as_stadium_action(state.stadium_card, state):
			stadium_quota = {}
			for key: String in ["scope", "group", "reset", "used", "limit", "remaining"]: stadium_quota[key] = absent("passive_stadium", "not_applicable")
		result.quotas.append({"id": "player:%d:stadium_effect" % pi, "player": pi,
			"quota": stadium_quota})
	var stages := {"main": "main", "discard": "payment", "search": "search", "assignment_target": "allocation", "attack_target": "target"}
	result.interaction = {"action_id": absent("parent_action_not_recorded"), "source_uid": absent("parent_source_not_recorded"),
		"source_entity": absent("parent_source_not_recorded"),
		"action_kind": absent("parent_action_not_recorded"), "action_index": absent("parent_action_not_recorded"), "in_progress": absent("parent_action_not_recorded"),
		"stage": known(stages[frame.prompt_kind]) if stages.has(frame.prompt_kind) else absent("context_stage_not_reviewed"),
		"parent_committed": absent("commit_phase_not_recorded"), "cancel_allowed": absent("cancel_not_recorded"),
		"cancel_semantics": absent("cancel_not_recorded"), "checkpoint": frame.sequence}
	var selection: Dictionary = frame.public_state.get("decision", {}).get("selection", {})
	for key: String in ["remaining_energy_cost", "remaining_damage_counters", "max_assignments", "max_assignments_per_target", "allow_partial"]:
		result.interaction[key] = known(selection[key], "Host.public_decision.selection") if selection.get(key) != null else absent("current_interaction_quantity_not_provided", "unknown")
	var bridge: Variant = owner.get("_public_input_bridge")
	if bridge != null and bridge.get_script().resource_path.get_file() == "HeadlessMatchBridge.gd":
		_capture_interaction(owner, bridge, result)
	var unique := {}
	for gap: String in result.gaps: unique[gap] = true
	result.gaps = unique.keys()
	result.gaps.sort()
	return result

func _capture_interaction(owner: Variant, bridge: Variant, result: Dictionary) -> void:
	var kind: String = bridge._pending_effect_kind
	var ctx: Dictionary = result.interaction
	ctx.in_progress = known(not kind.is_empty(), "HeadlessMatchBridge.pending_effect")
	if kind.is_empty():
		for key: String in ["action_id", "source_uid", "source_entity", "action_kind", "action_index", "parent_committed", "cancel_allowed", "cancel_semantics"]:
			ctx[key] = absent("no_parent_action", "not_applicable")
		return
	if bridge._pending_effect_player_index != _seat or kind not in ["ability", "trainer", "stadium", "play_stadium", "attack", "granted_attack"]:
		return
	if _interaction_generation != bridge._effect_interaction_generation:
		_interaction_generation = bridge._effect_interaction_generation
		_public_action_number += 1
	ctx.action_id = known("action:%d" % _public_action_number, "public_session_sequence")
	ctx.action_kind = known(kind, "HeadlessMatchBridge.pending_effect_kind")
	if bridge._pending_effect_card != null: ctx.source_uid = known(uid(bridge._pending_effect_card))
	if bridge._pending_effect_slot != null: ctx.source_entity = known(owner._entity_serial_for_slot(bridge._pending_effect_slot))
	else: ctx.source_entity = absent("card_action_without_entity", "not_applicable")
	if bridge._pending_effect_ability_index >= 0: ctx.action_index = known(bridge._pending_effect_ability_index)
	else: ctx.action_index = absent("card_action_without_ability_or_attack_index", "not_applicable")
	if kind in ["ability", "trainer", "stadium", "play_stadium"]:
		ctx.parent_committed = known(false, "HeadlessMatchBridge.executes_after_all_steps")
	var step: Dictionary = bridge._pending_effect_steps[bridge._pending_effect_step_index]
	var stages := {"basic_water_energy_from_hand": "payment", "attach_target": "target", "discard_card": "payment", "look_top_pick": "search", "search_cards": "search", "embrace_energy": "payment", "embrace_target": "target"}
	if stages.has(step.get("id")): ctx.stage = known(stages[step.id], "reviewed_engine_step_id")
	# Do not translate a UI allow_cancel flag into rollback semantics. This bridge
	# has no complete public cancellation contract; keep those fields unsupported.
