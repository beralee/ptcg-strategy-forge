extends SceneTree
## Constructed engine positions followed by real engine methods. No battle/win claim.
const Owner = preload("res://scripts/ai/ptcgdap/host/godot/PtcgDAPAuthorDevelopmentBattleOwner.gd")
const InputProjection = preload("res://scripts/ai/ptcgdap/public/PublicInputV2.gd")
const Registry = preload("res://scripts/ai/ptcgdap/host/godot/GodotSerialRegistry.gd")
var rows: Array = []
var failures: Array = []
var assertions := 0
var fixture_number := 0

func check(value: bool, label: String) -> void:
	assertions += 1
	if not value: failures.append(label)

func card(identity: String, seat: int) -> CardInstance:
	return CardInstance.create(CardData.from_dict(JSON.parse_string(FileAccess.get_file_as_string("res://data/bundled_user/cards/" + identity + ".json"))), seat)

func slot(identity: String, seat: int) -> PokemonSlot:
	var s := PokemonSlot.new()
	s.pokemon_stack.append(card(identity, seat))
	s.turn_played = 1
	return s

func fixture(identity: String = "CS4DaC_137") -> Dictionary:
	fixture_number += 1
	var gsm := GameStateMachine.new()
	var state := GameState.new()
	state.players = [PlayerState.new(), PlayerState.new()]
	state.current_player_index = 0
	state.first_player_index = 1
	state.turn_number = 4
	state.phase = GameState.GamePhase.MAIN
	gsm.game_state = state
	for pi: int in [0, 1]:
		var p: PlayerState = state.players[pi]
		p.player_index = pi
		p.active_pokemon = slot(identity if pi == 0 else "CSV8C_159", pi)
		for i: int in 12: p.deck.append(card("CSVE1C_WAT", pi))
		for i: int in 6: p.prizes.append(card("CSVE1C_FIR", pi))
	var p := state.players[0]
	p.bench = [slot("CSV8C_158", 0), slot("CSV8C_135", 0), slot("CSV8C_135", 0)]
	p.active_pokemon.attached_tool = card("CS6.5C_066", 0)
	p.hand = [card("CSV8C_159", 0), card("CSV2C_127", 0), card("CSV4C_129", 0), card("CSV8C_203", 0), card("CSVE1C_WAT", 0), card("CSVE1C_WAT", 0), card("CSV1C_118", 0)]
	for pi: int in [0, 1]:
		for s: PokemonSlot in state.players[pi].get_all_pokemon(): gsm.effect_processor.register_pokemon_card(s.get_card_data())
	var owners: Array = []
	for seat: int in [0, 1]:
		var o := Owner.new()
		o._gsm = gsm
		o.player_index = seat
		o._match_id = "public-input-v2-witness-" + str(fixture_number)
		o._external_decision_port = RefCounted.new()
		var registry := Registry.new()
		o._serial_registry = registry
		o._match_generation = registry.get_match_generation()
		var counts: Array[int] = []
		for pi: int in [0, 1]:
			var cards: Array = o._collect_player_cards(state.players[pi])
			counts.append(cards.size())
			for c: CardInstance in cards: registry.register_card(c, pi)
		registry.seal_card_inventory(counts)
		o._sync_public_pokemon_entities()
		o.public_input_v2 = InputProjection.new()
		o.public_input_v2.bind(gsm, o._match_id, seat)
		owners.append(o)
	return {"gsm": gsm, "state": state, "owners": owners}

