"""Seal public-only examples from a successful, source-matched engine probe."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.ai.ptcgdap.public_input_v3 import PublicInputV3, PublicHistoryV3


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def export(source, output):
    source, output = Path(source), Path(output)
    receipt = json.loads((source/'acceptance.json').read_bytes())
    if receipt['status'] != 'passed': raise ValueError('failed_probe_not_evidence')
    for name, expected in receipt['files'].items():
        if sha(ROOT/name) != expected: raise ValueError('qualified_source_drift:'+name)
    for name, key in [('engine.json','engine_evidence_sha256'),('engine-source-manifest.json','engine_source_manifest_sha256')]:
        if sha(source/name) != receipt[key]: raise ValueError('qualified_evidence_drift:'+name)
    rows = json.loads((source/'engine.json').read_bytes())['rows']
    values = {r['label']: PublicInputV3.capture(r['frame'],r['supplement']) for r in rows}
    output.mkdir(parents=True,exist_ok=True)
    for name, target in [('engine.json','engine-snapshots.json'),('acceptance.json','engine-acceptance.json'),
                         ('engine-source-manifest.json','engine-source-manifest.json'),('engine.log','engine.log'),
                         ('admission.json','resource-admission.json')]:
        shutil.copyfile(source/name,output/target)

    def save(name, value):
        (output/name).write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')

    for label in ['normal','shared-exhausted','v3-marker-protection-effective',
                  'v3-ultra-ball-payment','v3-ultra-ball-search','v3-ultra-ball-committed',
                  'v3-dragapult-allocation','v3-dragapult-allocation-remaining','v3-history-ring-truncated']:
        save(label+'.json',values[label].envelope())
    save('coverage-report.json',{k:v.coverage() for k,v in values.items()})
    value=values['v3-ultra-ball-committed']; memory=PublicHistoryV3()
    accepted=memory.ingest(value.history()); restored=PublicHistoryV3.restore(memory.export())
    duplicate=restored.ingest(value.history())
    truncated=values['v3-history-ring-truncated']; gap=PublicHistoryV3()
    gap_report=gap.ingest(truncated.history())
    save('history-recovery-example.json',dict(complete_memory=memory.export(),accepted=accepted,duplicate=duplicate,
         truncated_memory=gap.export(),snapshot_recovery=gap_report))
    return dict(status='passed',snapshots=len(values),output=str(output.resolve()))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True)
    parser.add_argument('--output',required=True)
    print(json.dumps(export(**vars(parser.parse_args()))))
