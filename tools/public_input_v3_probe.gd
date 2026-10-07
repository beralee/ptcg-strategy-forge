extends "res://public_input_v2_probe.gd"
const V3 = preload("res://scripts/ai/ptcgdap/public/PublicInputV3.gd")

func check(value: bool, label: String) -> void:
	if label == "unlogged_shuffle_not_claimed_complete":
		value = rows.back().supplement.history.events.any(func(e): return e.type == "shuffle_deck")
		label = "formerly_unlogged_shuffle_now_journaled"
	super.check(value, label)

func fixture(identity: String = "CS4DaC_137") -> Dictionary:
	var f: Dictionary = super.fixture(identity)
	for o: Variant in f.owners:
		o.public_input_v2.close()
		o.public_input_v2 = V3.new()
		o.public_input_v2.bind(f.gsm, o._match_id, o.player_index)
		o.public_input_v2._owner = o
		o.public_input_v2._reconcile()
	return f

func rebind_fixture(f: Dictionary) -> void:
	for o: Variant in f.owners:
		var registry := Registry.new()
		o._serial_registry = registry
		o._match_generation = registry.get_match_generation()
		var counts: Array[int] = []
		for pi: int in [0, 1]:
			var cards: Array = o._collect_player_cards(f.state.players[pi])
			counts.append(cards.size())
			for c: CardInstance in cards: registry.register_card(c, pi)
		registry.seal_card_inventory(counts)
		o._sync_public_pokemon_entities()
		o.public_input_v2._previous = {}
		o.public_input_v2._reconcile()

func connect_bridge(f: Dictionary) -> Variant:
	var bridge := preload("res://scripts/ai/HeadlessMatchBridge.gd").new()
	bridge.bind(f.gsm)
	for o: Variant in f.owners: o._public_input_bridge = bridge
	return bridge

func snap(f: Dictionary, label: String, seat: int = 0, main: bool = true) -> Dictionary:
	var o: Variant = f.owners[seat]
	var bridge: Variant = o._public_input_bridge
	if bridge == null or bridge._field_interaction_mode != "counter_distribution":
		var value: Dictionary = super.snap(f, label, seat, main)
		rows.back().frame = o.last_public_observation.frame.duplicate(true)
		rows.back().supplement = o.last_public_observation.input.duplicate(true)
		value = rows.back().supplement
		var schema: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://public_input_v2_contract.json"))
		check(V3.validate_receipt(rows.back().frame, value, schema) == "", label + ":v3_native_receipt")
		check(o.last_public_observation == {"profile": "ptcg-public-input-v3", "frame": rows.back().frame, "input": value}, label + ":transport_exact")
		return value
	o._sync_public_pokemon_entities()
	var step: Dictionary = bridge._pending_effect_steps[bridge._pending_effect_step_index]
	var semantics: Dictionary = o._select_raw_semantics_for_step(step, "assignment_source", false)
	o._add_public_assignment_limits(semantics, step)
	var context := {"pending_effect_card": bridge._pending_effect_card, "pending_effect_slot": bridge._pending_effect_slot,
		"cabt_select_type_raw": semantics.type, "cabt_select_context_raw": semantics.context,
		"cabt_option_type_raw": o._ucis_option_type_for_step(step, false),
		"remaining_damage_counters": int(step.total_counters) - bridge._get_counter_distribution_assigned_total(),
		"pending_counter_assignments": bridge._field_interaction_assignment_entries}
	var options: Array = []
	for i: int in step.target_items.size(): options.append(o._make_option(i, step.target_items[i], "assignment_target", context))
	var frame: Dictionary = o._build_frame("assignment_target", options, 1, 1, semantics)
	var payload: Dictionary = o.last_public_input_v2.duplicate(true)
	var schema: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://public_input_v2_contract.json"))
	check(V3.validate_receipt(frame, payload, schema) == "", label + ":native_receipt")
	check(payload == o.public_input_v2.capture(o, frame), label + ":deterministic")
	rows.append({"label": label, "frame": o.last_public_observation.frame.duplicate(true), "supplement": o.last_public_observation.input.duplicate(true)})
	return rows.back().supplement

