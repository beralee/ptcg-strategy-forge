"""Author and review strategies with the shared Base framework. No publishing."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'),str(ROOT)]
from ptcg_strategy_forge import StrategyWorkspace
from ptcg_strategy_forge.strategy_base import StrategyBase, BasePlanError
from ptcg_strategy_forge.strategy_reflection import reflect_native, reflect_bench
from scripts.ai.ptcgdap.source_lock import load_json_bytes_strict


def read(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 16*1024**2:
        raise BasePlanError('base_input_path_or_size_invalid')
    return load_json_bytes_strict(path.read_bytes())


def write_new(path, value):
    path = Path(path)
    payload = json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        stream.write(payload)


def init(workspace):
    root = StrategyWorkspace.open(workspace).root
    adapter = read(root/'package/policy/adapter.json')
    plan = StrategyBase.draft(adapter)
    path = root/'base'
    path.mkdir(exist_ok=False)
    write_new(path/'adapter.json',adapter)
    write_new(path/'plan.json',plan)
    write_new(path/'source-lock.json',dict(
        deck_manifest_sha256=hashlib.sha256((root/'package/deck/deck_manifest.json').read_bytes()).hexdigest(),
        sdk_manifest_sha256=hashlib.sha256((ROOT/'vendor/ptcgdap-sdk-manifest.json').read_bytes()).hexdigest()))
    return dict(status='needs_design',path=str(path),unresolved=list(plan['considerations']))


def inputs(workspace):
    root = StrategyWorkspace.open(workspace).root
    if (root/'base').is_symlink():
        raise BasePlanError('base_input_path_or_size_invalid')
    lock = read(root/'base/source-lock.json')
    for field,path in [('deck_manifest_sha256',root/'package/deck/deck_manifest.json'),
                       ('sdk_manifest_sha256',ROOT/'vendor/ptcgdap-sdk-manifest.json')]:
        if lock.get(field) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise BasePlanError('base_source_lock_changed')
    deck = read(root/'package/deck/deck_manifest.json')
    return read(root/'base/adapter.json'),read(root/'base/plan.json'),{row['local_card_uid'] for row in deck['cards']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    for name in ('init','audit','compile'):
        command = sub.add_parser(name)
        command.add_argument('--workspace',required=True,type=Path)
        if name == 'compile': command.add_argument('--output',required=True,type=Path)
        if name == 'audit': command.add_argument('--report',type=Path)
    command = sub.add_parser('reflect-native')
    command.add_argument('--trace',required=True,type=Path)
    command.add_argument('--seat',required=True,type=int,choices=(0,1))
    command.add_argument('--report',required=True,type=Path)
    command = sub.add_parser('reflect-bench')
    command.add_argument('--bench-report',required=True,type=Path)
    command.add_argument('--candidate-sha256',required=True)
    command.add_argument('--game-index',action='append',type=int)
    command.add_argument('--report',required=True,type=Path)
    args = parser.parse_args(argv)
    if getattr(args,'report',None) is not None and args.report.exists():
        raise BasePlanError('base_report_exists')
    if args.command == 'init':
        result = init(args.workspace)
    elif args.command in ('audit','compile'):
        adapter,plan,allowed = inputs(args.workspace)
        if args.command == 'audit':
            result = StrategyBase.audit(adapter,plan,allowed_card_uids=allowed)
        else:
            compiled = StrategyBase.compile(adapter,plan,allowed_card_uids=allowed)
            args.output.mkdir(parents=True,exist_ok=False)
            write_new(args.output/'adapter.json',compiled.adapter)
            write_new(args.output/'compile-report.json',compiled.report)
            result = compiled.report
    elif args.command == 'reflect-native':
        result = reflect_native(args.trace,seat=args.seat)
    else:
        result = reflect_bench(args.bench_report,expected_candidate_sha256=args.candidate_sha256,
                               game_indexes=args.game_index)
    if getattr(args,'report',None) is not None:
        write_new(args.report,result)
    # Full reports stay in files; terminal output remains small.
    print(json.dumps({k:result[k] for k in ('status','path','route_count','unresolved','gaps','reviewed_windows') if k in result},ensure_ascii=False))
    return 2 if args.command == 'audit' and result['status'] == 'needs_design' else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError,OSError) as error:
        code = str(error) if isinstance(error,BasePlanError) or (isinstance(error,ValueError) and str(error).startswith(('reflection_','native_trace_','bench_'))) else 'base_input_or_io_error'
        print(json.dumps(dict(status='failed',error_code=code)))
        raise SystemExit(1)
