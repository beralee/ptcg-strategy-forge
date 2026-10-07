extends RefCounted
## Public research mirror of public_cursed_route.py. No engine/private access.
static var _scope: Dictionary = {}
const Access = preload("res://scripts/ai/ptcgdap/public/PublicAttackAccess.gd")
const PULT = "CSV8C_159"
const CLOPS = "CSV8C_082"
const NOIR = "CSV8C_083"
const DUSKULL = "CSV8C_081"
const CANDY = "CSVH1C_045"
const GHOSTS = {CLOPS: 50, NOIR: 130}

static func uses(document: Dictionary) -> bool:
	for r: Dictionary in document.get("rules", []):
		for q: Dictionary in r.get("when", []) + r.get("score_terms", []):
			if str(q.get("fact", "")).begins_with("damage.option.cursed_") or str(q.get("fact", "")).begins_with("damage.option.cursed2_"): return true
	return false

static func uses_spread(document: Dictionary) -> bool:
	for r: Dictionary in document.get("rules", []):
		for q: Dictionary in r.get("when", []) + r.get("score_terms", []):
			if str(q.get("fact", "")).begins_with("damage.option.cursed2_"): return true
	return false

static func attack_outcomes(p: Dictionary, board: Array, active: int) -> Array:
	var projected: Array = board.duplicate(true); var defender := find_body(projected, active)
	if not defender.get("immune", false): defender.hp -= p.attack_damage
	var budget := int(p.get("attack_counters", 0))
	for b: Dictionary in board:
		if b.get("counter_guard", false) and b.hp > 0: budget = 0
	if budget == 0: return [projected]
	var targets := projected.filter(func(b: Dictionary) -> bool: return b.id != active and b.hp > 0)
	targets.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.id < b.id)
	if targets.is_empty(): return [projected]
	var best := -1; var rows := []
	for mask: int in (1 << targets.size()):
		var cost := 0; var gain := 0; var ids := {}
		for i: int in targets.size():
			if mask & (1 << i):
				cost += ceili(float(targets[i].hp) / 10.0); gain += int(targets[i].prize); ids[targets[i].id] = true
		if cost > budget or gain < best: continue
		if gain > best: best = gain; rows = []
		var value: Array = projected.duplicate(true)
		for b: Dictionary in value:
			if ids.has(b.id): b.hp = 0
		rows.append(value)
	return rows

static func less(a: Array, b: Array) -> bool:
	for i: int in a.size():
		if a[i] != b[i]: return a[i] < b[i]
	return false

static func ko_prizes(board: Array, damage: Dictionary, pool: int) -> int:
	var mandatory := 0; var debts := []
	for b: Dictionary in board:
		var hp := int(b.hp) - int(damage.get(b.id, 0))
		if hp <= 0: mandatory += int(b.prize)
		else: debts.append([hp, int(b.prize)])
	var best := mandatory
	for mask: int in (1 << debts.size()):
		var cost := 0; var gain := mandatory
		for i: int in debts.size():
			if mask & (1 << i): cost += debts[i][0]; gain += debts[i][1]
		if cost <= pool: best = maxi(best, gain)
	return best

static func response_prizes(own: Array, enemy: Array) -> int:
	if enemy.is_empty(): return 0
	var frost := 0; var pool := 0; var passive := {}
	for e: Dictionary in own + enemy:
		if e.get("frost", false): frost += 20
	for o: Dictionary in own: passive[o.id] = (frost if o.get("ability", false) else 0) + int(o.get("status_tick", 0))
	for e: Dictionary in enemy: pool += int(e.get("counters", 0))
	var best := ko_prizes(own, passive, pool)
	for attacker: Dictionary in enemy:
		for target: Dictionary in own:
			var damage: Dictionary = passive.duplicate()
			damage[target.id] += int(attacker.attack) * int(target.get("weakness", {}).get(attacker.get("type", ""), 1))
			best = maxi(best, ko_prizes(own, damage, pool + int(attacker.get("split", 0))))
	return best

