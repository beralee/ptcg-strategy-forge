"""Public, current-window comparison of conditional resource plans.

The mature rule ordering is an explicit candidate, never a hidden teacher.
Only Base's already admitted single-choice frontier is compared. Ordinal
estimates are not win probabilities or engine proofs.
"""
from __future__ import annotations
import copy
import json
from functools import lru_cache
from pathlib import Path

from . import public_attack_access as access

PROFILE = 'resource-continuity-v1'
MAX_STATES = 256
MAX_DEPTH = 3


@lru_cache(maxsize=1)
def metadata():
    return json.loads((Path(__file__).resolve().parents[3] /
        'contracts/ptcgdap/public_damage_capability_registry_v1.json').read_bytes())['cards']


def _printed(entity, cards):
    return max((a['pressure'] for a in cards.get(entity['uid'], {}).get('attacks', [])), default=0)


def _line(entity, cards):
    """Reviewed evolution reachability, without inventing cards in hand."""
    current = cards.get(entity['uid'], {})
    names = {current.get('name')}
    result = _printed(entity, cards)
    for _ in range(2):
        for c in cards.values():
            if c.get('from') and c['from'] in names:
                names.add(c['name'])
                result = max(result, max((a['pressure'] for a in c['attacks']), default=0))
    return result


def _actions(state, cards):
    result = []
    for h in sorted(state['hand'], key=lambda x: x['serial']):
        c = cards.get(h['local_card_uid'], {})
        for identity, entity in sorted(state['board'].items()):
            if state['attach'] and c.get('energy_model') and (identity == state['active'] or _line(entity, cards) >= 150):
                result.append(dict(kind='attach_energy', card_serial=h['serial'], card_uid=h['local_card_uid'], target=identity))
            if (not entity['played'] and not entity['evolved'] and c.get('from')
                    and c['from'] == cards[entity['uid']]['name']
                    and c['stage'] == cards[entity['uid']]['stage'] + 1):
                result.append(dict(kind='evolve', card_serial=h['serial'], card_uid=h['local_card_uid'], target=identity))
    active = state['board'][state['active']]
    if state['retreat'] and not any(s in active['conditions'] for s in ('asleep', 'paralyzed')):
        for identity, e in sorted(state['board'].items()):
            if identity != state['active'] and _printed(e, cards) >= 90:
                result.append(dict(kind='retreat', target=identity))
    return result


def _bind(option, action):
    if option['kind'] != action['kind'] or option.get('target_entity_serial') != action['target']: return False
    return action['kind'] == 'retreat' or (option.get('card_serial') == action['card_serial'] and option.get('card_uid') == action['card_uid'])


def _asset_value(state, cards):
    # Residual flexibility beyond the explicit next-attack horizon. The same
    # physical card contributes once, with diminishing duplicate value.
    counts = {}; value = 0
    for h in state['hand']:
        model = cards.get(h['local_card_uid'], {}).get('energy_model')
        if not model: continue
        counts[h['local_card_uid']] = counts.get(h['local_card_uid'], 0) + 1
        n = counts[h['local_card_uid']]
        value += (100 if model == 'neo_upper' else 28 if model == 'luminous' else 18) // n
    for e in state['board'].values():
        for energy in e['energies']:
            model = cards.get(energy['local_card_uid'], {}).get('energy_model')
            value += 50 if model == 'neo_upper' else 20 if model == 'luminous' else 14
    return value


