"""Opt-in public semantics, layered over the unchanged v1 legal frontier.

The engine owns rules. This module validates, joins and queries engine receipts;
it never reconstructs ability quotas or damage from printed prose.
"""
from __future__ import annotations

from dataclasses import dataclass
import json

from .base_input import BaseInput, canonical, digest, _paths
from .public_decision_facts import obj, array, integer, BOOL, UID, schema_error

PROFILE = 'ptcg-public-input-v2'
SUPPORTED_EFFECT_TYPES = ['reduce_damage_next_turn', 'retreat_lock', 'ability_disabled',
                          'resolved_ability_disabled', 'resolved_tool_suppressed']
UNSUPPORTED_EFFECT_TYPES = ['general_damage_increase', 'damage_immunity', 'attack_effect_immunity',
    'attack_restrictions', 'evolution_restrictions', 'energy_supply_effect_instances',
    'attack_cost_effect_instances', 'retreat_cost_effect_instances', 'hp_effect_instances',
    'weakness_effects', 'resistance_effects', 'general_stadium_and_field_effect_instances']
SDK_GAPS = ['complete_event_source_not_implemented', 'effect_registry_partial',
            'complete_training_profile_not_qualified']
EVENT_TYPES = ('game_start game_end turn_start turn_end draw_card mulligan setup_place_active '
               'setup_place_bench setup_set_prizes play_pokemon evolve attach_energy play_trainer '
               'play_tool play_stadium use_stadium use_ability retreat attack coin_flip knockout '
               'take_prize send_out status_applied status_removed damage_dealt heal pokemon_check '
               'discard shuffle_deck public_reveal').split()
PHASES = ('setup mulligan setup_place draw main attack pokemon_check between_turns knockout_replace game_over').split()
STATUSES = ['known', 'unknown', 'not_applicable', 'unsupported', 'history_incomplete', 'unlimited']
TEXT = {'type': 'string', 'maxLength': 256}
ID = {'type': 'string', 'minLength': 1, 'maxLength': 128}
NAT = integer(1000000)
SEAT = integer(1)


def enum(*values):
    return {'type': 'string', 'enum': list(values)}


def nullable(schema):
    return {'anyOf': [schema, {'type': 'null'}]}


def tagged(schema, *, unlimited=False):
    return obj({'status': enum(*(STATUSES if unlimited else STATUSES[:-1])), 'value': nullable(schema), 'reason': TEXT, 'source': TEXT})


def fact(value=None, *, status='known', reason='', source='engine'):
    return dict(status=status, value=value, reason=reason, source=source)


def validate_fact(value, schema):
    if (schema_error(value, tagged(schema)) or
            (value['status'] == 'known') != (value['value'] is not None) or
            (value['status'] != 'known' and not value['reason'])):
        raise ValueError('public_input_v2_fact')


QUOTA = obj({
    'scope': tagged(enum('entity', 'player', 'named_group', 'stadium_effect')),
    'group': tagged(ID), 'reset': tagged(enum('turn', 'match')),
    'used': tagged(NAT), 'limit': tagged(NAT, unlimited=True), 'remaining': tagged(NAT, unlimited=True),
})
ABILITY = obj({
    'id': ID, 'entity': integer(minimum=1), 'player': SEAT, 'source_uid': UID,
    'index': integer(31), 'kind': tagged(enum('activated', 'passive', 'triggered')),
    'quota': QUOTA, 'disabled': tagged(BOOL),
    'main_availability': tagged(enum('offered', 'not_offered', 'conditional')),
})
PARAM = obj({'name': ID, 'unit': enum('hp', 'energy_units', 'count', 'boolean', 'rule'),
             'value': {'anyOf': [integer(minimum=-1000000), BOOL, TEXT]}})
