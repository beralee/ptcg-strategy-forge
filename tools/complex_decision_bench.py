"""Run authored multi-window strategy exams, including semantic option reversal."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from ptcg_strategy_forge.decision_bench import run_bench


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',required=True)
    parser.add_argument('--suite',required=True)
    parser.add_argument('--report',required=True)
    args=parser.parse_args()
    path=Path(args.report)
    if path.exists():raise ValueError('decision_bench_report_exists')
    report=run_bench(args.package,args.suite)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('passed','cases','variants','passed_variants','families')}))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