static func find_body(board: Array, identity: int) -> Dictionary:
	for b: Dictionary in board:
		if b.id == identity: return b
	return {}

static func with_values(base: Dictionary, values: Dictionary) -> Dictionary:
	var result := base.duplicate(true); result.merge(values, true); return result

static func evaluate(p: Dictionary, source: int, amount: int, target: int) -> Dictionary:
	var denied := {"allowed": false, "reason": "invalid_route", "prizes": 0, "baseline_prizes": 0,
		"response_prizes": 0, "terminal": false, "target": target, "source": source}
	var own: Array = p.own.duplicate(true); var enemy: Array = p.enemy.duplicate(true)
	if find_body(own, source).is_empty() or find_body(enemy, target).is_empty(): return denied
	if p.enemy_prizes <= 1: return with_values(denied, {"reason": "give_last_prize"})
	own = own.filter(func(b: Dictionary) -> bool: return b.id != source)
	if own.is_empty(): return with_values(denied, {"reason": "own_last_body"})
	var baseline := 0; var total_prizes := 0
	for b: Dictionary in enemy: total_prizes += int(b.prize)
	if p.attack_ready and p.own_active == p.attacker:
		for row: Array in attack_outcomes(p, enemy, int(p.enemy_active)):
			var gain := 0
			for b: Dictionary in row:
				if b.hp <= 0: gain += int(b.prize)
			baseline = maxi(baseline, gain)
	if baseline > 0 and (baseline >= p.own_prizes or baseline >= total_prizes):
		return with_values(denied, {"reason": "attack_already_wins", "baseline_prizes": baseline})
	var struck := find_body(enemy, target); struck.hp -= amount
	var immediate := 0
	for b: Dictionary in enemy:
		if b.hp <= 0: immediate += int(b.prize)
	enemy = enemy.filter(func(b: Dictionary) -> bool: return b.hp > 0)
	if immediate >= p.own_prizes or enemy.is_empty():
		return with_values(denied, {"allowed": true, "reason": "terminal_blast", "prizes": immediate, "baseline_prizes": baseline, "terminal": true})
	if not p.attack_ready or find_body(own, int(p.attacker)).is_empty() or p.own_active not in [p.attacker, source]:
		return with_values(denied, {"reason": "attack_not_funded_or_accessible"})
	var promotions: Array = enemy if target == p.enemy_active and struck.hp <= 0 else [find_body(enemy, int(p.enemy_active))]
	var worst := {}; var worst_key := []
	for active: Dictionary in promotions:
		for board: Array in attack_outcomes(p, enemy, int(active.id)):
			var attack_gain := 0
			for b: Dictionary in board:
				if b.hp <= 0: attack_gain += int(b.prize)
			var gain := immediate + attack_gain
			var survivors := board.filter(func(b: Dictionary) -> bool: return b.hp > 0)
			var terminal: bool = gain >= p.own_prizes or survivors.is_empty()
			var risk := 0 if terminal else response_prizes(own, survivors)
			var allowed: bool = terminal or (attack_gain > 0 and gain > baseline and risk < p.enemy_prizes - 1)
			var reason := "terminal_attack" if terminal else ("attack_does_not_convert" if attack_gain == 0 else ("no_extra_prize" if gain <= baseline else ("response_can_finish" if risk >= p.enemy_prizes - 1 else "converted_and_response_bounded")))
			var key := [int(allowed), int(terminal), gain, -risk]
			if worst.is_empty() or less(key, worst_key):
				worst_key = key
				worst = with_values(denied, {"allowed": allowed, "reason": reason, "prizes": gain, "baseline_prizes": baseline, "response_prizes": risk, "terminal": terminal})
	return worst

static func best_route(p: Dictionary, source: int, amount: int) -> Dictionary:
	var best := {}; var best_key := []
	var enemies: Array = p.enemy.duplicate(); enemies.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return a.id < b.id)
	for b: Dictionary in enemies:
		var r := evaluate(p, source, amount, int(b.id))
		var key := [int(r.allowed), int(r.terminal), int(r.prizes) - int(r.baseline_prizes), -int(r.response_prizes), -int(r.target)]
		if best.is_empty() or less(best_key, key): best = r; best_key = key
	return best

