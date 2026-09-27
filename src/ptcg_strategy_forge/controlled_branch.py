"""Qualification of research-only, single-action replay interventions.

This never gives a continuation result the status of an optimal-action proof.
Private engine state and the other seat's observations are not model inputs.
"""
import json


def semantic_option(option):
    return {k:v for k,v in option.items() if k not in ('index','option_fingerprint')}


def bind_intervention(frame, frontier, rule, request):
    source=frame['source']; sem=frame['select_semantics']; options=frame['options']
    if (frontier.get('enabled') is not True or frontier.get('profile_id')!='ptcgdap-base-model-frontier-v1'
        or sem.get('min_count')!=1 or sem.get('max_count')!=1 or len(rule)!=1
        or any(source.get(k)!=frontier.get(k) or source.get(k)!=request.get(k)
               for k in ('public_observation_hash','window_id'))):
        raise ValueError('branch_frontier_not_fresh')
    indexes=frontier.get('indexes',[])
    if (len(indexes)<2 or len(set(indexes))!=len(indexes) or rule[0] not in indexes
        or any(type(i) is not int or not 0<=i<len(options) for i in indexes)):
        raise ValueError('branch_frontier_invalid')
    matches=[n for n,o in enumerate(options) if semantic_option(o)==request['option']]
    if len(matches)!=1 or matches[0] not in indexes:
        raise ValueError('branch_semantic_binding_failed')
    return matches[0]


def public_event(row):
    d=row['decision']
    # Timing/audit hashes are not gameplay. Include the entire public observation
    # and actual accepted action, not only the seed or the rule's proposal.
    return dict(seat=row['seat'],frame=d['frame'],accepted=d['host']['accepted_indexes'])


def qualify_pair(original, branch, baseline, alternate, request):
    for m in (baseline,alternate):
        if not m.get('clean') or not m.get('terminal') or m.get('winner_index') not in (0,1):
            raise ValueError('branch_dirty_or_truncated')
    for key in ('seed','candidate_seat','candidate_sha256','opponent_sha256','runtime_sha256'):
        if baseline.get(key)!=alternate.get(key):raise ValueError('branch_continuation_mismatch')
    found=False;prefix=0
    for a,b in zip(original,branch):
        fa,fb=a['decision']['frame'],b['decision']['frame']
        if a['seat']==baseline['candidate_seat'] and fa['source']=={k:request[k] for k in ('public_observation_hash','window_id')}:
            if fa!=fb or a['seat']!=b['seat']:raise ValueError('branch_target_state_mismatch')
            d=a['decision']; rule=d['host']['accepted_indexes']
            index=bind_intervention(fa,d['host']['model_input_evidence']['base_frontier'],rule,request)
            h=b['decision']['host']
            if h['accepted_indexes']!=[index] or [index]==rule or h.get('fallback_used') or h.get('error_code') or h.get('status')!='accepted':
                raise ValueError('branch_action_not_witnessed')
            found=True;break
        if public_event(a)!=public_event(b):raise ValueError('branch_prefix_mismatch')
        prefix+=1
    if not found:raise ValueError('branch_target_missing')
    return dict(prefix_decisions=prefix,outcome_delta=int(alternate['winner_index']==alternate['candidate_seat'])-int(baseline['winner_index']==baseline['candidate_seat']),
                label_kind='single_seed_paired_terminal_sample',expected_value_proven=False,
                rng_coupling='deterministic_initial_seed_and_identical_action_prefix; no post-action RNG reset')


def read_trace(path):
    with open(path,encoding='utf-8') as f:return [json.loads(json.loads(line)['payload']) for line in f]