EFFECT = obj({
    'id': ID, 'type': ID, 'target_entity': nullable(integer(minimum=1)),
    'target_player': nullable(SEAT), 'source_uid': tagged(UID),
    'parameters': array(PARAM), 'condition': TEXT, 'condition_met': tagged(BOOL),
    'starts_turn': tagged(NAT), 'expires_turn': tagged(NAT),
    'expiry_boundary': enum('after_turn_end', 'leave_active_or_after_turn_end', 'while_source_present', 'unknown'),
    'expiry_player': tagged(SEAT), 'combination': enum('additive', 'any', 'engine_resolved', 'unknown'),
    'rule': TEXT,
})
ENTITY = obj({
    'entity': integer(minimum=1), 'player': SEAT, 'zone': enum('active', 'bench'), 'source_uid': UID,
    'tools': tagged(array(UID)), 'evolution_stack': tagged(array(UID)),
    'printed_hp': tagged(NAT), 'effective_max_hp': tagged(NAT), 'damage_hp': tagged(NAT),
    'remaining_hp': tagged(NAT), 'poison_checkup_hp': tagged(NAT), 'burn_checkup_hp': tagged(NAT),
    'weakness': tagged(TEXT), 'resistance': tagged(TEXT),
})
EVENT = obj({
    'seq': integer(minimum=1), 'turn': NAT, 'player': nullable(SEAT), 'phase': integer(len(PHASES)-1),
    'type': enum(*EVENT_TYPES), 'visibility': enum('all', 'seat'), 'visible_to': nullable(SEAT),
    'count': tagged(NAT), 'cards': tagged(array(UID)),
    'knowledge': enum('invalidate_hidden_associations', 'public_reveal', 'snapshot_only'),
})
HISTORY = obj({
    'stream': ID, 'match': ID, 'seat': SEAT, 'cursor': NAT, 'first_available': integer(minimum=1),
    'complete': BOOL, 'scope': {'type': 'string', 'const': 'engine_logged_actions'},
    'events': array(EVENT, 128),
})
INTERACTION = obj({
    'action_id': tagged(ID), 'source_uid': tagged(UID), 'source_entity': tagged(integer(minimum=1)),
    'action_kind': tagged(enum('ability', 'trainer', 'stadium', 'play_stadium', 'attack', 'granted_attack')),
    'action_index': tagged(integer(31)), 'in_progress': tagged(BOOL),
    'stage': tagged(enum('main', 'payment', 'search', 'target', 'allocation', 'resolution')),
    'parent_committed': tagged(BOOL), 'cancel_allowed': tagged(BOOL),
    'cancel_semantics': tagged(enum('abort_before_commit', 'decline_optional', 'finish_partial')),
    **{key: tagged(integer(100)) for key in ('remaining_energy_cost', 'remaining_damage_counters',
                                             'max_assignments', 'max_assignments_per_target')},
    'allow_partial': tagged(BOOL),
    'checkpoint': NAT,
})
PAYLOAD_SCHEMA = obj({
    'version': {'type': 'integer', 'const': 2},
    'binding': obj({'window_id': ID, 'public_observation_hash': ID, 'sequence': NAT, 'seat': SEAT}),
    'abilities': array(ABILITY, 128),
    'quotas': array(obj({'id': ID, 'player': SEAT, 'quota': QUOTA}), 32),
    'effects': array(EFFECT, 256), 'entities': array(ENTITY, 18),
    'history': HISTORY, 'interaction': INTERACTION,
    'gaps': array(ID, 256),
})


def contract():
    return dict(profile=PROFILE, version=2, payload_schema=PAYLOAD_SCHEMA,
        states=STATUSES, units={'hp': 'damage points, not counters', 'count': 'nonnegative integer',
        'energy_units': 'engine effective supplied units', 'turn': 'global engine turn_number'},
        phase_codes={str(i): name for i, name in enumerate(PHASES)},
        identity_domains={'entity': 'current match public entity serial; never internal instance id',
        'source_uid': 'godot_local_card_uid_v1', 'ability': 'entity/source printing/ability index',
        'event': 'per-view public stream sequence; never card identity'},
        training_profiles={'public-state-complete-v2': 'no gaps or unknown/unsupported/history_incomplete facts; complete history'},
        visibility='payload is viewer-specific; opponent hidden card identities and hidden linkages forbidden',
        ephemeral_card_fields=['serial', 'card_serial', 'source_serial', 'target_serial', 'option_index_raw'],
        supported_effect_types=SUPPORTED_EFFECT_TYPES, unsupported_effect_types=UNSUPPORTED_EFFECT_TYPES,
        frontier='only current v1 frame options; quota/cost/evaluation is never authority',
        migration='opt-in companion payload; v1 frame, Base decisions and tensors unchanged')


def _model_public(value):
    """Keep public entity identities; quarantine card-instance bindings to v1.

    Reappearing hidden cards must not be linked by the legacy registry serial.
    Own visible printing multisets remain available, without physical-card IDs.
    """
    if isinstance(value, dict):
        return {k: _model_public(v) for k, v in value.items()
                if k not in {'serial', 'card_serial', 'source_serial', 'target_serial', 'option_index_raw', 'presence'}}
    if isinstance(value, list):
        return [_model_public(v) for v in value]
    return value