static func fundable_threat(slot: Dictionary, entity: Dictionary, cards: Dictionary) -> Array:
	var uid: String = slot.local_card_uid
	var future := {"CSV8C_157": PULT, "CSV8C_158": PULT, DUSKULL: NOIR, CLOPS: NOIR,
		"CSV10C_146": "CSV10C_148", "CSV10C_147": "CSV10C_148", "CSV10C_028": "CSV10C_030",
		"CSV10C_029": "CSV10C_030", "CSV9.5C_043": "CSV7C_059", "CSV10C_009": "CSV10C_010"}
	var power := 0; var split := 0; var uids := [uid]
	if future.has(uid): uids.append(future[uid])
	for target_uid: String in uids:
		var card: Dictionary = cards[target_uid]
		var allowance := 3 if card.stage != "Basic" and slot.prize_value == 1 else 2
		if target_uid == "CSV8C_028": allowance += 1
		for a: Dictionary in card.get("attacks", []):
			var costs := [a.cost]
			if target_uid == uid:
				for observed: Dictionary in entity.attacks:
					if observed.attack_index == a.attack_index: costs = observed.cost_candidates
			if uid not in ["CSV10C_161", "CSV10C_175", "CSV8C_172"] and Access.energy_debt(costs, entity.energies) > allowance: continue
			power = maxi(power, 10000 if a.active_damage == null else int(a.active_damage))
			split = maxi(split, maxi(int(a.get("bench_damage", 0)), 60 if target_uid == PULT and a.attack_index == 1 else 0))
	if power > 0: power += 100 if uid in ["CSV10C_161", "CSV10C_175"] else 30
	return [power, split]

static func body(slot: Dictionary, entity: Dictionary, cards: Dictionary, anticipate: bool = false, funded: bool = false) -> Dictionary:
	var card: Dictionary = cards[slot.local_card_uid]; var uid: String = slot.local_card_uid
	var power := 0; var split := 0
	for a: Dictionary in card.get("attacks", []):
		power = maxi(power, 10000 if a.get("active_damage") == null else int(a.active_damage))
		split = maxi(split, int(a.get("bench_damage", 0)))
	if uid in ["CSV10C_161", "CSV10C_175"]: power += 100
	if slot.get("attached_tool_uid") != null: power = 10000
	if uid == PULT: split = maxi(split, 60)
	var counters := int(GHOSTS.get(uid, 30 if uid == "CSV8C_094" else 0))
	var frost: bool = uid == "CSV7C_059"
	if anticipate:
		if uid in [DUSKULL, CLOPS]: counters = 130
		if uid in ["CSV8C_157", "CSV8C_158"]: power = maxi(power, 200); split = maxi(split, 60)
		if uid in ["CSV10C_146", "CSV10C_147"]: power = maxi(power, 180); split = maxi(split, 30)
		if uid in ["CSV10C_028", "CSV10C_029"]: power = 10000
		if uid == "CSV9.5C_043": power = maxi(power, 60); frost = true
		if uid == "CSV10C_009": power = maxi(power, 120)
		if uid not in ["CSV10C_161", "CSV10C_175"] and power > 0: power += 30
		if funded:
			var threat := fundable_threat(slot, entity, cards); power = threat[0]; split = threat[1]
	var weakness := {}; weakness[card.get("weakness_energy", "")] = int(card.get("weakness_multiplier", 1))
	return {"id": int(slot.entity_serial), "hp": int(slot.remaining_hp), "prize": int(slot.prize_value),
		"attack": power, "split": split, "counters": counters, "frost": frost, "ability": card.get("has_ability", false),
		"immune": uid == "CSV10C_010" and not entity.get("ability_disabled", false), "type": card.get("energy_type", ""), "weakness": weakness,
		"counter_guard": uid == "CSV10C_052" and not entity.get("ability_disabled", false),
		"status_tick": (20 if "poisoned" in entity.get("conditions", []) else 0) + (40 if "burned" in entity.get("conditions", []) else 0)}