func snap(f: Dictionary, label: String, seat: int = 0, main: bool = true) -> Dictionary:
	var o: Variant = f.owners[seat]
	o._sync_public_pokemon_entities()
	var options: Array = []
	var prompt := "main" if main else "effect_target"
	var semantics := {}
	if main and f.state.current_player_index == seat:
		var builder := Owner.LegalityOnlyActionBuilder.new()
		options = o._options_for_items(builder.build_actions(f.gsm, seat), "")
	else:
		options = [o._make_option(0, f.state.players[seat].active_pokemon, "effect_target", {})]
	var bridge: Variant = o._public_input_bridge
	if bridge != null and not bridge._pending_effect_kind.is_empty():
		var step: Dictionary = bridge._pending_effect_steps[bridge._pending_effect_step_index]
		prompt = o._prompt_kind_for_step(step)
		semantics = o._select_raw_semantics_for_step(step, prompt, false)
		var context := {"pending_effect_card": bridge._pending_effect_card, "pending_effect_slot": bridge._pending_effect_slot,
			"source_card": bridge._pending_effect_card, "cabt_select_type_raw": semantics.type,
			"cabt_select_context_raw": semantics.context, "cabt_option_type_raw": o._ucis_option_type_for_step(step, false)}
		options = o._options_for_items(step.items, o._option_kind_for_prompt(prompt), context)
	var frame: Dictionary = o._build_frame(prompt, options, 1, 1, semantics)
	var payload: Dictionary = o.last_public_input_v2.duplicate(true)
	var schema: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://public_input_v2_contract.json"))
	check(not preload("res://scripts/ai/ptcgdap/public/PublicDecisionFacts.gd").schema_error(payload, schema.payload_schema), label + ":native_schema")
	check(InputProjection.validate_receipt(frame, payload, schema) == "", label + ":native_receipt")
	check(JSON.stringify(payload) == JSON.stringify(o.public_input_v2.capture(o, frame)), label + ":native_determinism")
	rows.append({"label": label, "frame": frame, "supplement": payload})
	return payload

func ability(payload: Dictionary, source_uid: String, index: int = 0) -> Dictionary:
	for row: Dictionary in payload.abilities:
		if row.source_uid == source_uid and row.index == index: return row
	return {}

func dispose(f: Dictionary) -> void:
	for o: Variant in f.owners: o.public_input_v2.close()
	f.gsm.prepare_for_disposal()
	EffectProcessor.cleanup_live_instances_for_tests()

func _initialize() -> void:
	call_deferred("run")

