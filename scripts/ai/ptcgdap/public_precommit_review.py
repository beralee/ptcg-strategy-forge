"""Opt-in, current-window completion preference, never a safety/value proof.

Only the caller evaluates policy; this helper cannot mutate state or call Host.
The same validated public window is evaluated twice at most. Executing the
returned hand-card action consumes that window and requires reobservation.
"""

PREPARATION = frozenset(('attach_energy', 'evolve', 'play_basic_to_bench',
                        'play_trainer', 'play_stadium', 'attach_tool'))
CLOSING = frozenset(('attack', 'granted_attack', 'end_turn'))


def gate(frame, selected, audit, quotas=None):
    if audit.get('owner_layer') != 'base_graph': return 'forced_authority'
    semantics = frame['select_semantics']
    if (len(selected) != 1 or semantics['min_count'] != 1 or semantics['max_count'] != 1
            or frame.get('prompt_kind') != 'main' or quotas is not None):
        return 'not_single_main'
    if frame['options'][selected[0]]['kind'] not in CLOSING: return 'not_closing'
    if audit.get('damage_plan', {}).get('status') == 'unavailable': return 'damage_unknown'
    if audit.get('turn_contract', {}).get('route_authority_applied'): return 'route_authority'
    if audit.get('turn_program_canary', {}).get('applied'): return 'program_authority'
    for key in ('semantic_transaction', 'turn_transaction'):
        txn = audit.get(key, {})
        if any(txn.get(k) for k in ('selected_transaction_id', 'transaction_id', 'state', 'current_indexes')):
            return 'transaction_authority'
    comparison = audit.get('plan_comparison', {})
    if comparison.get('reason') == 'current_proven_finish': return 'proven_finish'
    remaining = frame['public_state']['self']['prizes_remaining']
    active = frame['public_state']['opponent'].get('active', [])
    for option in frame['options']:
        if option['kind'] in ('attack', 'granted_attack') and option.get('projected_knockout'):
            prizes = option.get('target_prize_value') or (active[0].get('prize_value', 0) if active else 0)
            if remaining > 0 and prizes >= remaining: return 'proven_finish'
    return ''


def propose(frame, selected, allowed, scorecards, ranked, rerun_index, allowed_uids):
    own = frame['public_state']['self']
    hand = {(c['serial'], c['local_card_uid']) for c in own.get('hand', [])}
    cards = {c['index']: c for c in scorecards}
    eligible = []
    for index in ranked:
        option = frame['options'][index]
        card = cards[index]
        # Redraw without increased resources is optional hand cycling, not
        # evidence of unfinished preparation. These exact reviewed printings
        # return the remaining hand and draw N; do not infer from card names.
        if option.get('card_uid') in ('CSV3C_123', '30thDC_040'):
            count = own['prizes_remaining'] if option['card_uid'] == 'CSV3C_123' else (8 if own['prizes_remaining'] == 6 else 6)
            after = len(hand) - 1
            if min(count, own['deck_count'] + after) <= after: continue
        if option['kind'] in ('attach_energy', 'evolve', 'attach_tool'):
            if not any(slot.get('entity_serial') == option.get('target_entity_serial')
                       for slot in own.get('active', []) + own.get('bench', [])):
                continue
        if (index in allowed and option['kind'] in PREPARATION and option.get('card_uid') in allowed_uids and card.get('score', 0) > 0
                and card.get('matched_rules')
                and (option.get('card_serial'), option.get('card_uid')) in hand):
            eligible.append(index)
    # Preserve score/goal priorities, resolve ties by current public identity.
    eligible.sort(key=lambda i: (-cards[i]['score'], -cards[i]['goal_priority'],
        frame['options'][i]['kind'], frame['options'][i]['card_uid'],
        frame['options'][i]['card_serial'], frame['options'][i].get('target_entity_serial') or 0))
    index = eligible[0] if eligible else selected[0]
    return dict(profile='completion-v1', evaluation_passes=2, first_index=selected[0],
                rerun_index=rerun_index, selected_index=index, eligible_indexes=eligible,
                changed=index != selected[0], reason='positive_preparation' if eligible else 'no_preparation')
