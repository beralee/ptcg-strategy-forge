"""Versioned public observation transport and recoverable public-window journal.

Rules are evaluated by the producer engine. This consumer validates receipts,
keeps unknown states typed, and always submits decisions to the existing Base.
"""
from __future__ import annotations

import copy
import json
from . import public_input_v2 as v2
from .base_input import BaseInput, canonical, digest
from .public_decision_facts import obj, array, integer, BOOL, UID, schema_error

PROFILE = 'ptcg-public-input-v3'
F = v2.tagged
ID, NAT, SEAT, TEXT = v2.ID, v2.NAT, v2.SEAT, v2.TEXT
enum, nullable, fact = v2.enum, v2.nullable, v2.fact
ZONES = ['deck', 'hand', 'prizes', 'discard', 'lost', 'active', 'bench', 'stadium', 'outside']
ZONE = obj({'player': SEAT, 'zone': enum(*ZONES), 'count': NAT, 'cards': F(array(UID, 120))})
EVENT = copy.deepcopy(v2.EVENT)
EVENT['properties'].update({
    'type': enum(*(v2.EVENT_TYPES + ['move', 'damage_change', 'status_change', 'information_checkpoint'])),
    'from_zone': F(enum(*ZONES)), 'to_zone': F(enum(*ZONES)),
    'source_entity': F(integer(minimum=1)), 'target_entity': F(integer(minimum=1)),
    'amount_hp': F(integer(minimum=-1000000)), 'origin': enum('engine_action', 'public_boundary', 'engine_shuffle', 'engine_coin'),
    'random_outcome': F(enum('heads', 'tails')),
})
EVENT['required'] = list(EVENT['properties'])
HISTORY = obj({'stream': ID, 'match': ID, 'seat': SEAT, 'cursor': NAT,
    'first_available': integer(minimum=1), 'complete': BOOL,
    'scope': {'type': 'string', 'const': 'public_boundaries_and_actions'},
    'events': array(EVENT, 512), 'snapshot': array(ZONE, 20), 'snapshot_cursor': NAT,
    'checkpoint': NAT})
ABILITY = copy.deepcopy(v2.ABILITY)
ABILITY['properties'].update({'availability_reason': F(TEXT),
    'resolution': F(enum('immediate', 'requires_interaction', 'passive', 'unknown'))})
ABILITY['required'] = list(ABILITY['properties'])
EFFECT = copy.deepcopy(v2.EFFECT)
EFFECT['properties'].update({'source_kind': F(enum('entity', 'card', 'player', 'rule')),
    'source_entity': F(integer(minimum=1)), 'source_player': F(SEAT),
    'identity_scope': enum('engine_instance', 'resolved_rule'),
    'lifecycle': F(enum('current_turn', 'next_turn', 'while_present', 'until_leave_active', 'unknown'))})
EFFECT['required'] = list(EFFECT['properties'])
EVALUATION = obj({'attacker': integer(minimum=1), 'target': integer(minimum=1), 'attack_index': integer(31),
    'damage_hp': F(NAT), 'kind': enum('exact', 'conditional', 'range', 'unknown'),
    'minimum_hp': F(NAT), 'maximum_hp': F(NAT), 'unresolved': array(ID),
    'damage_prevented': F(BOOL), 'effects_prevented': F(BOOL),
    'attacker_modifier_hp': F(integer(minimum=-1000000)), 'defender_modifier_hp': F(integer(minimum=-1000000)),
    'weakness_value': F(TEXT), 'weakness_type': F(TEXT), 'resistance_value': F(TEXT),
    'cost_satisfied': F(BOOL), 'cost_candidates': F(array(TEXT, 256)), 'restrictions': array(ID)})
CAPABILITY_KEYS = ['snapshot', 'ability_quotas', 'effects', 'event_stream', 'interaction', 'attack_evaluation']
PAYLOAD_SCHEMA = copy.deepcopy(v2.PAYLOAD_SCHEMA)
INTERACTION = copy.deepcopy(v2.INTERACTION)
INTERACTION['properties']['commit_stage'] = F(enum('idle', 'collecting_choices', 'declared_pending_resolution'))
INTERACTION['required'] = list(INTERACTION['properties'])
PAYLOAD_SCHEMA['properties'].update({
    'version': {'type': 'integer', 'const': 3}, 'abilities': array(ABILITY, 128),
    'effects': array(EFFECT, 512), 'history': HISTORY,
    'interaction': INTERACTION,
    'evaluations': array(EVALUATION, 1024),
    'capabilities': obj({k: F(enum('supported', 'partial', 'unsupported')) for k in CAPABILITY_KEYS}),
})
PAYLOAD_SCHEMA['required'] = list(PAYLOAD_SCHEMA['properties'])