func run() -> void:
	var f := fixture()
	var p: PlayerState = f.state.players[0]
	var start := snap(f, "normal")
	var validation_contract: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://public_input_v2_contract.json"))
	var invalid := start.duplicate(true)
	invalid.binding.sequence += 1
	check(InputProjection.validate_receipt(rows.back().frame, invalid, validation_contract) == "public_input_v2_binding", "native_stale_rejected")
	invalid = start.duplicate(true)
	invalid.abilities[0].quota.used = InputProjection.absent("missing", "unknown")
	invalid.abilities[0].quota.used.value = 0
	check(InputProjection.validate_receipt(rows.back().frame, invalid, validation_contract) == "public_input_v2_fact", "native_unknown_zero_rejected")
	invalid = start.duplicate(true)
	invalid.abilities[0].quota.remaining.value = 0
	check(InputProjection.validate_receipt(rows.back().frame, invalid, validation_contract) == "public_input_v2_quota_arithmetic", "native_bad_quota_rejected")
	check(ability(start, "CS4DaC_137").quota.remaining.value == 1, "native_initial")
	check(ability(start, "CS6.5C_066", 1).quota.remaining.value == 1, "granted_initial")
	check(f.gsm.use_ability(0, p.active_pokemon, 0, []), "native_engine_accepted")
	var used := snap(f, "independent-native-used")
	check(ability(used, "CS4DaC_137").quota.remaining.value == 0, "native_exhausted")
	check(ability(used, "CS6.5C_066", 1).quota.remaining.value == 1, "granted_independent")
	check(not p.active_pokemon.has_ability_used(f.state.turn_number), "boolean_marker_false_despite_exhausted_specific_quota")
	check(f.gsm.use_ability(0, p.active_pokemon, 1, [p.deck[0]]), "vstar_engine_accepted")
	var vstar := snap(f, "vstar-exhausted")
	check(ability(vstar, "CS6.5C_066", 1).quota.remaining.value == 0, "vstar_not_disappeared")
	check(ability(snap(f, "interaction-window", 0, false), "CS4DaC_137").main_availability.status == "unknown", "nonmain_not_false")
	# A public prerequisite may be established in the constructed initial position.
	f.state.turn_number = 3
	f.state.record_knockout_against(0, 1)
	f.state.turn_number = 4
	check(f.gsm.use_ability(0, p.bench[1], 0, []), "shared_engine_accepted")
	var shared := snap(f, "shared-exhausted")
	var shared_count := 0
	for a: Dictionary in shared.abilities:
		if a.source_uid == "CSV8C_135":
			shared_count += 1
			check(a.quota.remaining.value == 0 and a.quota.scope.value == "named_group", "shared_two_entities")
	check(shared_count == 2, "shared_two_present")
	var charm: CardInstance = p.hand.filter(func(c): return c.card_data.get_uid() == "CSV1C_118")[0]
	check(f.gsm.attach_tool(0, charm, p.bench[1]), "hp_tool_engine_accepted")
	var hp := snap(f, "effective-hp-tool")
	var fez: Dictionary = hp.entities.filter(func(e): return e.source_uid == "CSV8C_135")[0]
	check(fez.effective_max_hp.value == fez.printed_hp.value + 50, "effective_hp_differs_from_printed")
	# Drakloak: actual engine effect use, then actual ordinary evolution.
	var drak: PokemonSlot = p.bench[0]
	check(f.gsm.use_ability(0, drak, 0, [{"look_top_pick": [p.deck[0]]}]), "drakloak_engine_accepted")
	check(ability(snap(f, "drakloak-used"), "CSV8C_158").quota.used.value == 1, "drakloak_marker")
	check(f.gsm.evolve_pokemon(0, p.hand[0], drak), "evolution_engine_accepted")
	var evolved := snap(f, "evolved")
	check(ability(evolved, "CSV8C_158").is_empty(), "old_ability_absent_after_evolution")
	check(ability(evolved, "CSV8C_135").quota.remaining.value == 0, "evolution_preserves_shared")
	# Real effect execution, no hand-authored JSON state receipt.
	var cologne := EffectCancelCologne.new()
	cologne.execute(p.hand[0], [], f.state)
	var suppressed := snap(f, "ability-disabled")
	check(suppressed.entities.size() == 5, "board_count")
	check(f.gsm.effect_processor.is_ability_disabled(f.state.players[1].active_pokemon, f.state), "cologne_disabled")
	var reduction := AttackReduceDamageNextTurn.new(30)
	reduction.execute_attack(p.active_pokemon, f.state.players[1].active_pokemon, 0, f.state)
	reduction.execute_attack(p.active_pokemon, f.state.players[1].active_pokemon, 0, f.state)
	var inactive := snap(f, "effects-before-next-turn")
	check(inactive.effects.filter(func(e): return e.type == "reduce_damage_next_turn").size() == 2, "effect_instances_distinct")
	# Exercise the same engine turn transition used by ordinary end-turn.
	f.gsm.end_turn(0)
	var next := snap(f, "opponent-turn", 1)
	check(not f.gsm.effect_processor.is_ability_disabled(f.state.players[1].active_pokemon, f.state), "cologne_restored")
	check(f.gsm.effect_processor.get_defender_modifier(p.active_pokemon, f.state, f.state.players[1].active_pokemon) == -60, "additive_reduction")
	check(next.effects.filter(func(e): return e.type == "reduce_damage_next_turn" and e.condition_met.value).size() == 2, "effect_condition_next_turn")
	f.gsm.end_turn(1)
	var reset := snap(f, "turn-reset")
	check(ability(reset, "CS4DaC_137").quota.remaining.value == 1, "entity_reset")
	check(ability(reset, "CS6.5C_066", 1).quota.remaining.value == 0, "match_quota_not_reset")
	check(f.gsm.effect_processor.get_defender_modifier(p.active_pokemon, f.state) == 0, "effect_expired")
	# Hidden mutation leaves the observer's current semantics identical.
	var before: Dictionary = f.owners[0]._build_public_state()
	for c: CardInstance in f.state.players[1].hand + f.state.players[1].deck + f.state.players[1].prizes:
		c.card_data = card("CSVE1C_PSY", 1).card_data
	f.state.players[1].active_pokemon.effects.append({"type": "private_unreviewed_marker", "secret": "DO_NOT_PROJECT"})
	check(before == f.owners[0]._build_public_state(), "hidden_identity_invariant_v1")
	var hidden := snap(f, "hidden-mutated")
	var reset_semantics := reset.duplicate(true)
	var hidden_semantics := hidden.duplicate(true)
	reset_semantics.erase("binding")
	hidden_semantics.erase("binding")
	reset_semantics.interaction.erase("checkpoint")
	hidden_semantics.interaction.erase("checkpoint")
	check(reset_semantics == hidden_semantics, "hidden_identity_invariant_v2")
	f.gsm.draw_card(1, 2)
	var private_draw := snap(f, "opponent-private-draw")
	var last: Dictionary = private_draw.history.events.back()
	check(last.type == "draw_card" and last.cards.status == "unknown" and last.count.value == 2, "private_draw_redacted")
	# Stadium operation quota is bound to effect identity, not a stale boolean.
	var artazon: CardInstance = null
	var tower: CardInstance = null
	for c: CardInstance in p.hand:
		if c.card_data.get_uid() == "CSV2C_127": artazon = c
		if c.card_data.get_uid() == "CSV8C_203": tower = c
	check(f.gsm.play_stadium(0, artazon), "stadium_play_engine_accepted")
	var stadium := snap(f, "stadium-played")
	check(stadium.quotas.back().quota.remaining.value == 1, "stadium_action_initial")
	check(f.gsm.use_stadium_effect(0, []), "stadium_action_engine_accepted")
	var stadium_used := snap(f, "stadium-used")
	check(stadium_used.quotas.back().quota.remaining.value == 0, "stadium_action_exhausted")
	f.gsm.end_turn(0)
	f.gsm.end_turn(1)
	check(f.gsm.play_stadium(0, tower), "stadium_replacement_engine_accepted")
	var tower_snapshot := snap(f, "stadium-replaced-suppression")
	check(tower_snapshot.quotas.back().quota.remaining.status == "not_applicable", "passive_stadium_no_activation_quota")
	check(tower_snapshot.effects.any(func(e): return e.type == "resolved_tool_suppressed" and e.condition_met.value), "stadium_suppresses_tools")
	fez = tower_snapshot.entities.filter(func(e): return e.source_uid == "CSV8C_135")[0]
	check(fez.effective_max_hp.value == fez.printed_hp.value, "effective_hp_restored_by_tool_suppression")
	dispose(f)
	# A real compiled interaction: observe the two water-attachment steps before
	# the engine commits. Chosen windows are freshly constructed by the Host.
	f = fixture("CSV3C_042")
	p = f.state.players[0]
	var bridge := preload("res://scripts/ai/HeadlessMatchBridge.gd").new()
	bridge.bind(f.gsm)
	for o: Variant in f.owners: o._public_input_bridge = bridge
	var effect: Variant = f.gsm.effect_processor.get_ability_effect(p.active_pokemon, 0, f.state)
	bridge._start_effect_interaction("ability", 0, effect.get_interaction_steps(p.active_pokemon.get_top_card(), f.state), p.active_pokemon.get_top_card(), p.active_pokemon, 0)
	var interaction := snap(f, "real-payment-interaction", 0, false)
	check(interaction.interaction.action_id.status == "known", "interaction_public_parent")
	check(interaction.interaction.source_uid.value == "CSV3C_042" and not interaction.interaction.parent_committed.value, "interaction_source_commit_state")
	bridge._handle_effect_interaction_choice(PackedInt32Array([0]))
	var again := snap(f, "real-target-interaction-next-window", 0, false)
	check(again.interaction.action_id == interaction.interaction.action_id, "interaction_parent_continuity")
	check(bridge._pending_effect_step_index == 1, "real_choice_advances_window")
	bridge._handle_effect_interaction_choice(PackedInt32Array([0]))
	var committed := snap(f, "real-attachment-committed")
	check(not committed.interaction.in_progress.value and p.active_pokemon.attached_energy.size() == 1, "multiwindow_engine_committed")
	check(ability(committed, "CSV3C_042").quota.remaining.status == "unlimited", "unlimited_distinct_from_unknown")
	check(f.gsm.use_ability(0, p.active_pokemon, 0, []), "repeat_unlimited_engine_accepted")
	check(p.active_pokemon.attached_energy.size() == 2, "repeat_unlimited_actual_two_uses")
	snap(f, "unlimited-used-twice")
	bridge.bind(null)
	bridge.free()
	dispose(f)
	f = fixture("CSV7C_059")
	p = f.state.players[0]
	var passive := snap(f, "passive-ability")
	check(ability(passive, "CSV7C_059").kind.value == "passive", "passive_not_activated")
	check(ability(passive, "CSV7C_059").quota.remaining.status == "not_applicable", "passive_no_quota")
	p.active_pokemon.set_status("poisoned", true)
	var poisoned := snap(f, "poison-parameter")
	check(poisoned.entities[0].poison_checkup_hp.value == 10 and poisoned.entities[0].burn_checkup_hp.value == 0, "status_settlement_parameter")
	dispose(f)
	f = fixture()
	p = f.state.players[0]
	var original_active: PokemonSlot = p.active_pokemon
	check(f.gsm.use_ability(0, original_active, 0, []), "leave_active_ability_accepted")
	reduction.execute_attack(original_active, f.state.players[1].active_pokemon, 0, f.state)
	var leave_before := snap(f, "leave-active-before")
	check(BattleFieldTransitionService.switch_active_with_bench(f.state, 0, p.bench[0], "public_input_v2_witness"), "real_field_switch")
	var leave_after := snap(f, "leave-active-after")
	check(ability(leave_after, "CS4DaC_137").id == ability(leave_before, "CS4DaC_137").id, "switch_preserves_entity_identity")
	check(ability(leave_after, "CS4DaC_137").quota.remaining.value == 0, "switch_does_not_reset_specific_ability")
	check(not leave_after.effects.any(func(e): return e.type == "reduce_damage_next_turn"), "leave_active_expires_protection")
	check(BattleFieldTransitionService.switch_active_with_bench(f.state, 0, original_active, "public_input_v2_witness"), "real_field_switch_back")
	check(ability(snap(f, "return-active"), "CS4DaC_137").quota.remaining.value == 0, "return_active_does_not_reset_quota")
	# Construct a pending prize choice, then run the real resolver for each view.
	f.gsm._pending_prize_player_index = 1
	f.gsm._pending_prize_remaining = 1
	f.gsm._pending_prize_resume_mode = "resume_main"
	check(f.gsm.resolve_take_prize(1, 0), "real_prize_resolver")
	var prize_public := snap(f, "opponent-private-prize")
	var prize_private := snap(f, "owner-visible-prize", 1, false)
	check(prize_public.history.events.back().cards.status == "unknown", "opponent_prize_identity_redacted")
	check(prize_private.history.events.back().cards.status == "known" and prize_private.history.events.back().visibility == "seat", "owner_prize_identity_visible")
	var shuffle_before: Dictionary = f.owners[0]._build_public_state()
	f.state.players[1].shuffle_deck()
	check(shuffle_before == f.owners[0]._build_public_state(), "real_hidden_shuffle_no_identity_or_order_change")
	var shuffle_snapshot := snap(f, "opponent-shuffled")
	check(shuffle_snapshot.gaps.has("unlogged_zone_moves"), "unlogged_shuffle_not_claimed_complete")
	dispose(f)
	var file := FileAccess.open(OS.get_cmdline_user_args()[0], FileAccess.WRITE)
	file.store_string(JSON.stringify({"rows": rows, "failures": failures, "assertions": assertions}, "\t"))
	file.close()
	print("PUBLIC_INPUT_V2 " + JSON.stringify({"assertions": assertions, "failures": failures, "rows": rows.size()}))
	quit(0 if failures.is_empty() else 1)
