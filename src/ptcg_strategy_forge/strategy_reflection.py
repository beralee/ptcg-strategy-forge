"""Read-only, seat-scoped reflection over integrity-checked decision recordings.

Detectors identify review opportunities. They never infer a winning alternative,
create teacher labels, or use the other seat's private perspective as evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .native_trace import read_native_trace, _trace_frame_error
from .strategy_base import document_sha256


ISSUES = {
    'projected_finish_not_taken': dict(priority=1, layer='adapter_or_damage_projection',
        hypothesis='A current projected knockout may finish the prize schedule.',
        experiment='Verify damage and prize yield, Base authority and response; pair the last-prize threshold.'),
    'zero_damage_attack_with_bench': dict(priority=1, layer='adapter_or_damage_projection',
        hypothesis='Zero active damage may conceal useful bench counters or another attack effect.',
        experiment='Inspect exact attack and protection effects; test bench present/absent, immunity and source UID.'),
    'end_turn_with_legal_attack': dict(priority=2, layer='adapter',
        hypothesis='Ending with a published attack may lose an attack window.',
        experiment='Review attack costs, drawbacks, lock value, retaliation and Base authority before changing preference.'),
    'ready_bench_stranded': dict(priority=2, layer='route_or_payment',
        hypothesis='A ready bench attacker may be stranded behind an unready active.',
        experiment='Prove exact payment and a legal pivot; test spent tokens, target loss and same-name entities.'),
    'low_library_optional_action': dict(priority=3, layer='draw_or_recovery',
        hypothesis='An optional trainer or ability with a nearly empty library needs exhaustion review.',
        experiment='Inspect the exact effect; pair library thresholds and any verified immediate finish.'),
}


class _Review:
    def __init__(self):
        self.windows = 0
        self.unwitnessed = 0
        self.issues = {}
        self.first_attack_turns = {}

    def add(self, decision, *, trace_sha256, seat, witnessed):
        frame, host = decision['frame'], decision['host']
        if frame['seat'] != seat:
            return
        if host.get('status') != 'accepted' or host.get('fallback_used') or host.get('error_code'):
            raise ValueError('reflection_unqualified_host')
        self.windows += 1
        self.unwitnessed += not witnessed
        options = frame['options']
        selected = [options[i] for i in host['accepted_indexes']]
        if frame['prompt_kind'] != 'main':
            return
        own, opponent = frame['public_state']['self'], frame['public_state']['opponent']
        attacks = [o for o in options if o['kind'] == 'attack']
        ended = any(o['kind'] == 'end_turn' for o in selected)
        attacked = any(o['kind'] == 'attack' for o in selected)
        turn = frame['public_state']['turn_number']
        if attacked:
            self.first_attack_turns.setdefault(trace_sha256, turn)
        codes = []
        if ended and attacks:
            codes.append('end_turn_with_legal_attack')
            if opponent['bench'] and any(o['projected_damage'] == 0 for o in attacks):
                codes.append('zero_damage_attack_with_bench')
        if ended and own['active'] and not any(s['attack_ready'] is True for s in own['active']) and any(s['attack_ready'] is True for s in own['bench']):
            codes.append('ready_bench_stranded')
        if ended and any(o['projected_knockout'] is True and type(o['target_prize_value']) is int
                         and 0 < own['prizes_remaining'] <= o['target_prize_value'] for o in attacks):
            codes.append('projected_finish_not_taken')
        if own['deck_count'] <= 1 and any(o['kind'] in {'use_ability','play_trainer'} for o in selected):
            codes.append('low_library_optional_action')
        for code in codes:
            issue = self.issues.setdefault(code, dict(code=code, status='hypothesis', **ISSUES[code],
                occurrences=0, locations=[], required_gates=['public_proof','red_scenario','semantic_reorder',
                    'negative_gates','fresh_window_chain','workspace_check','paired_engine_evaluation']))
            issue['occurrences'] += 1
            # Bounded, no raw frame/hand/policy strings in the published report.
            if len(issue['locations']) < 50:
                issue['locations'].append(dict(trace_sha256=trace_sha256, decision_id=decision['decision_id'],
                    seat=seat, turn=turn, sequence=frame['sequence'], window_id=frame['source']['window_id'],
                    engine_commit_witnessed=witnessed, selected_indexes=list(host['accepted_indexes'])))

    def report(self, sources):
        if not self.windows:
            raise ValueError('reflection_no_qualified_windows')
        return dict(document_type='forge_strategy_reflection_v1',schema_version=1,status='review_required',
            sources=sources,reviewed_windows=self.windows,individual_commit_unwitnessed=self.unwitnessed,
            first_attack_turns=self.first_attack_turns,
            issues=sorted(self.issues.values(),key=lambda row:(row['priority'],-row['occurrences'],row['code'])),
            claims=dict(public_only=True,source_authenticated=False,alternative_executed=False,
                        causal_win_gain=False,training_labels_created=False,production_authority=False))


def reflect_native(directory, *, seat):
    if type(seat) is not int or seat not in (0,1):
        raise ValueError('reflection_seat_invalid')
    verified = read_native_trace(directory)
    if verified['dirty']:
        raise ValueError('reflection_dirty_trace')
    review = _Review()
    for decision in verified['decisions']:
        review.add(decision,trace_sha256=verified['trace_sha256'],seat=seat,
                   witnessed=decision['engine_commit_witnessed'])
    return review.report([dict(format='native',trace_sha256=verified['trace_sha256'],seat=seat,
        manifest_sha256=hashlib.sha256((Path(directory)/'developer_decision_trace_manifest.json').read_bytes()).hexdigest())])


def reflect_bench(report_path, *, expected_candidate_sha256, game_indexes=None):
    """Verify the recorded bench audit, hash chain and each scoped window first.

    At most 32 explicitly selected games, 128 MiB per trace. Current checked-in
    frame compatibility is used; never import executable code from replay input.
    """
    from tools.local_engine_bench import audit_game, verify_trace, verify_window

    if type(expected_candidate_sha256) is not str or not re.fullmatch('[0-9A-Fa-f]{64}',expected_candidate_sha256):
        raise ValueError('reflection_package_identity_required')
    expected_candidate_sha256 = expected_candidate_sha256.upper()
    report_path = Path(report_path)
    if report_path.is_symlink() or report_path.stat().st_size > 4*1024**2:
        raise ValueError('reflection_input_budget_invalid')
    raw = report_path.read_bytes()
    report = json.loads(raw)
    if report.get('clean') is not True or report.get('errors'):
        raise ValueError('reflection_dirty_bench')
    games = report.get('games')
    if type(games) is not list:
        raise ValueError('reflection_games_invalid')
    indexes = list(range(len(games))) if game_indexes is None else game_indexes
    if (type(indexes) is not list or not 1 <= len(indexes) <= 32
            or any(type(i) is not int or not 0 <= i < len(games) for i in indexes)
            or len(set(indexes)) != len(indexes)):
        raise ValueError('reflection_game_selection_invalid')
    review, sources = _Review(), []
    root = report_path.parent.resolve()
    for index in indexes:
        game = games[index]
        if game.get('candidate_sha256') != expected_candidate_sha256 or audit_game(game,expected_candidate_sha256,game.get('opponent_sha256')):
            raise ValueError('reflection_game_unqualified')
        name = game.get('trace_path')
        if type(name) is not str or '\\' in name or ':' in name or any(p in ('.','..','') for p in name.split('/')):
            raise ValueError('reflection_trace_path_invalid')
        path = root / name
        if not path.resolve().is_relative_to(root) or path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root and root in p.parents):
            raise ValueError('reflection_trace_path_invalid')
        if path.stat().st_size > 128*1024**2:
            raise ValueError('reflection_input_budget_invalid')
        # Legacy Godot JSON encodes integral seat values as floats.
        seat = game['candidate_seat']
        if type(seat) not in (int,float) or seat not in (0,1):
            raise ValueError('reflection_seat_invalid')
        seat = int(seat)
        if not verify_trace(path,game,validator=_trace_frame_error):
            raise ValueError('reflection_trace_verification_failed')
        trace_sha = game['trace_file_sha256']
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                decision = json.loads(json.loads(line)['payload'])['decision']
                if decision['frame']['seat'] != seat:
                    continue
                verified = verify_window(decision,_trace_frame_error)
                # Bench verifies accepted calls and whole-game commits; there is
                # no one-to-one owner-step witness for every policy invocation.
                review.add(verified,trace_sha256=trace_sha,seat=seat,witnessed=False)
        if hashlib.sha256(path.read_bytes()).hexdigest().upper() != trace_sha:
            raise ValueError('reflection_trace_changed')
        sources.append(dict(format='bench',report_sha256=hashlib.sha256(raw).hexdigest(),
            game_index=index,seed=game['seed'],seat=seat,candidate_sha256=expected_candidate_sha256,
            opponent_sha256=game['opponent_sha256'],trace_sha256=trace_sha,
            recorded_game_clean=True,individual_commits_proven=False))
    return review.report(sources)
