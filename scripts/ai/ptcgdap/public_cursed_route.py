"""Public, bounded Dragapult + Cursed Blast route calculator (research v1).

The response is a deliberately pessimistic public-board stress test: every
surviving printed attacker may be fully funded and gust any friendly body.
It is NOT a hidden-hand oracle or a guarantee against newly played/evolved
Pokemon. No 60-counter follow-up credit is needed to approve a blast in v1.
Unknown opposing attacks are treated as lethal; unknown own attack modifiers
decline the route. Every result is rebuilt for the immutable current window.
"""
from __future__ import annotations
import copy

PULT='CSV8C_159'
CLOPS='CSV8C_082'
NOIR='CSV8C_083'
DUSKULL='CSV8C_081'
CANDY='CSVH1C_045'
GHOSTS={CLOPS:50,NOIR:130}
PREFIX='damage.option.cursed_'


def uses_cursed_route(document):
    return any(str(q.get('fact','')).startswith((PREFIX,'damage.option.cursed2_'))
               for r in document.get('rules',[]) for q in r.get('when',[])+r.get('score_terms',[]))


def uses_cursed_spread(document):
    return any(str(q.get('fact','')).startswith('damage.option.cursed2_')
               for r in document.get('rules',[]) for q in r.get('when',[])+r.get('score_terms',[]))