def _check_tags(value):
    if isinstance(value, dict):
        if set(value) == {'status', 'value', 'reason', 'source'}:
            if ((value['status'] == 'known') != (value['value'] is not None) or
                    (value['status'] != 'known' and not value['reason'])):
                raise ValueError('public_input_v2_fact')
        for child in value.values():
            _check_tags(child)
    elif isinstance(value, list):
        for child in value:
            _check_tags(child)


def _missing(value, path=''):
    result = []
    if isinstance(value, dict):
        if value.get('status') in ('unknown', 'unsupported', 'history_incomplete'):
            result.append(path)
        for key, child in value.items():
            result.extend(_missing(child, path + '/' + key))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            result.extend(_missing(child, path + '/' + str(i)))
    return result


def validate_history(history):
    if schema_error(history, HISTORY):
        raise ValueError('public_input_v2_history_shape')
    _check_tags(history)
    seqs = [e['seq'] for e in history['events']]
    if (seqs != sorted(set(seqs)) or any(s < history['first_available'] or s > history['cursor'] for s in seqs)
            or history['first_available'] > history['cursor'] + 1):
        raise ValueError('public_input_v2_history_sequence')
    for event in history['events']:
        if ((event['visibility'] == 'all' and event['visible_to'] is not None) or
                (event['visibility'] == 'seat' and event['visible_to'] != history['seat'])):
            raise ValueError('public_input_v2_visibility')
        if event['type'] in ('draw_card', 'take_prize') and event['player'] != history['seat']:
            if event['cards']['status'] == 'known':
                raise ValueError('public_input_v2_hidden_cards')


def validate_payload(frame, payload):
    if schema_error(payload, PAYLOAD_SCHEMA):
        raise ValueError('public_input_v2_shape')
    _check_tags(payload)
    if payload['binding'] != dict(frame['source'], sequence=frame['sequence'], seat=frame['seat']):
        raise ValueError('public_input_v2_binding')
    board = {s['entity_serial']: (s, p, z) for p in ('self', 'opponent') for z in ('active', 'bench')
             for s in frame['public_state'][p][z] if 'entity_serial' in s}
    seen = set()
    for row in payload['entities']:
        identity = row['entity']
        if identity in seen or identity not in board:
            raise ValueError('public_input_v2_entity')
        slot, side, zone = board[identity]
        if row['source_uid'] != slot['local_card_uid'] or row['zone'] != zone or row['player'] != (frame['seat'] if side == 'self' else 1-frame['seat']):
            raise ValueError('public_input_v2_entity')
        seen.add(identity)
    if seen != set(board):
        raise ValueError('public_input_v2_entity')
    for section in ('abilities', 'quotas', 'effects'):
        if len({r['id'] for r in payload[section]}) != len(payload[section]):
            raise ValueError('public_input_v2_duplicate_identity')
    for row in payload['abilities']:
        if row['entity'] not in board:
            raise ValueError('public_input_v2_ability_entity')
        if row['player'] != (frame['seat'] if board[row['entity']][1] == 'self' else 1-frame['seat']):
            raise ValueError('public_input_v2_ability_entity')
        slot = board[row['entity']][0]
        tools = next(e['tools'] for e in payload['entities'] if e['entity'] == row['entity'])
        sources = [slot['local_card_uid']] + (tools['value'] if tools['status'] == 'known' else [])
        if (row['source_uid'] not in sources or
                row['id'] != f"{row['entity']}/{row['source_uid']}/ability/{row['index']}"):
            raise ValueError('public_input_v2_ability_source')
        # Opponent availability must not query hidden hand/deck prerequisites.
        if row['player'] != frame['seat'] and row['main_availability']['status'] == 'known':
            raise ValueError('public_input_v2_opponent_availability')
        if frame['select_semantics']['select_type_raw'] != 0 and row['main_availability']['status'] == 'known':
            raise ValueError('public_input_v2_nonmain_availability')
        availability = row['main_availability']
        if availability['status'] == 'known' and availability['value'] in ('offered', 'not_offered'):
            offered = any(o['kind'] == 'ability' and o.get('source_entity_serial') == row['entity']
                          and o.get('ability_index') == row['index'] for o in frame['options'])
            if offered != (availability['value'] == 'offered'):
                raise ValueError('public_input_v2_availability_frontier')
    for row in payload['abilities'] + payload['quotas']:
        q = row['quota']
        if all(q[k]['status'] == 'known' for k in ('used', 'limit', 'remaining')):
            if q['remaining']['value'] != max(0, q['limit']['value'] - q['used']['value']):
                raise ValueError('public_input_v2_quota_arithmetic')
    if payload['history']['seat'] != frame['seat']:
        raise ValueError('public_input_v2_visibility')
    validate_history(payload['history'])


