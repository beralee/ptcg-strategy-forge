"""Qualify real Godot teacher windows; fixture datasets remain a separate lane."""
from __future__ import annotations
import copy
import hashlib
import json

from scripts.ai.ptcgdap.semantic_model_profile import project_semantic_frame, PROFILE_ID
from .native_trace import _trace_frame_error


def teacher_seats(game, teacher_sha256):
    seat=game.get('candidate_seat')
    if (game.get('candidate_sha256')!=teacher_sha256 or type(seat) not in (int,float) or seat not in (0,1)
            or not isinstance(game.get('opponent_sha256'),str) or len(game['opponent_sha256'])!=64):
        raise ValueError('neural_teacher_identity_mismatch')
    return {0,1} if game['opponent_sha256']==teacher_sha256 else {int(seat)}


def equivalent_hand_copy_indexes(frame, frontier, selected):
    """Only interchangeable current-hand copies, never different target entities."""
    options=frame['options']; chosen=options[selected]
    allowed={'attach_energy','play_trainer','play_basic_to_bench','play_stadium','attach_tool'}
    if chosen.get('kind') not in allowed:return [selected]
    hand={c.get('serial'):c.get('local_card_uid') for c in frame['public_state']['self']['hand']}
    uid=chosen.get('card_uid'); serial=chosen.get('card_serial')
    if uid is None or serial is None or hand.get(serial)!=uid:return [selected]
    def meaning(option):return {k:v for k,v in option.items() if k not in ('index','option_fingerprint','card_serial')}
    target=meaning(chosen)
    return [i for i in frontier if (i==selected or options[i].get('card_serial') is not None
            and hand.get(options[i]['card_serial'])==uid and meaning(options[i])==target)]


def admit_unique_teacher_example(seen, identity, example):
    # Match-local decision IDs may differ across mirrored games. The projected
    # input, candidate binding and teacher label may not differ for one key.
    content={k:v for k,v in example.items() if k!='decision_id'}
    fingerprint=hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if identity in seen:
        if seen[identity]!=fingerprint:raise ValueError('neural_duplicate_teacher_conflict')
        return False
    seen[identity]=fingerprint
    return True


def qualify_teacher_record(payload, *, allowed_uids, projector_sha256):
    return _qualify_record(payload,allowed_uids=allowed_uids,projector_sha256=projector_sha256)


def qualify_teacher_query_record(payload, *, allowed_uids, projector_sha256, model_artifact_sha256):
    """A rule query on a model-visited state is NOT an executed teacher action.

    The run caller must verify that the frozen rule documents equal the teacher.
    """
    if not isinstance(model_artifact_sha256,str) or len(model_artifact_sha256)!=64:
        raise ValueError('neural_query_model_identity_invalid')
    return _qualify_record(payload,allowed_uids=allowed_uids,projector_sha256=projector_sha256,
                           query_artifact_sha256=model_artifact_sha256.upper())