def contract():
    result = v2.contract()
    result.update(profile=PROFILE, version=3, payload_schema=PAYLOAD_SCHEMA,
        history_scope='Every observed public boundary is reconciled; internal unobserved intermediate states are not a replay.',
        training_profiles={'public-observation-v3': 'typed public snapshot and cursor-bound journal; missing capabilities remain features, never zero',
                           'semantic-complete-v3': 'all declared capabilities supported, all required semantic facts resolved'},
        migration='new closed observation envelope {profile,frame,input}; v1/v2 unchanged',
        privacy='Public-zone moves use printing multisets. Hidden-to-hidden moves disclose count only. No physical card identifiers or hidden ordering.')
    result['supported_effect_types'] = v2.SUPPORTED_EFFECT_TYPES + [
        'prevent_attack_damage_and_effects', 'attack_lock_until_leave_active', 'defender_attack_lock',
        'hp_modifier', 'retreat_cost', 'energy_supply', 'early_evolution']
    result['unsupported_effect_types'] = [
        'unreviewed_damage_increase_instances', 'unreviewed_damage_and_effect_immunity_instances',
        'unreviewed_attack_and_evolution_restriction_instances', 'energy_supply_effect_instances',
        'attack_cost_effect_instances', 'retreat_cost_effect_instances', 'hp_effect_instances',
        'weakness_effect_instances', 'dynamic_resistance_override', 'general_stadium_and_field_effect_instances']
    result['evaluation_scope'] = {
        'reviewed_attackers': ['CSV8C_159','CSV8C_158','CS4DaC_137','CSV8C_094','CSV3C_042','CSV7C_059'],
        'reviewed_board_sources': ['CSV8C_159','CSV8C_158','CS4DaC_137','CSV8C_094','CSV3C_042','CSV7C_059',
                                  'CSV8C_135','CS6.5C_066','CSV1C_118','CSV2C_127','CSV8C_203'],
        'energy': 'basic only; unreviewed board sources fail closed before damage getter dispatch',
        'damage': 'conditional main hit only; excludes subsequent effect damage and counters',
        'predicates': 'defender prevention predicates before attack-specific ignores; not final immunity or legality proof',
        'simulation': False}
    result['identity_domains']['frame_card_reference'] = 'v3 window-local public ordinal, reissued from public field paths; never persistent registry serial'
    return result


def _legacy(payload):
    """Only for shared v2 invariants, never for inventing historical semantics."""
    old = copy.deepcopy(payload)
    old['version'] = 2
    for key in ('evaluations', 'capabilities'): old.pop(key)
    for row in old['abilities']:
        for key in ('availability_reason', 'resolution'): row.pop(key)
    for row in old['effects']:
        for key in ('source_kind', 'source_entity', 'source_player', 'identity_scope', 'lifecycle'): row.pop(key)
    old['interaction'].pop('commit_stage')
    old['history'] = dict(stream=payload['history']['stream'], match=payload['history']['match'], seat=payload['history']['seat'],
        cursor=0, first_available=1, complete=False, scope='engine_logged_actions', events=[])
    return old


def validate_history(history):
    if schema_error(history, HISTORY): raise ValueError('public_input_v3_history_shape')
    v2._check_tags(history)
    seqs = [e['seq'] for e in history['events']]
    if seqs != sorted(set(seqs)) or any(s < history['first_available'] or s > history['cursor'] for s in seqs):
        raise ValueError('public_input_v3_history_sequence')
    if history['snapshot_cursor'] != history['cursor'] or history['first_available'] > history['cursor'] + 1:
        raise ValueError('public_input_v3_snapshot_cursor')
    if history['complete'] and (history['first_available'] != 1 or seqs != list(range(1, history['cursor'] + 1))):
        raise ValueError('public_input_v3_false_complete_history')
    seen = set()
    for zone in history['snapshot']:
        key = (zone['player'], zone['zone'])
        if key in seen: raise ValueError('public_input_v3_duplicate_zone')
        seen.add(key)
        hidden = zone['zone'] in ('deck', 'prizes') or (zone['zone'] == 'hand' and zone['player'] != history['seat'])
        if hidden and zone['cards']['status'] == 'known': raise ValueError('public_input_v3_hidden_cards')
        if zone['cards']['status'] == 'known' and len(zone['cards']['value']) != zone['count']:
            raise ValueError('public_input_v3_zone_count')
    for event in history['events']:
        if ((event['visibility'] == 'all' and event['visible_to'] is not None) or
            (event['visibility'] == 'seat' and event['visible_to'] != history['seat'])):
            raise ValueError('public_input_v3_visibility')
        if event['type'] in ('draw_card', 'take_prize') and event['player'] != history['seat'] and event['cards']['status'] == 'known':
            raise ValueError('public_input_v3_hidden_cards')
        if event['type'] == 'move' and event['cards']['status'] == 'known':
            zones = [event[k]['value'] for k in ('from_zone', 'to_zone') if event[k]['status'] == 'known']
            visible = any(z not in ('deck', 'prizes', 'hand', 'outside') or (z == 'hand' and event['player'] == history['seat']) for z in zones)
            if not visible: raise ValueError('public_input_v3_hidden_move_identity')
    if seen != {(player, zone) for player in (0, 1) for zone in ZONES if zone != 'outside'}:
        raise ValueError('public_input_v3_missing_zone_snapshot')