def _attack_outcomes(p,board,active):
    projected=copy.deepcopy(board)
    defender=next(b for b in projected if b['id']==active)
    if not defender.get('immune'):defender['hp']-=p['attack_damage']
    budget=p.get('attack_counters',0)
    if any(b.get('counter_guard') and b['hp']>0 for b in board):budget=0
    if not budget:return [projected]
    # Keep every prize-optimal allocation. Existing counter selection owns the
    # real six fresh windows; no favorable equal-prize survivor is assumed.
    targets=sorted([b for b in projected if b['id']!=active and b['hp']>0],key=lambda b:b['id'])
    if not targets:return [projected]
    best=-1;rows=[]
    for mask in range(1<<len(targets)):
        chosen=[b for i,b in enumerate(targets) if mask&(1<<i)]
        if sum((b['hp']+9)//10 for b in chosen)>budget:continue
        gain=sum(b['prize'] for b in chosen)
        if gain<best:continue
        if gain>best:best=gain;rows=[]
        ids={b['id'] for b in chosen};result=copy.deepcopy(projected)
        for b in result:
            if b['id'] in ids:b['hp']=0
        rows.append(result)
    return rows


def _knockout_prizes(board, damage, pool):
    """Upper bound: the counter pool may be split freely, ignoring protections."""
    mandatory=0; debts=[]
    for b in board:
        hp=b['hp']-damage.get(b['id'],0)
        if hp<=0: mandatory+=b['prize']
        else: debts.append((hp,b['prize']))
    best=mandatory
    for mask in range(1<<len(debts)):
        cost=sum(d[0] for i,d in enumerate(debts) if mask&(1<<i))
        if cost<=pool:
            best=max(best,mandatory+sum(d[1] for i,d in enumerate(debts) if mask&(1<<i)))
    return best


def response_prizes(own, enemy):
    if not enemy: return 0
    frost=sum(20 for e in own+enemy if e.get('frost'))
    # Two checkups, including the end of the opponent's next turn. Stacking
    # every visible counter ability is an upper bound, even if unfunded.
    passive={o['id']:(frost if o.get('ability') else 0)+o.get('status_tick',0) for o in own}
    pool=sum(e.get('counters',0) for e in enemy)
    best=_knockout_prizes(own,passive,pool)
    for attacker in enemy:
        for target in own:  # assume gust access, including bench liabilities
            damage=dict(passive)
            damage[target['id']]+=attacker['attack']*target.get('weakness',{}).get(attacker.get('type',''),1)
            # Split and distributed attack damage are relaxed to a free pool.
            best=max(best,_knockout_prizes(own,damage,pool+attacker.get('split',0)))
    return best


def evaluate(p, source, amount, target):
    denied=dict(allowed=False,reason='invalid_route',prizes=0,baseline_prizes=0,
                response_prizes=0,terminal=False,target=target,source=source)
    own=copy.deepcopy(p['own']);enemy=copy.deepcopy(p['enemy'])
    if source not in [b['id'] for b in own] or target not in [b['id'] for b in enemy]: return denied
    if p['enemy_prizes']<=1:
        return dict(denied,reason='give_last_prize')
    own=[b for b in own if b['id']!=source]
    if not own: return dict(denied,reason='own_last_body')
    baseline=0
    if p['attack_ready'] and p['own_active']==p['attacker']:
        baseline=max(sum(b['prize'] for b in row if b['hp']<=0) for row in _attack_outcomes(p,enemy,p['enemy_active']))
    if baseline and (baseline>=p['own_prizes'] or baseline>=sum(b['prize'] for b in enemy)):
        return dict(denied,reason='attack_already_wins',baseline_prizes=baseline)
    struck=next(b for b in enemy if b['id']==target);struck['hp']-=amount
    immediate=sum(b['prize'] for b in enemy if b['hp']<=0)
    enemy=[b for b in enemy if b['hp']>0]
    # Last-prize self-KO was excluded before considering a simultaneous finish.
    if immediate>=p['own_prizes'] or not enemy:
        return dict(denied,allowed=True,reason='terminal_blast',prizes=immediate,
                    baseline_prizes=baseline,terminal=True)
    attacker=next((b for b in own if b['id']==p['attacker']),None)
    if not p['attack_ready'] or attacker is None or p['own_active'] not in (p['attacker'],source):
        return dict(denied,reason='attack_not_funded_or_accessible')
    promotions=enemy if target==p['enemy_active'] and struck['hp']<=0 else [next(b for b in enemy if b['id']==p['enemy_active'])]
    outcomes=[]
    for active in promotions:
        for board in _attack_outcomes(p,enemy,active['id']):
            attack_gain=sum(b['prize'] for b in board if b['hp']<=0)
            gain=immediate+attack_gain
            survivors=[b for b in board if b['hp']>0]
            terminal=gain>=p['own_prizes'] or not survivors
            risk=0 if terminal else response_prizes(own,survivors)
            allowed=terminal or (attack_gain>0 and gain>baseline and risk<p['enemy_prizes']-1)
            outcomes.append(dict(denied,allowed=allowed,reason='terminal_attack' if terminal else (
                'attack_does_not_convert' if attack_gain==0 else 'no_extra_prize' if gain<=baseline else 'response_can_finish' if risk>=p['enemy_prizes']-1 else 'converted_and_response_bounded'),
                prizes=gain,baseline_prizes=baseline,response_prizes=risk,terminal=terminal))
    # Adversarial promotion: never assume the opponent volunteers a soft target.
    return min(outcomes,key=lambda r:(r['allowed'],r['terminal'],r['prizes'],-r['response_prizes']))


def best_route(p,source,amount):
    routes=[evaluate(p,source,amount,b['id']) for b in sorted(p['enemy'],key=lambda x:x['id'])]
    return max(routes,key=lambda r:(r['allowed'],r['terminal'],r['prizes']-r['baseline_prizes'],-r['response_prizes'],-r['target'])) if routes else {}


def evolution_choice(p,source):
    small=best_route(p,source,50);large=best_route(p,source,130)
    if small.get('allowed') and (not large.get('allowed') or (small['terminal'],small['prizes']) >= (large['terminal'],large['prizes'])):
        return dict(choice='clops',route=small)
    if large.get('allowed'): return dict(choice='noir',route=large)
    return dict(choice='wait',route=large)


def _fundable_threat(slot,entity,cards):
    from .public_attack_access import energy_debt
    uid=slot['local_card_uid']
    future={'CSV8C_157':PULT,'CSV8C_158':PULT,DUSKULL:NOIR,CLOPS:NOIR,
            'CSV10C_146':'CSV10C_148','CSV10C_147':'CSV10C_148','CSV10C_028':'CSV10C_030',
            'CSV10C_029':'CSV10C_030','CSV9.5C_043':'CSV7C_059','CSV10C_009':'CSV10C_010'}
    power=split=0
    for target_uid in [uid]+([future[uid]] if uid in future else []):
        card=cards[target_uid]
        # Generous one-attachment upper bound: up to two units for basics/ex,
        # three for evolved one-prize bodies. Ogerpon can also self-accelerate.
        allowance=3 if card['stage']!='Basic' and slot['prize_value']==1 else 2
        if target_uid=='CSV8C_028':allowance+=1
        for a in card.get('attacks',[]):
            observed=next((x for x in entity['attacks'] if x['attack_index']==a['attack_index']),{}) if target_uid==uid else {}
            costs=observed.get('cost_candidates',[a['cost']])
            if uid not in ('CSV10C_161','CSV10C_175','CSV8C_172') and energy_debt(costs,entity['energies'])>allowance:continue
            power=max(power,10000 if a['active_damage'] is None else a['active_damage'])
            split=max(split,a.get('bench_damage',0),60 if target_uid==PULT and a['attack_index']==1 else 0)
    if power:power+=100 if uid in ('CSV10C_161','CSV10C_175') else 30
    return power,split


def _body(slot, entity, cards, anticipate=False, funded=False):
    card=cards[slot['local_card_uid']];uid=slot['local_card_uid']
    printed=[a.get('active_damage') for a in card.get('attacks',[])]
    power=max([10000 if x is None else x for x in printed]+[0])
    # Dunsparce/stadium/tool/ability boosts in the reviewed Hop deck are
    # conservatively reserved, even when their resources are not visible.
    if uid in ('CSV10C_161','CSV10C_175'): power+=100
    # Unknown tools/modifiers or conditional attacks cannot establish safety.
    if slot.get('attached_tool_uid'): power=10000
    split=max([a.get('bench_damage',0) for a in card.get('attacks',[])]+[0])
    if uid==PULT: split=max(split,60)
    # Kingambit-style attack-wide changes and other unknown ability semantics
    # are handled by declining own projections, not pretending they are inert.
    counters=GHOSTS.get(uid,30 if uid=='CSV8C_094' else 0)
    frost=uid=='CSV7C_059'
    if anticipate:
        # Hidden evolution cards are never read. These are public, reviewed
        # possible upgrades of the five frozen opponents' visible bodies.
        if uid in (DUSKULL,CLOPS):counters=130
        if uid in ('CSV8C_157','CSV8C_158'):power=max(power,200);split=max(split,60)
        if uid in ('CSV10C_146','CSV10C_147'):power=max(power,180);split=max(split,30)
        if uid in ('CSV10C_028','CSV10C_029'):power=10000
        if uid=='CSV9.5C_043':power=max(power,60);frost=True
        if uid=='CSV10C_009':power=max(power,120)
        # Reserve a potential +30 attack modifier for ordinary attackers.
        # Hop's larger reviewed bonus ceiling was already reserved above.
        if uid not in ('CSV10C_161','CSV10C_175') and power>0:power+=30
        if funded:power,split=_fundable_threat(slot,entity,cards)
    return dict(id=slot['entity_serial'],hp=slot['remaining_hp'],prize=slot['prize_value'],
        attack=power,split=split,counters=counters,frost=frost,ability=card.get('has_ability',False),
        immune=uid=='CSV10C_010' and not entity.get('ability_disabled',False),
        counter_guard=uid=='CSV10C_052' and not entity.get('ability_disabled',False),
        type=card.get('energy_type',''),weakness={card.get('weakness_energy',''):card.get('weakness_multiplier',1)},
        status_tick=(20 if 'poisoned' in entity.get('conditions',[]) else 0)+(40 if 'burned' in entity.get('conditions',[]) else 0))


def calculate(frame,cards,include_spread=False):
    """Bridge a validated public frame into per-option preferences, no actions."""
    prefix='cursed2_' if include_spread else 'cursed_'
    options={str(o['index']):{prefix+k:v for k,v in dict(allowed=False,preferred=False,evolve=False,preserve=False,value=0,**({'prepare':False} if include_spread else {})).items()} for o in frame['options']}
    result=dict(options=options,routes=[],scope='public-board-full-funding-stress-v1')
    public=frame.get('public_state',{});decision=public.get('decision')
    if not decision or frame['prompt_kind'] not in ('main','effect_target','card_selection','evolve'): return result
    own=public['self'];enemy=public['opponent']
    if not own['active'] or not enemy['active']: return result
    table={e['entity_serial']:e for e in decision['entities']}
    slots=own['active']+own['bench']+enemy['active']+enemy['bench']
    if any(s['entity_serial'] not in table or s['local_card_uid'] not in cards or s['remaining_hp']<=0 for s in slots): return result
    # Same reviewed board-ability scope as the existing public gust projection.
    # An unreviewed effect may prevent the attack/counters; fail closed.
    from .public_gust_forecast import scope
    reviewed=scope()['board_abilities']
    stadium=decision.get('stadium',{}).get('card_uid')
    if stadium is not None and scope()['stadiums'].get(stadium)!=cards.get(stadium,{}).get('effect_id'):return result
    if any(s.get('attached_tool_uid') or (cards[s['local_card_uid']].get('has_ability') and
           cards[s['local_card_uid']].get('effect_id')!=reviewed.get(s['local_card_uid'])) for s in slots): return result
    active=own['active'][0]['entity_serial'];op_active=enemy['active'][0]['entity_serial']
    own_bodies=[_body(s,table[s['entity_serial']],cards) for s in own['active']+own['bench']]
    enemy_bodies=[_body(s,table[s['entity_serial']],cards,True,include_spread) for s in enemy['active']+enemy['bench']]
    attackers=[]
    for s in own['active']+own['bench']:
        e=table[s['entity_serial']]
        if s['local_card_uid']!=PULT or e.get('conditions'): continue
        if not any(a['attack_index']==1 and a['energy_ready'] for a in e['attacks']): continue
        # MAIN requires the actual attack frontier for an already-active Pult.
        if frame['prompt_kind']=='main' and s['entity_serial']==active and not any(o['kind']=='attack' and o.get('attack_index')==1 and o.get('source_uid')==PULT for o in frame['options']): continue
        attackers.append(s['entity_serial'])
    def position(attacker):
        return dict(own=own_bodies,enemy=enemy_bodies,own_active=active,enemy_active=op_active,
            own_prizes=own['prizes_remaining'],enemy_prizes=enemy['prizes_remaining'],
            attacker=attacker,attack_ready=attacker!=-1,attack_damage=200,**({'attack_counters':6} if include_spread else {}))
    def route(source,amount):
        return max((best_route(position(a),source,amount) for a in (attackers or [-1])),key=lambda r:(r.get('allowed',False),r.get('terminal',False),r.get('prizes',0),-r.get('response_prizes',0)))
    ghosts={s['entity_serial']:s for s in own['active']+own['bench'] if s['local_card_uid'] in GHOSTS}
    actual={}
    for source,s in sorted(ghosts.items()):
        if table[source].get('ability_disabled'):continue
        r=route(source,GHOSTS[s['local_card_uid']]);actual[source]=r;result['routes'].append(r)
    roots=[s for s in own['active']+own['bench'] if s['local_card_uid']==DUSKULL and
           not table[s['entity_serial']]['played_this_turn'] and not table[s['entity_serial']]['evolved_this_turn'] and
           not decision['self']['is_first_turn']]
    candy_routes={s['entity_serial']:route(s['entity_serial'],130) for s in roots}
    for o in frame['options']:
        m=options[str(o['index'])]
        # Internal names stay stable; the explicit v2 fact family opts in.
        if include_spread:
            m={k.replace('cursed2_','cursed_'):v for k,v in m.items()}
        source=o.get('source_entity_serial');uid=o.get('source_uid')
        if o['kind']=='use_ability' and uid in GHOSTS and o.get('ability_index')==0 and source in ghosts and ghosts[source]['local_card_uid']==uid:
            r=actual.get(source,{})
            same=[v for s,v in actual.items() if ghosts[s]['local_card_uid']==uid]
            m['cursed_allowed']=r.get('allowed',False) and all(v['allowed'] and v['target']==r['target'] for v in same)
            m['cursed_value']=1000*r.get('prizes',0)-100*r.get('response_prizes',0)
        if o['kind']=='effect_target' and uid in GHOSTS:
            # Typed windows omit source entity. With duplicate copies, only a
            # target approved for EVERY possible source gets a preference.
            choices=[r for s,r in actual.items() if ghosts[s]['local_card_uid']==uid]
            m['cursed_preferred']=bool(choices) and all(r['allowed'] and r['target']==o.get('target_entity_serial') for r in choices)
        if o['kind']=='evolve' and o.get('card_uid')==NOIR and o.get('target_entity_serial') in ghosts:
            target=o['target_entity_serial'];small=actual.get(target,{});large=route(target,130)
            preserve=small.get('allowed',False) and (small.get('terminal'),small.get('prizes',0))>=(large.get('terminal'),large.get('prizes',0))
            m['cursed_preserve']=preserve;m['cursed_evolve']=large.get('allowed',False) and not preserve
        if o['kind']=='play_trainer' and o.get('card_uid')==CANDY and any(h['local_card_uid']==NOIR for h in own['hand']):
            m['cursed_evolve']=any(r.get('allowed',False) for r in candy_routes.values())
        if o['kind']=='evolve' and o.get('card_uid')==NOIR and o.get('source_uid')==CANDY:
            m['cursed_evolve']=candy_routes.get(o.get('target_entity_serial'),{}).get('allowed',False)
        if o['kind']=='evolve' and o.get('card_uid')==CLOPS and o.get('target_entity_serial') in candy_routes:
            m['cursed_evolve']=route(o['target_entity_serial'],50).get('allowed',False)
        if include_spread and o['kind']=='retreat' and o.get('target_entity_serial') in attackers and not any(r.get('allowed') for r in actual.values()):
            p=position(o['target_entity_serial']);p['own_active']=o['target_entity_serial']
            m['cursed_prepare']=any(best_route(p,s,GHOSTS[v['local_card_uid']]).get('allowed',False) for s,v in ghosts.items())
        if include_spread:options[str(o['index'])]={k.replace('cursed_','cursed2_'):v for k,v in m.items()}
    if include_spread:result['scope']='public-funded-reply-and-phantom-spread-v2'
    return result