func interactions() -> void:
	var f := fixture()
	var p: PlayerState = f.state.players[0]
	p.hand[0].card_data = card("CSV1C_112", 0).card_data
	p.deck[0].card_data = card("CSV8C_158", 0).card_data
	rebind_fixture(f)
	var bridge: Variant = connect_bridge(f)
	check(bridge._try_play_trainer_with_interaction(0, p.hand[0]), "ultra_ball_real_bridge_start")
	var payment := snap(f, "v3-ultra-ball-payment", 0, false)
	check(payment.interaction.stage.value == "payment" and payment.interaction.parent_committed.value == false, "discard_stage_before_commit")
	bridge._handle_effect_interaction_choice(PackedInt32Array([0, 1]))
	var search := snap(f, "v3-ultra-ball-search", 0, false)
	check(search.interaction.stage.value == "search" and search.interaction.action_id == payment.interaction.action_id, "search_parent_continuity")
	check(search.history.checkpoint > payment.history.checkpoint, "search_information_checkpoint")
	check(not search.interaction.cancel_allowed.value and search.interaction.cancel_semantics.value == "decline_optional", "optional_search_is_not_rollback")
	var step: Dictionary = bridge._pending_effect_steps[bridge._pending_effect_step_index]
	var choice := -1
	for i: int in step.items.size():
		if step.items[i] is CardInstance and step.items[i].card_data.is_pokemon(): choice = i
	check(choice >= 0, "search_has_real_pokemon")
	bridge._handle_effect_interaction_choice(PackedInt32Array([choice]))
	var committed := snap(f, "v3-ultra-ball-committed")
	check(p.discard_pile.size() == 3, "cost_and_trainer_discarded")
	check(committed.history.events.any(func(e): return e.type == "public_reveal"), "search_result_public_reveal_event")
	check(committed.history.events.any(func(e): return e.type == "shuffle_deck"), "search_shuffle_event")
	bridge.bind(null)
	bridge.free()
	dispose(f)
	# Dragapult's real compiled counter allocation: partial assignments do not
	# apply damage until the parent attack commits.
	f = fixture("CSV8C_159")
	p = f.state.players[0]
	var rival: PlayerState = f.state.players[1]
	rival.bench.append(slot("CSV8C_135", 1))
	rival.bench.append(slot("CSV8C_135", 1))
	p.active_pokemon.attached_energy.append(p.hand.pop_back())
	p.active_pokemon.attached_energy.back().card_data = card("CSVE1C_PSY", 0).card_data
	p.active_pokemon.attached_energy.append(p.hand.pop_back())
	p.active_pokemon.attached_energy.back().card_data = card("CSVE1C_FIR", 0).card_data
	rebind_fixture(f)
	bridge = connect_bridge(f)
	check(bridge._try_use_attack_with_interaction(0, p.active_pokemon, 1), "dragapult_attack_real_bridge_start")
	var allocation := snap(f, "v3-dragapult-allocation", 0, false)
	check(allocation.interaction.remaining_damage_counters.value == 6, "allocation_initial_six")
	bridge._on_counter_distribution_amount_chosen(2)
	bridge._handle_counter_distribution_target(0)
	var remainder := snap(f, "v3-dragapult-allocation-remaining", 0, false)
	check(remainder.interaction.remaining_damage_counters.value == 4 and remainder.interaction.action_id == allocation.interaction.action_id, "allocation_remaining_four_same_parent")
	check(rival.bench[0].damage_counters == 0, "allocation_not_prematurely_applied")
	bridge._on_counter_distribution_amount_chosen(4)
	bridge._handle_counter_distribution_target(1)
	check(rival.bench[0].damage_counters == 20 and rival.bench[1].damage_counters == 40, "allocation_engine_applies_exact_amounts")
	snap(f, "v3-dragapult-attack-committed", 1)
	bridge.bind(null)
	bridge.free()
	dispose(f)
	# Real return-to-hand effect clears entity counters; shared player quota
	# survives the destruction and recreation of the public entity.
	f = fixture()
	p = f.state.players[0]
	f.state.turn_number = 3
	f.state.record_knockout_against(0, 1)
	f.state.turn_number = 4
	check(f.gsm.use_ability(0, p.bench[1], 0, []), "shared_before_bounce")
	var before := snap(f, "v3-before-bounce")
	var old_entity: int = ability(before, "CSV8C_135").entity
	var bounced: CardInstance = p.bench[1].get_top_card()
	EffectProfTuro.new().execute(card("CSV6C_125", 0), [{"prof_turo_target": [p.bench[1]]}], f.state)
	snap(f, "v3-after-bounce")
	check(f.gsm.play_basic_to_bench(0, bounced), "replay_bounced_pokemon")
	var returned := snap(f, "v3-reentered-field")
	check(returned.abilities.filter(func(a): return a.source_uid == "CSV8C_135").all(func(a): return a.quota.remaining.value == 0), "shared_quota_survives_reentry")
	check(not returned.entities.any(func(e): return e.entity == old_entity), "old_entity_retired_after_reentry")
	dispose(f)

