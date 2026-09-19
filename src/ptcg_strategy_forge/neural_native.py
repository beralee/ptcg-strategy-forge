"""Reference for the existing Godot development-frame Actor projection.

This is a training adapter, not a new runtime tensor profile. Its result must
match a pinned Godot projector's captured tensors before a sample is used.
The raw CABT tensorizer is a different projection and is never substituted.
"""
from __future__ import annotations

import hashlib
import json

from scripts.ai.ptcgdap.cabt_tree_hash import jcs_canonical_json_bytes
from scripts.ai.ptcgdap.ptcgai_model_actor import (
    FRAME_WIDTH, MAX_OPTIONS, OPTION_WIDTH, PublicActorTensors, TENSOR_PROFILE_ID,
)
from .native_trace import _trace_frame_error


def uid_feature(uid):
    digest = hashlib.sha256(b'PTCGDAP\0MODEL_UID_V1\0' + uid.encode('ascii')).digest()
    return int.from_bytes(digest[:4], 'big', signed=True)


def _values(values):
    result, presence = [], []
    for value in values:
        if value is None:
            result.append(0); presence.append(0)
        elif type(value) in (int, bool) and -(2**31) <= int(value) < 2**31:
            result.append(int(value)); presence.append(1)
        else:
            raise ValueError('native_model_feature_range_invalid')
    return tuple(result), tuple(presence)


def project_native_frame(frame, allowed_uids):
    if _trace_frame_error(frame):
        raise ValueError('native_model_public_frame_invalid')
    state, semantics, options = frame['public_state'], frame['select_semantics'], frame['options']
    if len(options) > MAX_OPTIONS:
        raise ValueError('native_model_option_limit')
    own, opponent = state['self'], state['opponent']
    turn = own.get('turn', {})
    f, fp = _values([
        state.get('turn_number'), frame.get('sequence'), None,
        own.get('prizes_remaining'), opponent.get('prizes_remaining'),
        own.get('deck_count'), opponent.get('deck_count'), len(own['hand']), opponent.get('hand_count'),
        None, None, not turn.get('supporter_available', True), None,
        not turn.get('manual_attachment_available', True), not turn.get('retreat_available', True),
        semantics.get('select_type_raw'), semantics.get('select_context_raw'),
        semantics.get('min_count'), semantics.get('max_count'),
        semantics.get('remain_damage_counter'), semantics.get('remain_energy_cost'),
        len(options), None, None,
    ])
    assert len(f) == FRAME_WIDTH
    rows = []
    for index, option in enumerate(options):
        uid = option.get('target_uid') if option.get('kind') == 'evolve' else option.get('card_uid')
        if uid is None: uid = option.get('source_uid')
        if uid is not None and (type(uid) is not str or uid not in allowed_uids):
            raise ValueError('native_model_unknown_uid')
        serial = next((option[k] for k in ('card_serial', 'target_serial', 'source_serial') if option.get(k) is not None), None)
        hashed = uid_feature(uid) if uid is not None else None
        values, presence = _values([
            option['option_type_raw'], option.get('option_number'), option.get('option_area_raw'), serial,
            None, option.get('energy_type_raw'), option.get('energy_count'), option.get('pending_assignment_count'),
            None, None, option.get('attack_index'), hashed, serial, option.get('special_condition_type'), hashed, None,
        ])
        semantic = {k:v for k,v in option.items() if k != 'index'}
        key = hashlib.sha256(b'PTCGDAP\0MODEL_OPTION_V1\0' + jcs_canonical_json_bytes({'local_card_uid':uid, 'option':semantic})).hexdigest().upper()
        # Godot's development adapter sorts Array string representations, not
        # numeric tuples. Preserve that existing wire behavior exactly.
        sort_key = f'{list(values)}|{list(presence)}|{key}'
        rows.append((sort_key, index, values, presence, key))
    rows.sort(key=lambda row: (row[0], row[1]))
    indexes = tuple(row[1] for row in rows)
    padding = MAX_OPTIONS - len(rows)
    return PublicActorTensors(
        profile_id=TENSOR_PROFILE_ID, frame_i32=f, frame_presence_i32=fp,
        option_i32=tuple(row[2] for row in rows) + ((0,)*OPTION_WIDTH,)*padding,
        option_presence_i32=tuple(row[3] for row in rows) + ((0,)*OPTION_WIDTH,)*padding,
        option_mask_i32=(1,)*len(rows) + (0,)*padding,
        semantic_keys=tuple(row[4] for row in rows), row_to_current_index=indexes,
        current_index_to_row={index:row for row,index in enumerate(indexes)},
        min_count=semantics['min_count'], max_count=semantics['max_count'],
    )


def native_frontier(policy, option_count):
    """None means unavailable, not an empty legal candidate set."""
    base = policy.get('base_result', {})
    nodes = base.get('node_audit')
    if type(nodes) is not list: return None
    frontier = None
    for node in nodes:
        if type(node) is dict and node.get('operator') == 'base_veto':
            frontier = node.get('output_indexes')
    if frontier is None: return None
    if (type(frontier) is not list or any(type(i) is not int or not 0 <= i < option_count for i in frontier)
            or len(frontier) != len(set(frontier))):
        raise ValueError('native_model_frontier_invalid')
    return frontier


def verify_captured_projection(tensors, captured, projector_sha256):
    if (captured.get('status') != 'captured' or captured.get('profile_id') != 'ptcgdap-development-model-input-v1'
            or captured.get('projector_sha256', '').upper() != projector_sha256.upper()):
        raise ValueError('native_model_projector_binding_invalid')
    n = len(tensors.row_to_current_index)
    expected = {
        'frame_i32':list(tensors.frame_i32), 'frame_presence_i32':list(tensors.frame_presence_i32),
        'option_i32':[v for row in tensors.option_i32[:n] for v in row],
        'option_presence_i32':[v for row in tensors.option_presence_i32[:n] for v in row],
        'option_mask_i32':list(tensors.option_mask_i32[:n]),
        'row_to_current_index':list(tensors.row_to_current_index), 'semantic_keys':list(tensors.semantic_keys),
    }
    for key, value in expected.items():
        if json.dumps(captured.get(key)) != json.dumps(value):
            raise ValueError('native_model_projection_mismatch:' + key)
    return True