@dataclass(frozen=True, slots=True)
class PublicInputV2:
    base: BaseInput
    _payload: bytes | None

    @classmethod
    def capture(cls, frame, supplement=None):
        base = BaseInput.capture(frame)
        if supplement is not None:
            validate_payload(base.frame(), supplement)
        return cls(base, canonical(supplement) if supplement is not None else None)

    def payload(self):
        return json.loads(self._payload) if self._payload is not None else None

    def document(self):
        payload = self.payload()
        if payload is not None:
            payload.pop('binding')  # Binding is audit metadata, never a learned card identity.
            payload['interaction'].pop('checkpoint')
        base = _model_public(self.base.model_document())
        base['options'].sort(key=canonical)
        # Card ordering inside the owner's hand is not persistent identity.
        base['public_state']['self']['hand'].sort(key=canonical)
        base['presence'] = _paths(base)
        return dict(profile=PROFILE, base=base,
                    semantics=fact(payload) if payload is not None else
                    fact(status='unsupported', reason='legacy_data_missing_semantics', source='migration'))

    @property
    def input_sha256(self):
        return digest(self.document())

    def coverage(self):
        payload = self.payload()
        missing = _missing(self.document()['semantics'])
        gaps = sorted(set((payload['gaps'] if payload is not None else ['legacy_data_missing_semantics']) + SDK_GAPS))
        history_ok = payload is not None and payload['history']['complete']
        return dict(profile=PROFILE, supported=payload is not None, missing=missing, gaps=gaps,
                    training_ready=self.base.coverage()['ready'] and not missing and not gaps and history_ok,
                    source='engine_projection' if payload else 'legacy_data',
                    full_simulation=False, legal_frontier='current_select_option_only',
                    capabilities=dict(ability_quota_coverage='per_row' if payload else 'legacy_missing',
                        effective_hp='engine' if payload else 'source_missing',
                        event_history='engine_logged_actions_only' if payload else 'legacy_missing',
                        interaction='reviewed_headless_pending_actions_only' if payload else 'legacy_missing',
                        arbitrary_attack_damage='unsupported',
                        supported_effect_types=list(SUPPORTED_EFFECT_TYPES) if payload else [],
                        unsupported_effect_types=list(UNSUPPORTED_EFFECT_TYPES)))

    def require_training(self, profile):
        if profile != 'public-state-complete-v2':
            raise ValueError('public_input_v2_training_profile')
        if not self.coverage()['training_ready']:
            raise ValueError('public_input_v2_incomplete')
        return self

    def abilities(self, entity=None):
        payload = self.payload()
        return None if payload is None else [r for r in payload['abilities'] if entity is None or r['entity'] == entity]

    def effects(self, entity=None):
        payload = self.payload()
        return None if payload is None else [r for r in payload['effects'] if entity is None or r['target_entity'] in (None, entity)]

    def quotas(self, player=None):
        payload = self.payload()
        return None if payload is None else [r for r in payload['quotas'] if player is None or r['player'] == player]

    def entities(self, entity=None):
        payload = self.payload()
        return None if payload is None else [r for r in payload['entities'] if entity is None or r['entity'] == entity]

    def interaction(self):
        payload = self.payload()
        return None if payload is None else payload['interaction']

    def history(self):
        payload = self.payload()
        return None if payload is None else payload['history']

    def evaluate_attack(self, entity, attack_index, target):
        """Cost-only receipt from engine; no hypothetical state transitions."""
        frame = self.base.frame()
        rows = frame['public_state'].get('decision', {}).get('entities', [])
        attacker = next((r for r in rows if r['entity_serial'] == entity), None)
        attack = next((r for r in attacker['attacks'] if r['attack_index'] == attack_index), None) if attacker else None
        if attacker is None or attack is None or not any(r['entity_serial'] == target for r in rows):
            raise ValueError('public_input_v2_attack_identity')
        return dict(binding=self.base.binding, input_sha256=self.input_sha256,
                    attacker=entity, attack_index=attack_index, target=target,
                    cost_candidates=fact(attack['cost_candidates'], source='engine_effective_cost'),
                    cost_satisfied=fact(attack['energy_ready'], source='engine_energy_debt'),
                    damage=fact(status='unsupported', reason='arbitrary_target_damage_not_qualified'),
                    result_kind='unknown', unresolved=['target_modifiers', 'randomness', 'payment', 'followup'],
                    legal_authority=False, simulation_supported=False)

    def decide(self, policy, **base_guards):
        """Reuse the existing Base adjudicator; enriched state grants no authority."""
        from .competitive_policy_v2 import CompetitivePolicyV2Runtime
        return CompetitivePolicyV2Runtime.decide(policy, self.base.frame(), **base_guards)