func run() -> void:
	interactions()
	marker_witnesses()
	history_ring_witness()
	var f := fixture("CSV8C_159")
	var before := snap(f, "v3-journal-start")
	check(before.version == 3, "v3_version")
	check(f.owners[0].last_public_observation.profile == "ptcg-public-input-v3", "host_transport_envelope")
	var schema: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://public_input_v2_contract.json"))
	var frame: Dictionary = rows.back().frame
	var renamed: Dictionary = frame.duplicate(true)
	_rename_card_serials(renamed)
	check(f.owners[0].public_input_v2.make_observation(renamed, before) == f.owners[0].public_input_v2.make_observation(frame, before), "private_registry_renumbering_same_entire_v3_observation")
	var invalid := before.duplicate(true)
	invalid.history.snapshot[1].cards = V3.known(["CSV8C_159"])
	check(V3.validate_receipt(frame, invalid, schema) == "public_input_v3_hidden_cards", "native_v3_hidden_zone_rejected")
	invalid = before.duplicate(true)
	invalid.history.snapshot_cursor += 1
	check(V3.validate_receipt(frame, invalid, schema) == "public_input_v3_snapshot_cursor", "native_v3_cursor_rejected")
	invalid = before.duplicate(true)
	invalid.evaluations[0].kind = "exact"
	check(V3.validate_receipt(frame, invalid, schema) == "public_input_v3_false_exact", "native_v3_false_exact_rejected")
	invalid = before.duplicate(true)
	invalid.entities.append(invalid.entities[0].duplicate(true))
	check(V3.validate_receipt(frame, invalid, schema) == "public_input_v3_duplicate_entity", "native_v3_duplicate_entity_rejected")
	var p: PlayerState = f.state.players[0]
	# A direct effect-side draw bypasses GameStateMachine.action_logged.
	p.draw_card()
	var moved := snap(f, "v3-direct-effect-draw")
	check(moved.history.events.any(func(e): return e.type == "move" and e.from_zone.value == "deck" and e.to_zone.value == "hand"), "unlogged_draw_reconciled")
	p.shuffle_deck()
	var shuffled := snap(f, "v3-direct-effect-shuffle")
	check(shuffled.history.events.any(func(e): return e.type == "shuffle_deck" and e.origin == "engine_shuffle"), "unlogged_shuffle_reconciled")
	check(shuffled.evaluations.any(func(e): return e.attacker == shuffled.entities[0].entity and e.damage_hp.status == "known"), "bounded_engine_damage_receipt")
	var a: PokemonSlot = p.active_pokemon
	var reduction := AttackReduceDamageNextTurn.new(30)
	reduction.execute_attack(a, f.state.players[1].active_pokemon, 0, f.state)
	reduction.execute_attack(a, f.state.players[1].active_pokemon, 0, f.state)
	var first := snap(f, "v3-effect-instances")
	var ids: Array = first.effects.filter(func(e): return e.type == "reduce_damage_next_turn").map(func(e): return e.id)
	a.effects.remove_at(a.effects.size()-2)
	var removed := snap(f, "v3-one-identical-effect-removed")
	var kept: Array = removed.effects.filter(func(e): return e.type == "reduce_damage_next_turn")
	check(kept.size() == 1 and kept[0].id == ids[1], "identical_marker_survivor_keeps_instance_id")
	dispose(f)
	super.run()

