"""Public-window decision chains; fixture suffixes are never engine transitions."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from scripts.ai.ptcgdap.author_strategy_package import AuthorStrategyPackageLoader
from scripts.ai.ptcgdap.cabt_tree_hash import public_observation_hash
from scripts.ai.ptcgdap.competitive_policy_v2 import CompetitivePolicyV2Compiler, CompetitivePolicyV2Runtime
from scripts.ai.ptcgdap.public_damage_planning import SemanticTransactionJournal
from .scenarios import COMPETITIVE_SCENARIO_KEYS, BASE_AUTHORITY_KEYS, is_competitive_scenario

IDENTIFIER = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}$')


def _bindings(frame):
    observation = {k:frame[k] for k in ('schema_version','sequence','seat','prompt_kind','public_state')}
    observation_hash = public_observation_hash(observation)
    window_hash = public_observation_hash(dict(public_observation_hash=observation_hash,
                                              select_semantics=frame['select_semantics'], options=frame['options']))
    return dict(public_observation_hash=observation_hash, window_id=window_hash)


def bind_frame(frame):
    """Author a fixture's canonical bindings. Execution never repairs input drift."""
    frame['source'] = _bindings(frame)


def load_steps(root, specs):
    root = Path(root).resolve(); result = []; seen = set()
    if type(specs) is not list or not 1 <= len(specs) <= 64:
        raise ValueError('decision_bench_steps_invalid')
    for spec in specs:
        if type(spec) is not dict or set(spec) != {'path','expect_error'} or type(spec['expect_error']) is not str:
            raise ValueError('decision_bench_step_invalid')
        name = spec['path']
        if type(name) is not str or '\\' in name or ':' in name:
            raise ValueError('decision_bench_path_invalid')
        relative = PurePosixPath(name)
        if relative.is_absolute() or any(p in ('..','.') for p in name.split('/')):
            raise ValueError('decision_bench_path_invalid')
        path = root.joinpath(*relative.parts)
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root and root in p.parents):
            raise ValueError('decision_bench_path_invalid')
        if not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError('decision_bench_path_invalid')
        if path.resolve() in seen:
            raise ValueError('decision_bench_duplicate_step')
        seen.add(path.resolve())
        raw = path.read_bytes()
        scenario = json.loads(raw)
        if (type(scenario) is not dict or set(scenario) != COMPETITIVE_SCENARIO_KEYS
                or not is_competitive_scenario(scenario) or set(scenario.get('base_authority',{})) != BASE_AUTHORITY_KEYS):
            raise ValueError('decision_bench_scenario_invalid')
        result.append(dict(scenario=scenario, expect_error=spec['expect_error'],
                           source_sha256=hashlib.sha256(raw).hexdigest().upper()))
    return result


def run_chain(policy, steps, *, reverse=False, package_identity='local-fixture'):
    records = []; seen = set(); previous_sequence = -1; seat = None; journal = None
    error = ''
    for step in steps:
        scenario = copy.deepcopy(step['scenario']); frame = scenario['frame']
        try:
            if frame['source'] != _bindings(frame):
                error = 'decision_chain_binding_mismatch'; break
            window = frame['source']['window_id']; sequence = frame['sequence']
            if window in seen or type(sequence) is not int or sequence <= previous_sequence:
                error = 'decision_chain_stale_window'; break
            if seat is not None and frame['seat'] != seat:
                error = 'decision_chain_seat_changed'; break
            seen.add(window); previous_sequence = sequence; seat = frame['seat']
            if journal is None:
                journal = SemanticTransactionJournal('complex-chain', seat, package_identity)
            expected = scenario['expected_selected_indexes']; authority = scenario['base_authority']
            if reverse:
                n = len(frame['options']); frame['options'].reverse()
                for i, option in enumerate(frame['options']):option['index'] = i
                expected = [n-1-i for i in expected]
                for key in ('mandatory_indexes','terminal_indexes','base_vetoed_indexes'):
                    authority[key] = [n-1-i for i in authority[key]]
                for row in authority['base_hard_tiers']:row['index'] = n-1-row['index']
                bind_frame(frame)
            decision = CompetitivePolicyV2Runtime.decide(policy, frame, transaction_journal=journal, **authority)
            observed_error = decision.error_code if not decision.accepted else ''
            passed = (observed_error == step['expect_error'] and
                      (bool(observed_error) or list(decision.selected_indexes) == expected))
            record = dict(scenario_id=scenario['scenario_id'], sequence=sequence,
                          window_id=frame['source']['window_id'], selected_indexes=list(decision.selected_indexes),
                          expected_indexes=expected, error_code=observed_error, passed=passed,
                          owner_layer=decision.audit.get('owner_layer','') if decision.accepted else '',
                          audit_hash=decision.audit.get('audit_hash','') if decision.accepted else '',
                          source_sha256=step.get('source_sha256',''))
            records.append(record)
            if not passed:
                error = 'decision_chain_expectation_failed'; break
            if observed_error and len(records) != len(steps):
                error = 'decision_chain_suffix_after_rejection'; break
        except (KeyError, TypeError, ValueError, IndexError):
            error = 'decision_chain_frame_invalid'; break
    return dict(passed=not error and bool(records) and len(records)==len(steps), error_code=error,
                variant='reversed' if reverse else 'original', steps=records,
                planned_steps=len(steps), executed_steps=len(records), engine_execution=False)