class PublicEventMemory:
    """Per-view cursor/deduplication. Persist state via export()/restore().

    Card knowledge is deliberately conservative: reveal events establish facts
    at their cursor only. Any hidden movement or gap invalidates associations.
    """
    def __init__(self):
        self.stream = None
        self.match = None
        self.seat = None
        self.cursor = 0
        self.complete = True
        self._seen = {}
        self.reveals = []

    def ingest(self, history):
        validate_history(history)
        identity = (history['stream'], history['match'], history['seat'])
        if self.stream is not None and identity != (self.stream, self.match, self.seat):
            raise ValueError('public_input_v2_stream_mismatch')
        # Transactional update: conflicting duplicates cannot partly mutate memory.
        restored = self.export()
        try:
            prefix_known = self.complete and self.cursor > 0
            self.stream, self.match, self.seat = identity
            gap = history['first_available'] > self.cursor + 1
            accepted = 0
            for event in history['events']:
                seq, fingerprint = event['seq'], digest(event)
                if seq <= self.cursor:
                    if str(seq) not in self._seen or self._seen[str(seq)] != fingerprint:
                        raise ValueError('public_input_v2_event_conflict')
                    continue
                gap |= seq != self.cursor + 1
                if gap or event['knowledge'] == 'invalidate_hidden_associations':
                    self.reveals = []
                if event['knowledge'] == 'public_reveal' and event['cards']['status'] == 'known':
                    self.reveals.append(dict(seq=seq, player=event['player'], cards=event['cards']['value']))
                self._seen[str(seq)] = fingerprint
                self.cursor = seq
                accepted += 1
            gap |= self.cursor < history['cursor']
            if gap:
                self.reveals = []
            self.complete &= (history['complete'] or prefix_known) and not gap
            return dict(accepted=accepted, gap=gap, complete=self.complete, cursor=self.cursor)
        except Exception:
            self._load(restored)
            raise

    def export(self):
        return json.loads(canonical(dict(version=2, stream=self.stream, match=self.match, seat=self.seat,
            cursor=self.cursor, complete=self.complete, seen=self._seen, reveals=self.reveals)))

    def _load(self, value):
        self.stream, self.match, self.seat = value['stream'], value['match'], value['seat']
        self.cursor, self.complete = value['cursor'], value['complete']
        self._seen, self.reveals = value['seen'], value['reveals']

    @classmethod
    def restore(cls, value):
        schema = obj({'version': {'type': 'integer', 'const': 2}, 'stream': nullable(ID), 'match': nullable(ID),
                      'seat': nullable(SEAT), 'cursor': NAT, 'complete': BOOL, 'seen': obj({}), 'reveals': array(TEXT)})
        # Dynamic seq hashes are checked independently; they never contain card IDs.
        basic = dict(value) if type(value) is dict else {}
        basic['seen'], basic['reveals'] = {}, []
        if schema_error(basic, schema) or type(value.get('seen')) is not dict or type(value.get('reveals')) is not list:
            raise ValueError('public_input_v2_memory_shape')
        for seq, fingerprint in value['seen'].items():
            if type(seq) is not str or not seq.isdecimal() or not 1 <= int(seq) <= value['cursor'] or type(fingerprint) is not str or len(fingerprint) != 64 or any(c not in '0123456789ABCDEF' for c in fingerprint):
                raise ValueError('public_input_v2_memory_shape')
        reveal_schema = obj({'seq': integer(minimum=1), 'player': nullable(SEAT), 'cards': array(UID)})
        if any(schema_error(r, reveal_schema) or r['seq'] > value['cursor'] for r in value['reveals']):
            raise ValueError('public_input_v2_memory_shape')
        result = cls()
        result._load(json.loads(canonical(value)))
        return result