func _rename_card_serials(value: Variant) -> void:
	if value is Dictionary:
		for key: Variant in value:
			if key in ["serial", "card_serial", "source_serial", "target_serial"] and value[key] != null: value[key] = int(value[key]) + 98765
			else: _rename_card_serials(value[key])
	elif value is Array:
		for child: Variant in value: _rename_card_serials(child)

func marker_witnesses() -> void:
	var f := fixture("CSV8C_159")
	var a: PokemonSlot = f.state.players[0].active_pokemon
	var d: PokemonSlot = f.state.players[1].active_pokemon
	AttackSelfLockUntilLeaveActive.new(1).execute_attack(a, d, 1, f.state)
	AttackDefenderAttackLockNextTurn.new("evolved_only").execute_attack(a, d, 1, f.state)
	var protection := AttackCoinFlipPreventDamageAndEffectsNextTurn.new(f.gsm.coin_flipper)
	# Actual deterministic engine coin draws, no fabricated effect JSON.
	f.gsm.coin_flipper._rng.seed = 713
	for attempt: int in 32:
		protection.execute_attack(a, d, 1, f.state)
		if a.effects.any(func(e): return e.type == "prevent_attack_damage_and_effects"): break
	var pending := snap(f, "v3-marker-protection-pending")
	check(pending.history.events.any(func(e): return e.type == "coin_flip" and e.random_outcome.value == "heads"), "completed_coin_signal_public_no_rng")
	check(pending.effects.any(func(e): return e.type == "attack_lock_until_leave_active" and e.condition_met.value), "persistent_attack_lock_projected")
	check(pending.effects.any(func(e): return e.type == "prevent_attack_damage_and_effects" and not e.condition_met.value), "protection_waits_for_opponent_turn")
	f.gsm.end_turn(0)
	var effective := snap(f, "v3-marker-protection-effective", 1)
	check(effective.effects.any(func(e): return e.type == "prevent_attack_damage_and_effects" and e.condition_met.value and e.expiry_player.value == 1), "protection_opponent_boundary")
	check(effective.effects.any(func(e): return e.type == "defender_attack_lock" and e.condition_met.value), "defender_lock_engine_condition")
	check(effective.evaluations.any(func(e): return e.damage_prevented.value == true and e.effects_prevented.value == true), "engine_immunity_predicates")
	f.gsm.end_turn(1)
	var expired := snap(f, "v3-marker-protection-expired")
	check(expired.effects.filter(func(e): return e.type == "prevent_attack_damage_and_effects").all(func(e): return not e.condition_met.value), "protection_expires_at_opponent_end")
	check(BattleFieldTransitionService.switch_active_with_bench(f.state, 0, f.state.players[0].bench[0], "v3_marker_witness"), "marker_switch_real_engine")
	var left := snap(f, "v3-marker-left-active")
	check(not left.effects.any(func(e): return e.type == "attack_lock_until_leave_active"), "persistent_lock_cleared_on_leave_active")
	dispose(f)

func history_ring_witness() -> void:
	var f := fixture()
	snap(f, "v3-history-ring-anchor")
	for i: int in 520:
		f.state.players[1].shuffle_deck()
		for o: Variant in f.owners: o.public_input_v2._reconcile()
	var truncated := snap(f, "v3-history-ring-truncated")
	check(truncated.history.events.size() == 512 and truncated.history.cursor == 520, "real_shuffle_journal_bounded")
	check(not truncated.history.complete and truncated.history.first_available == 9, "real_journal_truncation_explicit")
	check(truncated.history.events.all(func(e): return e.type == "shuffle_deck" and e.cards.status != "known" and e.knowledge == "invalidate_hidden_associations"), "shuffle_ring_has_no_hidden_identity")
	dispose(f)