def _successor_plan(state, cards, frame=None, weight=500):
    """Joint next-attacker and residual portfolio, using each physical card once.

    Reserving an evolution/energy for this conditional continuation removes it
    from the residual hand. Equal portfolios prefer preserving next turn's
    attachment budget. No reservation survives the current decision window.
    """
    residual = _asset_value(state, cards)
    engine = sum(bool(cards[e['uid']].get('information_abilities')) for e in state['board'].values())
    best = dict(value=0, entity_serial=None, debt=32, residual_value=residual, engine_count=engine,
                future_attachment=False, reserved_card_serials=[], joint_value=residual+28*engine)
    hand = sorted(state['hand'], key=lambda h: h['serial'])
    for serial, entity in sorted(state['board'].items()):
        if serial == state['active'] or _line(entity, cards) < 150: continue
        variants = [(copy.deepcopy(entity), [])]
        for h in hand:
            c = cards.get(h['local_card_uid'], {})
            if c.get('from') and c['from'] == cards[entity['uid']]['name'] and c['stage'] == cards[entity['uid']]['stage'] + 1:
                e = copy.deepcopy(entity); e['uid'] = h['local_card_uid']
                e['costs'] = {a['index']: [a['cost']] for a in c['attacks']}
                if access._resupply(e, cards): variants.append((e, [h['serial']]))
        for base, evolved in variants:
            supplies = [(base, evolved, False)]
            for h in hand:
                if not cards.get(h['local_card_uid'], {}).get('energy_model') or h['serial'] in evolved: continue
                if (frame and frame['public_state']['self']['turn']['manual_attachment_available']
                        and not any(o['kind']=='attach_energy' and o.get('card_serial')==h['serial']
                            and o.get('target_entity_serial')==serial for o in frame['options'])):
                    continue
                e = copy.deepcopy(base)
                e['energies'].append(dict(serial=h['serial'],local_card_uid=h['local_card_uid'],units=1,types=['C']))
                if access._resupply(e, cards): supplies.append((e, evolved + [h['serial']], True))
            for e, reserved, attached in supplies:
                shadow = dict(hand=[h for h in hand if h['serial'] not in reserved],
                              board=dict(state['board']))
                shadow['board'][serial] = e
                residual = _asset_value(shadow, cards)
                engine = sum(bool(cards[x['uid']].get('information_abilities')) for x in shadow['board'].values())
                for a in cards[e['uid']]['attacks']:
                    if a['pressure'] < 150 or a['index'] not in e['costs']: continue
                    missing = access.energy_debt(e['costs'][a['index']], e['energies'])
                    quality = a['pressure'] * (100 if missing == 0 else 35 if missing == 1 else 10) // 100
                    joint = quality * weight // 1000 + residual + 28*engine
                    if (joint, -int(attached)) > (best['joint_value'], -int(best['future_attachment'])):
                        best = dict(value=quality, entity_serial=serial, debt=missing,
                            residual_value=residual, engine_count=engine, future_attachment=attached,
                            reserved_card_serials=sorted(reserved), joint_value=joint)
    return best


def _successor(state, cards, frame=None):
    """Best ONE replacement, at most one next-turn attachment/evolution.

    The current attacker uses only energy already on it. Never sum separately
    optimized successors which might have reused a single hand card/budget.
    """
    best = 0; identity = None; debt = 32
    for serial, entity in sorted(state['board'].items()):
        if serial == state['active'] or _line(entity, cards) < 150: continue
        variants = [copy.deepcopy(entity)]
        for h in state['hand']:
            c = cards.get(h['local_card_uid'], {})
            if c.get('from') and c['from'] == cards[entity['uid']]['name'] and c['stage'] == cards[entity['uid']]['stage'] + 1:
                e = copy.deepcopy(entity); e['uid'] = h['local_card_uid']
                e['costs'] = {a['index']: [a['cost']] for a in c['attacks']}
                if access._resupply(e, cards): variants.append(e)
        for base in variants:
            supplies = [base]
            for h in state['hand']:
                if not cards.get(h['local_card_uid'], {}).get('energy_model'): continue
                if (frame and frame['public_state']['self']['turn']['manual_attachment_available']
                        and not any(o['kind']=='attach_energy' and o.get('card_serial')==h['serial']
                            and o.get('target_entity_serial')==serial for o in frame['options'])):
                    continue  # An observed restriction is not wished away next turn.
                e = copy.deepcopy(base)
                e['energies'].append(dict(serial=h['serial'],local_card_uid=h['local_card_uid'],units=1,types=['C']))
                if access._resupply(e, cards): supplies.append(e)
            for e in supplies:
                for a in cards[e['uid']]['attacks']:
                    if a['pressure'] < 150 or a['index'] not in e['costs']: continue
                    missing = access.energy_debt(e['costs'][a['index']], e['energies'])
                    # Missing cards are discounted prospects, never ready proofs.
                    quality = a['pressure'] * (100 if missing == 0 else 35 if missing == 1 else 10) // 100
                    if quality > best: best, identity, debt = quality, serial, missing
    return best, identity, debt


def _damage(uid, attack_index, target_uid, meta):
    c = meta.get(uid, {}); target = meta.get(target_uid, {})
    a = next((a for a in c.get('attacks', []) if a['attack_index'] == attack_index), {})
    damage = a.get('active_damage')
    if type(damage) is not int: return None
    if c.get('energy_type') and c['energy_type'] == target.get('weakness_energy'):
        damage *= target.get('weakness_multiplier', 1)
    if c.get('energy_type') and c['energy_type'] == target.get('resistance_energy'):
        damage = max(0, damage - target.get('resistance_reduction', 0))
    return damage