def _qualify_record(payload, *, allowed_uids, projector_sha256, query_artifact_sha256=None):
    from tools.local_engine_bench import verify_window
    record=payload['decision']; checked=verify_window(record,_trace_frame_error)
    frame,host=checked['frame'],checked['host']; policy=record['policy']
    if host.get('status')!='accepted' or host.get('fallback_used') or host.get('error_code'):
        return None,'host_not_accepted'
    if (any(type(payload.get(k)) is not int for k in ('step_decision_count','engine_commit_delta','engine_rejection_delta'))
            or payload.get('step_decision_count')!=1 or payload.get('engine_commit_delta')!=1 or payload.get('engine_rejection_delta')!=0):
        return None,'not_one_to_one_engine_commit'
    model=host.get('model_decision',{})
    if query_artifact_sha256:
        if not model.get('invoked'):return None,'not_model_visited'
        if (model.get('diagnostic_code') or model.get('model_artifact_sha256')!=query_artifact_sha256
            or model.get('selected_indexes')!=host['accepted_indexes']
            or model.get('fallback_indexes')!=policy.get('reported_indexes')):
            raise ValueError('neural_teacher_query_binding_invalid')
    elif model.get('invoked'):
        return None,'model_visited_requires_distinct_teacher_query_lane'
    capture=host.get('model_input_evidence',{})
    if capture.get('status')!='captured': return None,'projection_unavailable'
    if (capture.get('profile_id')!='ptcgdap-semantic-model-input-v1' or capture.get('tensor_profile_id')!=PROFILE_ID
            or capture.get('semantic_projector_sha256','').upper()!=projector_sha256.upper()):
        raise ValueError('neural_projector_identity_mismatch')
    frontier=capture.get('base_frontier',{})
    if (frontier.get('profile_id')!='ptcgdap-base-model-frontier-v1'
            or frontier.get('window_id')!=frame['source']['window_id']
            or frontier.get('public_observation_hash')!=frame['source']['public_observation_hash']):
        raise ValueError('neural_frontier_binding_invalid')
    if frontier.get('enabled') is not True: return None,'base_gate:'+str(frontier.get('reason'))
    indexes=frontier.get('indexes'); sem=frame['select_semantics']
    if (type(indexes) is not list or len(indexes)<2 or len(indexes)!=len(set(indexes))
            or any(type(i) is not int or not 0<=i<len(frame['options']) for i in indexes)
            or sem['min_count']!=1 or sem['max_count']!=1 or indexes!=capture.get('frontier_indexes')):
        raise ValueError('neural_frontier_invalid')
    selected=policy.get('reported_indexes') if query_artifact_sha256 else host['accepted_indexes']
    if (policy.get('reported_window_id')!=frame['source']['window_id'] or
            policy.get('reported_public_observation_hash')!=frame['source']['public_observation_hash']):
        raise ValueError('neural_teacher_binding_invalid')
    if (not isinstance(selected,list) or len(selected)!=1 or type(selected[0]) is not int
            or selected!=policy.get('reported_indexes') or selected[0] not in indexes):
        raise ValueError('neural_teacher_selection_invalid')
    if policy['base_result'].get('selected_indexes')!=selected or not policy.get('ok') or policy.get('error_code'):
        raise ValueError('neural_teacher_selection_invalid')
    t=project_semantic_frame(frame,allowed_uids); n=len(t.row_to_current_index)
    expected={'frame_i32':list(t.frame_i32),'frame_presence_i32':list(t.frame_presence_i32),
        'option_i32':[v for row in t.option_i32[:n] for v in row],
        'option_presence_i32':[v for row in t.option_presence_i32[:n] for v in row],
        'option_mask_i32':list(t.option_mask_i32[:n]),'row_to_current_index':list(t.row_to_current_index),'semantic_keys':list(t.semantic_keys)}
    for key,value in expected.items():
        if value!=capture.get(key): raise ValueError('neural_projection_mismatch:'+key)
    rows=[r for r,index in enumerate(t.row_to_current_index) if index in indexes]
    ordered=[t.row_to_current_index[r] for r in rows]
    result={'evidence_kind':'godot_same_window_rule_query_v1' if query_artifact_sha256 else 'godot_single_commit_teacher_v1','frame':list(t.frame_i32),
        'frame_presence':list(t.frame_presence_i32),'options':[list(t.option_i32[r]) for r in rows],
        'option_presence':[list(t.option_presence_i32[r]) for r in rows], 'label':ordered.index(selected[0]),
        'current_indexes':ordered,'semantic_keys':[t.semantic_keys[r] for r in rows],
        'context':frame['prompt_kind'],'seat':frame['seat'],'window_id':frame['source']['window_id'],
        'public_observation_hash':frame['source']['public_observation_hash'],'decision_id':record['decision_id']}
    equivalent=equivalent_hand_copy_indexes(frame,ordered,selected[0])
    result.update(positive_labels=[ordered.index(i) for i in equivalent],
                  equivalence_kind='same_uid_hand_copy_current_target_v1')
    if query_artifact_sha256:
        result.update(teacher_was_executed=False,observed_host_indexes=host['accepted_indexes'],model_artifact_sha256=query_artifact_sha256)
    return result,'qualified'