def validate_payload(frame, payload):
    if schema_error(payload, PAYLOAD_SCHEMA): raise ValueError('public_input_v3_shape')
    v2._check_tags(payload)
    v2.validate_payload(frame, _legacy(payload))
    validate_history(payload['history'])
    zones = {(z['player'], z['zone']): z for z in payload['history']['snapshot']}
    for side in ('self', 'opponent'):
        player = frame['seat'] if side == 'self' else 1-frame['seat']
        board = frame['public_state'][side]
        expected = {'deck': board['deck_count'], 'prizes': board['prizes_remaining'],
                    'hand': len(board['hand']) if side == 'self' else board['hand_count'],
                    'discard': len(board['discard'])}
        for zone, count in expected.items():
            if zones[player, zone]['count'] != count: raise ValueError('public_input_v3_snapshot_frame_mismatch')
    entities = {e['entity']: e for e in payload['entities']}
    for row in payload['effects']:
        if row['target_entity'] is not None and row['target_entity'] not in entities: raise ValueError('public_input_v3_effect_target')
    keys = set()
    for row in payload['evaluations']:
        key = (row['attacker'], row['attack_index'], row['target'])
        if key in keys or row['attacker'] not in entities or row['target'] not in entities:
            raise ValueError('public_input_v3_evaluation_identity')
        keys.add(key)
        if row['kind'] == 'exact' and (row['damage_hp']['status'] != 'known' or row['unresolved']):
            raise ValueError('public_input_v3_false_exact')


class PublicInputV3(v2.PublicInputV2):
    @classmethod
    def capture(cls, frame, supplement=None):
        if type(frame) is dict and frame.get('profile') == PROFILE:
            if set(frame) != {'profile', 'frame', 'input'} or supplement is not None:
                raise ValueError('public_input_v3_envelope')
            frame, supplement = frame['frame'], frame['input']
        base = BaseInput.capture(frame)
        if supplement is not None: validate_payload(base.frame(), supplement)
        return cls(base, canonical(supplement) if supplement is not None else None)

    def envelope(self):
        return dict(profile=PROFILE, frame=self.base.frame(), input=self.payload())

    def document(self):
        result = super().document()
        result['profile'] = PROFILE
        return result

    def coverage(self):
        payload = self.payload()
        if payload is None:
            return dict(profile=PROFILE, supported=False, training_ready=False, gaps=['legacy_data_missing_semantics'],
                        missing=['/'], capabilities={}, source='legacy_data')
        missing = v2._missing(payload)
        gaps = list(payload['gaps'])
        caps = payload['capabilities']
        transport_ready = (all(caps[k]['status'] == 'known' and caps[k]['value'] == 'supported'
                               for k in ('snapshot', 'event_stream')) and payload['history']['complete'])
        return dict(profile=PROFILE, supported=True, source='engine_projection', missing=missing, gaps=gaps,
            capabilities=caps, training_ready=transport_ready,
            effect_coverage={k: contract()[k] for k in ('supported_effect_types', 'unsupported_effect_types')},
            training_profiles={'public-observation-v3': transport_ready,
                'semantic-complete-v3': transport_ready and not missing and not gaps and all(c['value'] == 'supported' for c in caps.values())},
            legal_frontier='current_select_option_only', full_simulation=False)

    def require_training(self, profile, history_memory=None):
        if profile not in ('public-observation-v3', 'semantic-complete-v3'): raise ValueError('public_input_v3_training_profile')
        ready = self.coverage().get('training_profiles', {}).get(profile, False)
        if not ready and profile == 'public-observation-v3' and history_memory is not None and self.payload() is not None:
            h = self.history()
            ready = (history_memory.complete and history_memory.cursor == h['cursor'] and
                     history_memory.identity == (h['stream'], h['match'], h['seat']) and
                     history_memory.snapshot == h['snapshot'] and
                     all(self.payload()['capabilities'][k]['status'] == 'known' and
                         self.payload()['capabilities'][k]['value'] == 'supported' for k in ('snapshot', 'event_stream')))
        if not ready: raise ValueError('public_input_v3_incomplete')
        return self

    def evaluate_attack(self, entity, attack_index, target):
        legacy = super().evaluate_attack(entity, attack_index, target)
        row = next((r for r in (self.payload() or {}).get('evaluations', [])
                    if (r['attacker'], r['attack_index'], r['target']) == (entity, attack_index, target)), None)
        if row:
            legacy.update(row, damage=row['damage_hp'], result_kind=row['kind'])
        return legacy

    def history_since(self, cursor):
        """Current zone snapshot plus the retained event suffix after a cursor.

        A suffix is not a complete prefix. Use PublicHistoryV3 to recover prefix
        completeness, and bind that memory explicitly when qualifying training.
        """
        history = self.history()
        if history is None: raise ValueError('public_input_v3_missing_history')
        if type(cursor) is not int or not 0 <= cursor <= history['cursor']:
            raise ValueError('public_input_v3_history_cursor')
        history['events'] = [e for e in history['events'] if e['seq'] > cursor]
        history['first_available'] = max(history['first_available'], cursor + 1)
        history['complete'] = history['complete'] and cursor == 0
        return history