def _attack(state, initial, frame, cards, meta, *, wait=False, attack_index=None):
    result = dict(damage=0,prizes=0,counters=0,pressure=0,finishes=False,conditional=False,defender_ko=False,attack_index=None)
    if wait: return result
    d = frame['public_state']['decision']
    if d['self']['is_first_turn'] and d['current_player_index'] == d['first_player_index']: return result
    opponent = frame['public_state']['opponent']
    if not opponent['active']: return result
    e = state['board'][state['active']]; target = opponent['active'][0]
    if any(s in e['conditions'] for s in ('asleep','paralyzed')): return result
    for a in cards[e['uid']]['attacks']:
        if attack_index is not None and a['index'] != attack_index: continue
        if a['index'] not in e['costs'] or access.energy_debt(e['costs'][a['index']],e['energies']): continue
        legal = next((o for o in frame['options'] if o['kind'] == 'attack' and o.get('source_uid') == e['uid']
                      and o.get('attack_index') == a['index'] and state['active'] == initial['active']), None)
        unchanged = state['active'] == initial['active'] and e['uid'] == initial['board'][initial['active']]['uid']
        if unchanged and access._pressure(initial['board'][initial['active']],cards) > 0 and legal is None: continue
        damage = legal.get('projected_damage') if legal else _damage(e['uid'],a['index'],target['local_card_uid'],meta)
        if type(damage) is not int: continue
        # Catalog-only forecasts cannot prove future legality/protection.
        conditional = legal is None
        ko = damage >= target['remaining_hp'] and damage > 0
        prizes = target['prize_value'] if ko else 0
        # Reviewed Phantom Dive places counters; fixed-split attack damage is
        # a different mechanic and is not treated as distributable counters.
        counters = 60 if e['uid'] == 'CSV8C_159' and a['index'] == 1 else 0
        budget = counters; bench_prizes = 0
        for b in sorted(opponent['bench'],key=lambda b:(-b['prize_value'],b['remaining_hp'],b['entity_serial'])):
            if 0 < b['remaining_hp'] <= budget:
                budget -= ((b['remaining_hp']+9)//10)*10; bench_prizes += b['prize_value']
        # Actual host front KO can certify a finish; unreviewed bench immunity
        # prevents treating catalog split estimates as terminal authority.
        finishes = not conditional and ko and prizes >= frame['public_state']['self']['prizes_remaining']
        candidate = dict(damage=min(damage,target['remaining_hp']),prizes=prizes+bench_prizes,counters=counters,
                         pressure=a['pressure'],finishes=finishes,conditional=conditional,defender_ko=ko,attack_index=a['index'])
        if (candidate['finishes'],candidate['prizes'],candidate['damage']+counters) > (result['finishes'],result['prizes'],result['damage']+result['counters']): result=candidate
    return result


def _response(state, frame, attack, meta):
    """Public one-response stress estimate; no access to the opponent's hand."""
    e = state['board'][state['active']]; public = frame['public_state']; opp = public['opponent']
    entities = {r['entity_serial']:r for r in public['decision']['entities']}
    exposure = 0; damage = 0; unknown = False
    for slot in opp['active'] + opp['bench']:
        if attack['defender_ko'] and slot in opp['active']: continue
        source = entities.get(slot['entity_serial'], {})
        for a in source.get('attacks', []):
            amount = _damage(slot['local_card_uid'],a['attack_index'],e['uid'],meta)
            if amount is None: unknown=True; continue
            missing = a['energy_debt']
            if missing > 1: continue
            weight = 1000 if missing == 0 else 450
            # Bench attackers still need a pivot. This is a scenario weight,
            # explicitly NOT a calibrated hidden-hand probability.
            if slot in opp['bench'] and not attack['defender_ko']: weight = weight * 3 // 4
            damage = max(damage,amount*weight//1000)
            if amount >= e['hp']: exposure=max(exposure,weight)
    return dict(active_ko_exposure=exposure,damage=damage,unknown=unknown)


def _slot_continuity(state, attack, response, successor, opponent_prizes, *, joint_budget=False):
    """Ordinal continuation credit after access cost and the public response.

    A nonterminal KO releases the active slot for free. A terminal KO leaves
    no successor turn. Otherwise a stranded front competes for future manual
    attachments and/or the next retreat budget. Scenario weights are the
    existing stress estimates, never calibrated hidden-hand probabilities.
    """
    active = state['board'][state['active']]
    exposure = response['active_ko_exposure']
    units = sum(e['units'] for e in active['energies'])
    debt = max(0, active['retreat'] - units)
    future = int(successor.get('future_attachment',False)) if joint_budget else 0
    delay = 0 if attack['pressure'] > 0 else max(debt + future, int(not state['retreat']),
        int(any(c in active['conditions'] for c in ('asleep', 'paralyzed'))))
    release = exposure if active['prize'] < opponent_prizes else 0
    weight = release + (1000-exposure)//(1+delay)
    base = successor['value']*(500+exposure)//1000
    result = dict(escape_delay=delay, retreat_energy_debt=debt,
        forced_promotion_weight_milli=release, continuity_weight_milli=weight,
        unadjusted_value=base, value=base*weight//1000)
    if joint_budget: result['successor_attachment_steps'] = future
    return result


def _evaluate(state, initial, frame, cards, meta, *, wait=False, attack_index=None, joint_resources=False, active_slot=False, joint_mobility=False):
    if not joint_resources:
        return _evaluate_legacy(state,initial,frame,cards,meta,wait=wait,attack_index=attack_index)
    attack = _attack(state,initial,frame,cards,meta,wait=wait,attack_index=attack_index)
    response = _response(state,frame,attack,meta)
    active = state['board'][state['active']]
    current = access._pressure(active,cards)
    exposure = response['active_ko_exposure']
    successor = _successor_plan(state,cards,frame,500+exposure)
    residual = successor['residual_value']
    lost_prize = active['prize'] * exposure
    own_prizes = frame['public_state']['self']['prizes_remaining']
    their_prizes = frame['public_state']['opponent']['prizes_remaining']
    engine = successor['engine_count']
    slot = _slot_continuity(state,attack,response,successor,their_prizes,joint_budget=joint_mobility) if active_slot else None
    continuity = slot['value'] if slot is not None else successor['value']*(500+exposure)//1000
    # Unified ordinal critic. The attack is a component, not a lexicographic
    # gate. Replacement is valued after a public response, using one budget.
    score = (min(own_prizes,attack['prizes'])*220 + (attack['damage']+attack['counters'])//3
             + current*(1000-exposure)//2000 + continuity
             + residual + 28*engine - lost_prize*130//1000 - state['retreat_count']*8)
    if exposure and active['prize'] >= their_prizes:
        score -= exposure*500//1000
    if attack['finishes']: score += 100000
    opportunity = max(0,_asset_value(initial,cards)-residual)
    result = dict(value=score,attack=attack,response=response,successor_value=successor['value'],
        successor_entity_serial=successor['entity_serial'],successor_debt=successor['debt'],
        successor_commitment=successor,opportunity_cost=opportunity,
        resource_cost=state['spent'],steps=copy.deepcopy(state['steps']))
    if slot is not None: result['active_slot'] = slot
    return result


def _evaluate_legacy(state, initial, frame, cards, meta, *, wait=False, attack_index=None):
    attack = _attack(state,initial,frame,cards,meta,wait=wait,attack_index=attack_index)
    response = _response(state,frame,attack,meta)
    successor, identity, debt = _successor(state,cards,frame)
    active = state['board'][state['active']]
    current = access._pressure(active,cards)
    residual = _asset_value(state,cards)
    exposure = response['active_ko_exposure']
    lost_prize = active['prize'] * exposure
    own_prizes = frame['public_state']['self']['prizes_remaining']
    their_prizes = frame['public_state']['opponent']['prizes_remaining']
    engine = sum(1 for e in state['board'].values() if cards[e['uid']].get('information_abilities'))
    # Unified ordinal critic. The attack is a component, not a lexicographic
    # gate. Replacement is valued after a public response, using one budget.
    score = (min(own_prizes,attack['prizes'])*220 + (attack['damage']+attack['counters'])//3
             + current*(1000-exposure)//2000 + successor*(500+exposure)//1000
             + residual + 28*engine - lost_prize*130//1000 - state['retreat_count']*8)
    if exposure and active['prize'] >= their_prizes:
        score -= exposure*500//1000
    if attack['finishes']: score += 100000
    opportunity = max(0,_asset_value(initial,cards)-residual)
    return dict(value=score,attack=attack,response=response,successor_value=successor,
        successor_entity_serial=identity,successor_debt=debt,opportunity_cost=opportunity,
        resource_cost=state['spent'],steps=copy.deepcopy(state['steps']))



def _information(frame, ordered, state, cards):
    if frame['public_state']['self']['deck_count'] < 2: return []
    found=[]
    for i in ordered:
        o=frame['options'][i]
        if o['kind']=='use_ability':
            e=state['board'].get(o.get('source_entity_serial'),{})
            c=cards.get(e.get('uid'),{})
            if e.get('uid')==o.get('source_uid') and o.get('ability_index') in c.get('information_abilities',[]):
                found.append(dict(index=i,reason='information_checkpoint'))
        elif o['kind']=='evolve':
            e=state['board'].get(o.get('target_entity_serial'),{})
            c=cards.get(o.get('card_uid'),{})
            if (e and c.get('information_abilities') and not e['played'] and not e['evolved']
                    and c.get('from')==cards[e['uid']]['name'] and c['stage']==cards[e['uid']]['stage']+1
                    and any(h['serial']==o.get('card_serial') and h['local_card_uid']==o.get('card_uid') for h in state['hand'])):
                found.append(dict(index=i,reason='information_predecessor'))
    def information_order(row):
        o=frame['options'][row['index']]
        identity=o.get('source_entity_serial') if o['kind']=='use_ability' else o.get('target_entity_serial')
        e=state['board'][identity]
        return (0 if o['kind']=='use_ability' else 1,-len(e['energies']),identity,
                o.get('card_serial') or 0,o.get('ability_index') or 0)
    found.sort(key=information_order)
    return found


def _voluntary_switch(frame, ordered, result):
    """Replan the actual switch window; knockout promotion keeps its own floor."""
    if (frame['select_semantics']['select_context_raw'] != 3
            or frame['public_state']['decision']['current_player_index'] != frame['seat']):
        return dict(result,reason='unsupported_planning_window')
    cards=access.catalog(); initial=access._state(frame,cards); meta=metadata()
    if (initial['active'] not in initial['board'] or
            len(initial['board']) != len(frame['public_state']['self']['active']+frame['public_state']['self']['bench'])):
        return dict(result,reason='unknown_board_capability')
    baseline_control=frame['options'][ordered[0]].get('target_uid')=='CSV9.5C_004'
    choices=[]
    for index in ordered:
        o=frame['options'][index]; identity=o.get('target_entity_serial'); e=initial['board'].get(identity)
        if o['kind']!='send_out' or not e or e['uid']!=o.get('target_uid') or identity==initial['active']: continue
        state=copy.deepcopy(initial);state['active']=identity
        attack=_attack(state,initial,frame,cards,meta)
        finish=attack['defender_ko'] and frame['public_state']['opponent']['active'][0]['prize_value']>=frame['public_state']['self']['prizes_remaining']
        if baseline_control and not finish: continue
        if not finish and not (attack['defender_ko'] or attack['pressure']>=150): continue
        choices.append(dict(index=index,entity_serial=identity,attack=attack,finish_forecast=finish))
    if not choices:return dict(result,reason='voluntary_switch_baseline')
    chosen=max(choices,key=lambda r:(r['finish_forecast'],r['attack']['prizes'],r['attack']['damage']+r['attack']['counters'],r['attack']['pressure'],-r['entity_serial']))
    return dict(result,proposed_index=chosen['index'],reason='voluntary_attack_switch',switch_candidates=choices)


def _funded_promotion(state, identity, cards):
    """A known Dragapult attack after at most one evolution and attachment."""
    state = copy.deepcopy(state)
    state['active'] = identity
    if state['board'][identity]['uid'] == 'CSV8C_159' and access._pressure(state['board'][identity], cards) >= 150:
        return dict(steps=[], pressure=access._pressure(state['board'][identity], cards))
    frontier = [state]
    if state['board'][identity]['uid'] == 'CSV8C_157':
        # The reviewed Rare Candy line spends both known cards on a mature
        # Dreepy. It never assumes that a search or draw finds either card.
        candy = next((h for h in state['hand'] if h['local_card_uid'] == 'CSVH1C_045'), None)
        pult = next((h for h in state['hand'] if h['local_card_uid'] == 'CSV8C_159'), None)
        if candy and pult:
            child = copy.deepcopy(state)
            entity = child['board'][identity]
            observed = copy.deepcopy(entity['energies'])
            if (not entity['played'] and not entity['evolved'] and access._resupply(entity, cards)
                    and entity['energies'] == observed):
                old, new = cards[entity['uid']], cards['CSV8C_159']
                entity['hp'] += new['hp'] - old['hp']
                entity['uid'] = 'CSV8C_159'
                entity['evolved'] = True
                entity['conditions'] = []
                entity['retreat'] = max(0, entity['retreat'] + new['retreat'] - old['retreat'])
                entity['costs'] = {a['index']: [a['cost']] for a in new['attacks']}
                if access._resupply(entity, cards):
                    child['hand'] = [h for h in child['hand'] if h['serial'] not in (candy['serial'], pult['serial'])]
                    child['steps'].append(dict(kind='rare_candy', candy_serial=candy['serial'],
                                               card_serial=pult['serial'], target=identity))
                    if access._pressure(entity, cards) >= 150:
                        return dict(steps=child['steps'], pressure=access._pressure(entity, cards))
                    frontier.append(child)
    for depth in range(2):
        next_frontier = []
        for current in frontier:
            for action in access._actions(current, cards):
                if action['target'] != identity or action['kind'] not in ('evolve', 'attach_energy'):
                    continue
                child = access._apply(current, action, cards)
                if child is None:
                    continue
                attacker = child['board'][identity]
                if attacker['uid'] == 'CSV8C_159' and access._pressure(attacker, cards) >= 150:
                    return dict(steps=child['steps'], pressure=access._pressure(attacker, cards))
                if depth == 0:
                    next_frontier.append(child)
        frontier = next_frontier
    return None


def _knockout_promotion(frame, ordered, result):
    """Choose a paid attacker; otherwise keep the zero-cost Budew retreat."""
    if frame['select_semantics']['select_context_raw'] != 4:
        return dict(result, reason='unsupported_planning_window')
    cards = access.catalog()
    state = access._state(frame, cards)
    decision = frame['public_state']['decision']
    own_turn = decision['current_player_index'] == frame['seat']
    if not own_turn:
        # The replacement is selected on the opponent's turn. The next own
        # action window restores one manual attachment and evolution timing.
        state['attach'] = True
        for entity in state['board'].values():
            entity['played'] = entity['evolved'] = False
    attack_blocked = (own_turn and decision['self']['is_first_turn']
                      and decision['current_player_index'] == decision['first_player_index'])
    direct = []
    buffer = []
    for index in ordered:
        option = frame['options'][index]
        identity = option.get('target_entity_serial')
        entity = state['board'].get(identity)
        if option['kind'] != 'send_out' or not entity or entity['uid'] != option.get('target_uid'):
            continue
        if entity['uid'] == 'CSV9.5C_004' and entity['retreat'] == 0:
            buffer.append(index)
        if not attack_blocked and entity['uid'] in ('CSV8C_157', 'CSV8C_158', 'CSV8C_159'):
            route = _funded_promotion(state, identity, cards)
            if route:
                direct.append((len(route['steps']), -route['pressure'], identity, index, route))
    if direct:
        _, _, _, index, route = min(direct)
        return dict(result, proposed_index=index, reason='funded_dragapult_promotion',
                    promotion_route=route, assumptions=['future_window_legality', 'no_unobserved_opponent_disruption'])
    if buffer:
        return dict(result, proposed_index=buffer[0], reason='free_budew_promotion')
    return dict(result, reason='promotion_fallback')


def _ready_budew_handoff(frame, ordered, result):
    decision = frame['public_state']['decision']
    if (frame['select_semantics']['select_context_raw'] != 0
            or decision['current_player_index'] != frame['seat']
            or (decision['self']['is_first_turn'] and decision['first_player_index'] == frame['seat'])):
        return None
    cards = access.catalog()
    state = access._state(frame, cards)
    active = state['board'].get(state['active'])
    if (not active or active['uid'] != 'CSV9.5C_004' or active['retreat'] != 0
            or not state['retreat'] or any(s in active['conditions'] for s in ('asleep', 'paralyzed'))):
        return None
    choices = []
    for index in ordered:
        option = frame['options'][index]
        identity = option.get('target_entity_serial')
        entity = state['board'].get(identity)
        if (option['kind'] == 'retreat' and entity and entity['uid'] == 'CSV8C_159'
                and option.get('target_uid') == entity['uid']):
            pressure = access._pressure(entity, cards)
            if pressure >= 150:
                choices.append((-pressure, identity, index))
    if not choices:
        return None
    index = min(choices)[2]
    return dict(result, proposed_index=index, reason='ready_dragapult_budew_handoff')


def _protect_free_attack_access(initial, option, route, wait):
    """Keep the admitted floor when cutoff successor credit favors waiting.

    Only a single free retreat with a productive attack and no worse public
    prize exposure qualifies. This is a model-coverage guard, not a win proof;
    the next window must still reobserve and establish attack legality.
    """
    target = option.get('target_entity_serial')
    steps = route['steps']
    if (option['kind'] != 'retreat' or target not in initial['board']
            or len(steps) != 1 or steps[0]['kind'] != 'retreat'
            or steps[0]['target'] != target or steps[0]['discarded_energy_serials']
            or route['attack']['pressure'] <= 0
            or route['response']['unknown'] or wait['response']['unknown']):
        return False
    return (initial['board'][target]['prize'] * route['response']['active_ko_exposure']
            <= initial['board'][initial['active']]['prize'] * wait['response']['active_ko_exposure'])


def compare_plans(frame, ordered, *, validated=False, profile=PROFILE):
    if profile == 'card-goals-v1':
        from .public_card_goals import compare_card_goals
        return compare_card_goals(frame, ordered, validated=validated)
    from .competitive_policy_v2 import _frame_error
    result=dict(accepted=False,proposed_index=None,reason='unqualified_public_position',plans=[],
        current_window_only=True,stale_plan_has_authority=False,profile=profile,
        value_kind='ordinal_public_response_critic',expected_value_proven=False)
    if profile not in ('resource-continuity-v1','resource-continuity-v2','resource-continuity-v3','resource-continuity-v4','resource-continuity-v5'): return dict(result,reason='unsupported_plan_profile')
    joint_profile = profile in ('resource-continuity-v2','resource-continuity-v3','resource-continuity-v4','resource-continuity-v5')
    if type(frame) is not dict or (not validated and _frame_error(frame)) or not frame.get('public_state',{}).get('decision'): return result
    if (type(ordered) is not list or not ordered or any(type(i) is not int or not 0<=i<len(frame['options']) for i in ordered)
            or len(set(ordered)) != len(ordered)): return dict(result,reason='invalid_current_frontier')
    baseline=ordered[0]
    result.update(accepted=True,proposed_index=baseline,baseline_index=baseline,reason='baseline')
    if frame['select_semantics']['min_count']!=1 or frame['select_semantics']['max_count']!=1:
        return dict(result,reason='unsupported_planning_window')
    if frame['prompt_kind']!='main':
        if profile == 'resource-continuity-v5' and frame['prompt_kind'] == 'send_out' and frame['select_semantics']['select_context_raw'] == 4:
            return _knockout_promotion(frame,ordered,result)
        if joint_profile and frame['prompt_kind'] in ('send_out','self_switch'): return _voluntary_switch(frame,ordered,result)
        return dict(result,reason='unsupported_planning_window')
    if profile == 'resource-continuity-v5':
        handoff = _ready_budew_handoff(frame,ordered,result)
        if handoff:
            return handoff
    cards=access.catalog(); meta=metadata(); initial=access._state(frame,cards)
    if initial['active'] not in initial['board']: return dict(result,reason='unknown_active_capability')
    if len(initial['board'])!=len(frame['public_state']['self']['active']+frame['public_state']['self']['bench']):
        return dict(result,reason='unknown_board_capability')
    baseline_option=frame['options'][baseline]
    if joint_profile and baseline_option['kind']=='evolve':
        target=baseline_option.get('target_entity_serial'); entity=initial['board'].get(target)
        twins=[i for i in ordered if frame['options'][i]['kind']=='evolve'
            and frame['options'][i].get('card_serial')==baseline_option.get('card_serial')
            and frame['options'][i].get('card_uid')==baseline_option.get('card_uid')
            and initial['board'].get(frame['options'][i].get('target_entity_serial'))==entity
            and (frame['options'][i].get('target_entity_serial')==initial['active'])==(target==initial['active'])]
        if entity and twins:
            baseline=min(twins,key=lambda i:frame['options'][i]['target_entity_serial'])
            baseline_option=frame['options'][baseline]
            result.update(baseline_index=baseline,proposed_index=baseline)
    # Never replace a mature, unmodeled trainer/ability/bench route with a
    # partial resource model. These remain explicit information checkpoints.
    known=('attach_energy','evolve','retreat','attack','end_turn')
    if baseline_option['kind'] not in known: return dict(result,reason='baseline_unmodeled_checkpoint')
    current=_attack(initial,initial,frame,cards,meta)
    if current['finishes']:
        finish=next((i for i in ordered if frame['options'][i]['kind']=='attack'
                     and frame['options'][i].get('attack_index')==current['attack_index']),None)
        if finish is not None: return dict(result,proposed_index=finish,reason='current_proven_finish')
    info=_information(frame,ordered,initial,cards)
    if info and not current['finishes']:
        chosen=info[0]
        return dict(result,proposed_index=chosen['index'],reason=chosen['reason'],
            information_candidates=info,requires_reobservation=True)
    if joint_profile and ((baseline_option['kind']=='retreat' and baseline_option.get('target_uid')=='CSV9.5C_004')
            or (baseline_option['kind']=='attack' and baseline_option.get('source_uid')=='CSV9.5C_004')):
        return dict(result,reason='unmodeled_control_route_protected')
    if (baseline_option['kind']=='retreat' and frame.get('_derived_damage',{}).get('options',{}).get(str(baseline),{}).get('cursed2_prepare') is True):
        # The resource-only critic cannot see the self-KO suffix. Keep this
        # fresh same-tier proposal until the next legal window is observed.
        return dict(result,reason='public_self_ko_route_checkpoint',requires_reobservation=True)
    joint_resources = joint_profile
    def evaluate(*args, **kwargs):
        return _evaluate(*args, **kwargs, joint_resources=joint_resources,
            active_slot=profile in ('resource-continuity-v3','resource-continuity-v4'),joint_mobility=profile=='resource-continuity-v4')
    actions=_actions(initial,cards); best={}; expanded=0
    for index in ordered:
        option=frame['options'][index]
        if option['kind'] not in known: continue
        if option['kind'] in ('attack','end_turn'):
            row=evaluate(initial,initial,frame,cards,meta,wait=option['kind']=='end_turn',attack_index=option.get('attack_index'))
            best[index]=dict(row,first_index=index)
            continue
        for action in actions:
            if not _bind(option,action): continue
            child=access._apply(initial,action,cards)
            if child is None: continue
            queue=[child]
            while queue:
                state=queue.pop(0);expanded+=1
                row=evaluate(state,initial,frame,cards,meta)
                row.update(first_index=index)
                if index not in best or row['value']>best[index]['value']: best[index]=row
                if expanded>=MAX_STATES: break
                if len(state['steps'])>=MAX_DEPTH: continue
                next_rows=[]
                for follow in _actions(state,cards):
                    # Never search through information unlocked by evolution.
                    if any(cards[state['board'][s['target']]['uid']].get('information_abilities') for s in state['steps'] if s['kind']=='evolve'): break
                    nxt=access._apply(state,follow,cards)
                    if nxt is not None:
                        value=evaluate(nxt,initial,frame,cards,meta)['value']
                        next_rows.append((value,nxt))
                # Deterministic beam, independent of the incoming option order.
                next_rows.sort(key=lambda x:-x[0])
                queue.extend(nxt for _,nxt in next_rows[:4])
            if expanded>=MAX_STATES: break
        if expanded>=MAX_STATES: break
    result.update(plans=[best[i] for i in sorted(best)],expanded=expanded)
    if expanded>=MAX_STATES: return dict(result,reason='planning_budget_exceeded')
    if baseline not in best or not best: return dict(result,reason='baseline_not_modeled')
    chosen=max((i for i in ordered if i in best),key=lambda i:(best[i]['value'],-int(best[i]['successor_commitment']['future_attachment']) if joint_resources else 0))
    advantage=best[chosen]['value']-best[baseline]['value']
    if (joint_resources and chosen != baseline and frame['options'][chosen]['kind']=='end_turn'
            and _protect_free_attack_access(initial,baseline_option,best[baseline],best[chosen])):
        return dict(result,reason='attack_access_floor_protected',advantage=advantage,requires_reobservation=True)
    if joint_resources and chosen != baseline and baseline_option['kind']=='evolve':
        current_plan, alternative = best[baseline], best[chosen]
        attack_key=lambda p:(p['attack']['prizes'],p['attack']['damage']+p['attack']['counters'])
        if (attack_key(alternative)<=attack_key(current_plan)
                and alternative['successor_value']<=current_plan['successor_value']
                and alternative['response']['active_ko_exposure']>=current_plan['response']['active_ko_exposure']):
            return dict(result,reason='preparation_value_unproven',advantage=advantage)
    # A cutoff estimate cannot prove that skipping productive bench preparation
    # is superior. The missing information/response model keeps that decision
    # with the qualified rule floor, while active payment can be deferred.
    if (frame['options'][chosen]['kind']=='end_turn' and
            (baseline_option['kind']=='evolve' or (baseline_option['kind']=='attach_energy'
             and baseline_option.get('target_entity_serial')!=initial['active']))):
        return dict(result,reason='preparation_floor_protected',advantage=advantage)
    # Margin protects the mature ordering against numerical dust and ties.
    margin=60 if best[chosen]['attack']['conditional'] else 20
    if advantage>=margin: result.update(proposed_index=chosen,reason='comparative_plan_advantage')
    result['required_margin']=margin
    result['advantage']=advantage
    return result