def run_bench(package_path, suite_path):
    package = AuthorStrategyPackageLoader().load_path(Path(package_path))
    deck = json.loads(package.payload_bytes('deck/deck_manifest.json'))
    adapter = json.loads(package.payload_bytes('policy/adapter.json'))
    compiled = CompetitivePolicyV2Compiler.compile_local_uid(adapter, allowed_card_uids={r['local_card_uid'] for r in deck['cards']})
    if not compiled.accepted:raise ValueError(compiled.error_code)
    suite_path = Path(suite_path); suite_raw = suite_path.read_bytes(); suite = json.loads(suite_raw)
    if (type(suite) is not dict or set(suite) != {'document_type','schema_version','cases'}
            or suite['document_type'] != 'forge_complex_decision_bench_v1' or suite['schema_version'] != 1
            or type(suite['cases']) is not list or not 1 <= len(suite['cases']) <= 5000):
        raise ValueError('decision_bench_suite_invalid')
    seen = set(); rows = []; families = {}; fixture_manifest = {}
    for case in suite['cases']:
        if (type(case) is not dict or set(case) != {'id','family','steps'}
                or not IDENTIFIER.fullmatch(str(case['id'])) or not IDENTIFIER.fullmatch(str(case['family']))
                or case['id'] in seen):raise ValueError('decision_bench_case_invalid')
        seen.add(case['id']); steps = load_steps(suite_path.parent, case['steps'])
        for spec, step in zip(case['steps'], steps):
            name = spec['path']; digest = step['source_sha256']
            if name in fixture_manifest and fixture_manifest[name] != digest:
                raise ValueError('decision_bench_fixture_changed')
            fixture_manifest[name] = digest
        for reverse in (False,True):
            result = run_chain(compiled.policy, steps, reverse=reverse, package_identity=package.archive_sha256)
            result.update(case_id=case['id'], family=case['family']); rows.append(result)
            family = families.setdefault(case['family'], dict(total=0, passed=0))
            family['total'] += 1; family['passed'] += int(result['passed'])
    return dict(document_type='forge_complex_decision_bench_report_v1', package_sha256=package.archive_sha256,
                suite_sha256=hashlib.sha256(suite_raw).hexdigest().upper(),
                fixture_manifest=fixture_manifest,
                fixture_manifest_sha256=hashlib.sha256(json.dumps(fixture_manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest().upper(),
                passed=all(r['passed'] for r in rows), cases=len(seen), variants=len(rows),
                passed_variants=sum(r['passed'] for r in rows),
                chain_variants=sum(r['planned_steps']>1 for r in rows),
                passed_chain_variants=sum(r['passed'] and r['planned_steps']>1 for r in rows),
                families=families, results=rows,
                claims=dict(public_window_simulation=True, authored_fixture_suffixes=True,
                            engine_state_transitions=False, win_rate_evidence=False, production_authority=False))
