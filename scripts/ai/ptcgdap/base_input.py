"""Base-owned, lossless public input. Training and inference share this boundary.

Version 1 preserves every admitted public field. Binding/sequence are audit
metadata, not model features. Unknown information is never synthesized.
This is a structured observation contract, not an ORT tensor profile.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path

PROFILE = 'ptcg-base-input-v1'
PLAN_KEYS = {'goal_id','target_entity','turn','phase','method_id'}
PRINTED_KEYS = ('card_type', 'stage', 'hp', 'energy_type', 'energy_provides',
                'evolves_from', 'weakness_energy', 'weakness_value',
                'resistance_energy', 'resistance_value', 'retreat_cost',
                'mechanic', 'ancient_trait', 'abilities', 'attacks', 'description')
LIMITATIONS = ('ability_marker_is_not_per_ability_quota',
               'arbitrary_dynamic_effects_not_fully_projected',
               'cost_ready_is_not_legal_action',
               'unknown_deck_and_prize_identities_not_observed')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest().upper()


@lru_cache(maxsize=1)
def contract_bytes():
    from . import competitive_policy_v2 as c
    from .public_decision_facts import DECISION_SCHEMA
    return canonical(dict(profile=PROFILE, version=1,
        frame_required=sorted(c.FRAME_KEYS), state_required=sorted(c.STATE_KEYS),
        self_required=sorted(c.SELF_REQUIRED_KEYS), self_allowed=sorted(c.SELF_KEYS),
        opponent_required=sorted(c.OPPONENT_KEYS), slot_required=sorted(c.SLOT_REQUIRED_KEYS),
        slot_allowed=sorted(c.SLOT_KEYS), option_required=sorted(c.OPTION_REQUIRED_KEYS),
        option_allowed=sorted(c.OPTION_KEYS), turn_required=sorted(c.TURN_LEDGER_KEYS),
        decision_schema=DECISION_SCHEMA, printed_keys=list(PRINTED_KEYS),
        optional_representation='omitted with explicit presence paths; null remains null',
        option_order='canonical semantic record without current index; duplicates retained',
        identity_domain='godot_local_card_uid_v1', plan_keys=sorted(PLAN_KEYS),
        plan_unknown=None, action_mask='Base-issued current frontier in canonical option row order',
        limitations=list(LIMITATIONS)))


def contract_hash():
    return hashlib.sha256(contract_bytes()).hexdigest().upper()


def _paths(value, path=''):
    out = [path]
    if isinstance(value, dict):
        for key in sorted(value):
            out.extend(_paths(value[key], path + '/' + key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            out.extend(_paths(child, path + '/' + str(index)))
    return out


def _printed(uid, root):
    path = Path(root) / (uid + '.json')
    if not path.is_file() or path.is_symlink():
        return canonical(dict(card_uid=uid, known=False, source_sha256=None, facts=None))
    raw = path.read_bytes()
    return _decode_printed(uid, raw)


@lru_cache(maxsize=4096)
def _decode_printed(uid, raw):
    card = json.loads(raw)
    if str(card.get('set_code')) + '_' + str(card.get('card_index')) != uid:
        raise ValueError('base_input_card_identity')
    return canonical(dict(card_uid=uid, known=True,
        source_sha256=hashlib.sha256(raw).hexdigest().upper(),
        facts={key: card[key] for key in PRINTED_KEYS if key in card}))


def _uids(value):
    out = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key.endswith('_uid') and isinstance(child, str):
                out.add(child)
            elif key.endswith('_uids') and isinstance(child, list):
                out.update(v for v in child if isinstance(v, str))
            else:
                out.update(_uids(child))
    elif isinstance(value, list):
        for child in value:
            out.update(_uids(child))
    return out


@dataclass(frozen=True, slots=True)
class BaseInput:
    _frame_bytes: bytes
    _model_bytes: bytes
    _coverage_bytes: bytes
    option_indexes: tuple[int, ...]

    @classmethod
    def capture(cls, frame, *, plan=None):
        from .competitive_policy_v2 import _frame_error, SLOT_KEYS
        error = _frame_error(frame)
        if error:
            raise ValueError(error)
        if plan is not None:
            if (type(plan) is not dict or set(plan)-PLAN_KEYS
                    or any(type(v) not in (str,int,type(None)) for v in plan.values())
                    or ('turn' in plan and type(plan['turn']) is not int)
                    or ('target_entity' in plan and type(plan['target_entity']) not in (int,type(None)))):
                raise ValueError('base_input_plan_invalid')
        raw = canonical(frame)
        frame = json.loads(raw)
        state = frame['public_state']
        missing = []
        if 'decision' not in state:
            missing.append('/public_state/decision')
        if 'turn' not in state['self']:
            missing.append('/public_state/self/turn')
        for side in ('self', 'opponent'):
            for zone in ('active', 'bench'):
                for index, slot in enumerate(state[side][zone]):
                    for key in sorted(SLOT_KEYS - set(slot)):
                        missing.append(f'/public_state/{side}/{zone}/{index}/{key}')
        # Card knowledge is public immutable metadata, never engine state.
        root = str(Path(__file__).resolve().parents[3] / 'data/bundled_user/cards')
        cards = [json.loads(_printed(uid, root)) for uid in sorted(_uids(frame))]
        unknown = [row['card_uid'] for row in cards if not row['known']]
        options = [(canonical({k:v for k,v in o.items() if k != 'index'}), o['index'])
                   for o in frame['options']]
        options.sort(key=lambda row: (row[0], row[1]))
        model = dict(profile=PROFILE, contract_sha256=contract_hash(), seat=frame['seat'],
            prompt_kind=frame['prompt_kind'], public_state=state,
            select_semantics=frame['select_semantics'],
            options=[json.loads(row[0]) for row in options], printed_cards=cards, plan=plan)
        model['presence'] = _paths(model)
        coverage = dict(profile=PROFILE, contract_sha256=contract_hash(),
            ready=not missing and not unknown, missing=missing, unknown_card_uids=unknown,
            scope='all admitted fields and printed card metadata; not complete game semantics',
            limitations=list(LIMITATIONS))
        return cls(raw, canonical(model), canonical(coverage), tuple(row[1] for row in options))

    def frame(self):
        return json.loads(self._frame_bytes)

    def model_document(self):
        return json.loads(self._model_bytes)

    def actor_document(self, frontier):
        """Bind a Base-issued frontier; scores/teacher labels never enter input."""
        frame=self.frame()
        if (type(frontier) is not dict or frontier.get('profile_id')!='ptcgdap-base-model-frontier-v1'
                or type(frontier.get('enabled')) is not bool
                or any(frontier.get(k)!=frame['source'][k] for k in ('window_id','public_observation_hash'))
                or type(frontier.get('indexes')) is not list
                or len(set(frontier['indexes']))!=len(frontier['indexes'])
                or any(type(i) is not int or i not in self.option_indexes for i in frontier['indexes'])):
            raise ValueError('base_input_frontier_binding')
        model=self.model_document()
        model['action_mask']=[int(frontier['enabled'] and i in frontier['indexes']) for i in self.option_indexes]
        model.pop('presence')
        model['presence']=_paths(model)
        return model

    def coverage(self):
        return json.loads(self._coverage_bytes)

    def require_learning_ready(self):
        if not self.coverage()['ready']:
            raise ValueError('base_input_incomplete')
        return self

    @property
    def input_sha256(self):
        return hashlib.sha256(self._model_bytes).hexdigest().upper()

    @property
    def binding(self):
        frame = self.frame()
        return dict(frame['source'], sequence=frame['sequence'], seat=frame['seat'])