class PublicHistoryV3:
    """Snapshot recovery is independent of complete historical knowledge."""
    def __init__(self):
        self.identity = None
        self.cursor = 0
        self.complete = True
        self.snapshot = []
        self.seen = {}

    def ingest(self, history):
        validate_history(history)
        identity = (history['stream'], history['match'], history['seat'])
        if self.identity is not None and identity != self.identity: raise ValueError('public_input_v3_stream_mismatch')
        seen = dict(self.seen)
        cursor = self.cursor
        gap = history['first_available'] > cursor + 1
        accepted = 0
        for event in history['events']:
            seq, fingerprint = event['seq'], digest(event)
            if seq <= cursor:
                if seen.get(str(seq)) != fingerprint: raise ValueError('public_input_v3_event_conflict')
                continue
            gap |= seq != cursor + 1
            seen[str(seq)] = fingerprint
            cursor = seq
            accepted += 1
        gap |= cursor < history['cursor']
        if history['cursor'] >= self.cursor:
            self.snapshot = copy.deepcopy(history['snapshot'])
        self.complete &= not gap and (history['complete'] or self.cursor > 0)
        self.identity, self.cursor, self.seen = identity, max(cursor, history['cursor']), seen
        return dict(accepted=accepted, gap=gap, history_complete=self.complete, snapshot_restored=True, cursor=self.cursor)

    def export(self):
        return json.loads(canonical(dict(version=3, identity=self.identity, cursor=self.cursor, complete=self.complete,
                                        snapshot=self.snapshot, seen=self.seen)))

    @classmethod
    def restore(cls, value):
        shape = obj({'version': {'type': 'integer', 'const': 3}, 'identity': nullable(array({'anyOf': [ID, SEAT]}, 3)),
            'cursor': NAT, 'complete': BOOL, 'snapshot': array(ZONE, 20), 'seen': obj({})})
        basic = copy.deepcopy(value)
        if type(basic) is not dict: raise ValueError('public_input_v3_memory_shape')
        seen = basic.get('seen')
        basic['seen'] = {}
        if schema_error(basic, shape) or type(seen) is not dict: raise ValueError('public_input_v3_memory_shape')
        identity = value['identity']
        if identity is not None and (len(identity) != 3 or type(identity[0]) is not str or type(identity[1]) is not str or type(identity[2]) is not int or identity[2] not in (0, 1)):
            raise ValueError('public_input_v3_memory_shape')
        for key, fingerprint in seen.items():
            if type(key) is not str or not key.isdecimal() or str(int(key)) != key or not 1 <= int(key) <= value['cursor'] or type(fingerprint) is not str or len(fingerprint) != 64 or any(c not in '0123456789ABCDEF' for c in fingerprint):
                raise ValueError('public_input_v3_memory_shape')
        if identity is None and (value['cursor'] or value['snapshot'] or seen):
            raise ValueError('public_input_v3_memory_shape')
        if value['complete'] and len(seen) != value['cursor']:
            raise ValueError('public_input_v3_memory_incomplete')
        obj_ = cls()
        obj_.identity = tuple(identity) if identity is not None else None
        obj_.cursor, obj_.complete = value['cursor'], value['complete']
        obj_.snapshot, obj_.seen = copy.deepcopy(value['snapshot']), dict(seen)
        if identity is not None:
            validate_history(dict(stream=identity[0],match=identity[1],seat=identity[2],cursor=value['cursor'],
                first_available=value['cursor']+1,complete=False,scope='public_boundaries_and_actions',events=[],
                snapshot=value['snapshot'],snapshot_cursor=value['cursor'],checkpoint=0))
        return obj_


def agent_observation(raw_observation, compiled_policy, **base_guards):
    """One validated observation -> only indexes from its immutable frontier."""
    return PublicInputV3.capture(raw_observation).decide(compiled_policy, **base_guards).selected_indexes