static func route(p: Dictionary, attackers: Array, source: int, amount: int) -> Dictionary:
	var best := {}; var best_key := []
	for a: int in attackers:
		p.attacker = a
		p.attack_ready = a != -1
		var r := best_route(p, source, amount)
		var key := [int(r.get("allowed", false)), int(r.get("terminal", false)), int(r.get("prizes", 0)), -int(r.get("response_prizes", 0))]
		if best.is_empty() or less(best_key, key): best = r; best_key = key
	return best

static func calculate(frame: Dictionary, cards: Dictionary, include_spread: bool = false) -> Dictionary:
	var options := {}
	for o: Dictionary in frame.options:
		options[str(o.index)] = {"cursed_allowed": false, "cursed_preferred": false, "cursed_evolve": false, "cursed_preserve": false, "cursed_value": 0}
		if include_spread:
			var values := {"cursed2_prepare": false}
			for k: String in options[str(o.index)]: values[k.replace("cursed_", "cursed2_")] = options[str(o.index)][k]
			options[str(o.index)] = values
	var result := {"options": options, "routes": [], "scope": "public-board-full-funding-stress-v1"}
	var public: Dictionary = frame.get("public_state", {}); var decision: Dictionary = public.get("decision", {})
	if decision.is_empty() or frame.prompt_kind not in ["main", "effect_target", "card_selection", "evolve"]: return result
	var own: Dictionary = public.self; var enemy: Dictionary = public.opponent
	if own.active.is_empty() or enemy.active.is_empty(): return result
	var table := {}
	for e: Dictionary in decision.entities: table[int(e.entity_serial)] = e
	var slots: Array = own.active + own.bench + enemy.active + enemy.bench
	if _scope.is_empty(): _scope = JSON.parse_string(FileAccess.get_file_as_string("res://contracts/ptcgdap/public_gust_scope_v1.json"))
	var reviewed: Dictionary = _scope
	var stadium: Variant = decision.get("stadium", {}).get("card_uid")
	if stadium != null and reviewed.stadiums.get(stadium) != cards.get(stadium, {}).get("effect_id"): return result
	for s: Dictionary in slots:
		if not table.has(int(s.entity_serial)) or not cards.has(s.local_card_uid) or s.remaining_hp <= 0: return result
		var card: Dictionary = cards[s.local_card_uid]
		if s.get("attached_tool_uid") != null or (card.get("has_ability", false) and card.get("effect_id") != reviewed.board_abilities.get(s.local_card_uid)): return result
	var active := int(own.active[0].entity_serial); var op_active := int(enemy.active[0].entity_serial)
	var own_bodies := []; var enemy_bodies := []; var attackers := []; var ghosts := {}
	for s: Dictionary in own.active + own.bench:
		var identity := int(s.entity_serial); var e: Dictionary = table[identity]
		own_bodies.append(body(s, e, cards))
		if GHOSTS.has(s.local_card_uid): ghosts[identity] = s
		if s.local_card_uid != PULT or not e.get("conditions", []).is_empty(): continue
		var ready := false
		for a: Dictionary in e.attacks:
			if a.attack_index == 1 and a.energy_ready: ready = true
		if not ready: continue
		if frame.prompt_kind == "main" and identity == active:
			var legal := false
			for o: Dictionary in frame.options:
				if o.kind == "attack" and o.get("attack_index") == 1 and o.get("source_uid") == PULT: legal = true
			if not legal: continue
		attackers.append(identity)
	for s: Dictionary in enemy.active + enemy.bench: enemy_bodies.append(body(s, table[int(s.entity_serial)], cards, true, include_spread))
	if attackers.is_empty(): attackers.append(-1)
	var p := {"own": own_bodies, "enemy": enemy_bodies, "own_active": active, "enemy_active": op_active,
		"own_prizes": int(own.prizes_remaining), "enemy_prizes": int(enemy.prizes_remaining), "attack_ready": true, "attack_damage": 200, "attacker": 0}
	if include_spread: p.attack_counters = 6
	var actual := {}; var sources := ghosts.keys(); sources.sort()
	for source: int in sources:
		if table[source].get("ability_disabled", false): continue
		var r := route(p, attackers, source, int(GHOSTS[ghosts[source].local_card_uid])); actual[source] = r; result.routes.append(r)
	var candy_routes := {}
	for s: Dictionary in own.active + own.bench:
		var e: Dictionary = table[int(s.entity_serial)]
		if s.local_card_uid == DUSKULL and not e.played_this_turn and not e.evolved_this_turn and not decision.self.is_first_turn:
			candy_routes[int(s.entity_serial)] = route(p, attackers, int(s.entity_serial), 130)
	for o: Dictionary in frame.options:
		var m: Dictionary = options[str(o.index)]; var source: Variant = o.get("source_entity_serial"); var uid: Variant = o.get("source_uid")
		if include_spread:
			var values := {}
			for k: String in m: values[k.replace("cursed2_", "cursed_")] = m[k]
			m = values
		if source != null: source = int(source)
		if o.kind == "use_ability" and GHOSTS.has(uid) and o.get("ability_index") == 0 and ghosts.has(source) and ghosts[source].local_card_uid == uid:
			var r: Dictionary = actual.get(source, {}); m.cursed_allowed = r.get("allowed", false); m.cursed_value = 1000 * int(r.get("prizes", 0)) - 100 * int(r.get("response_prizes", 0))
			for s: int in actual:
				if ghosts[s].local_card_uid == uid and (not actual[s].allowed or actual[s].target != r.get("target")): m.cursed_allowed = false
		if o.kind == "effect_target" and GHOSTS.has(uid):
			var count := 0; var preferred := true
			for s: int in actual:
				if ghosts[s].local_card_uid != uid: continue
				count += 1; var r: Dictionary = actual[s]
				if not r.allowed or r.target != o.get("target_entity_serial"): preferred = false
			m.cursed_preferred = count > 0 and preferred
		var target: Variant = o.get("target_entity_serial")
		if target != null: target = int(target)
		if o.kind == "evolve" and o.get("card_uid") == NOIR and ghosts.has(target):
			var small: Dictionary = actual.get(target, {}); var large := route(p, attackers, target, 130)
			var preserve: bool = small.get("allowed", false) and not less([int(small.get("terminal", false)), int(small.get("prizes", 0))], [int(large.get("terminal", false)), int(large.get("prizes", 0))])
			m.cursed_preserve = preserve; m.cursed_evolve = large.get("allowed", false) and not preserve
		if o.kind == "play_trainer" and o.get("card_uid") == CANDY:
			var in_hand := false
			for h: Dictionary in own.hand:
				if h.local_card_uid == NOIR: in_hand = true
			if in_hand:
				for r: Dictionary in candy_routes.values():
					if r.get("allowed", false): m.cursed_evolve = true
		if o.kind == "evolve" and o.get("card_uid") == NOIR and o.get("source_uid") == CANDY:
			m.cursed_evolve = candy_routes.get(target, {}).get("allowed", false)
		if o.kind == "evolve" and o.get("card_uid") == CLOPS and candy_routes.has(target):
			m.cursed_evolve = route(p, attackers, int(target), 50).get("allowed", false)
		if include_spread and o.kind == "retreat" and target in attackers:
			var approved := false
			for r: Dictionary in actual.values():
				if r.get("allowed", false): approved = true
			if not approved:
				var prepared: Dictionary = p.duplicate(true); prepared.own_active = target; prepared.attacker = target; prepared.attack_ready = true
				for s: int in ghosts:
					if best_route(prepared, s, int(GHOSTS[ghosts[s].local_card_uid])).get("allowed", false): m.cursed_prepare = true
		if include_spread:
			var values := {}
			for k: String in m: values[k.replace("cursed_", "cursed2_")] = m[k]
			options[str(o.index)] = values
	if include_spread: result.scope = "public-funded-reply-and-phantom-spread-v2"
	return result
