"""Guarded v3 engine conformance; no model training or benchmark."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from ptcg_strategy_forge.resources_gate import heavy_job
from ptcg_strategy_forge.run_safety import monitor_process, child_environment, child_creation_flags, atomic_json
from scripts.ai.ptcgdap.public_input_v3 import PublicInputV3, PublicHistoryV3, contract
from check_public_input_v2 import sha
from public_input_v3_runtime import upgrade_transport


def run(runtime, output, godot):
    runtime, output, godot = [Path(p).resolve() for p in (runtime, output, godot)]
    if not runtime.is_relative_to(ROOT/'work') or not (runtime/'public-input-v3-install.json').is_file(): raise ValueError('not_isolated')
    if output.exists(): raise ValueError('output_exists')
    output.mkdir(parents=True)
    with heavy_job(output_path=output) as admission:
        atomic_json(output/'admission.json', admission)
        upgrade_transport(runtime)
        for version in (2,3):
            target = runtime/f'scripts/ai/ptcgdap/public/PublicInputV{version}.gd'
            if target.is_symlink() or target.stat().st_nlink != 1: raise ValueError('shared_runtime_module')
            shutil.copyfile(ROOT/f'runtime/godot/PublicInputV{version}.gd', runtime/f'scripts/ai/ptcgdap/public/PublicInputV{version}.gd')
            shutil.copyfile(ROOT/f'tools/public_input_v{version}_probe.gd', runtime/f'public_input_v{version}_probe.gd')
        atomic_json(runtime/'public_input_v2_contract.json', contract())
        with (output/'engine.log').open('w',encoding='utf-8') as log:
            process = subprocess.Popen([str(godot),'--headless','--path',str(runtime),'--script','res://public_input_v3_probe.gd','--',str(output/'engine.json')],
                stdout=log,stderr=subprocess.STDOUT,env=child_environment(),creationflags=child_creation_flags())
            monitor_process(process,output,storage_targets=admission['storage_targets'],max_seconds=60,output_limit_bytes=32*1024*1024)
        evidence=json.loads((output/'engine.json').read_bytes()) if (output/'engine.json').exists() else dict(rows=[],failures=['engine_result_missing'],assertions=0)
        errors=list(evidence['failures']); checks=0; memories={}
        log_text=(output/'engine.log').read_text(encoding='utf-8')
        if 'SCRIPT ERROR:' in log_text or 'ERROR:' in log_text: errors.append('engine_script_or_resource_error')
        for row in evidence['rows']:
            try:
                value=PublicInputV3.capture(dict(profile='ptcg-public-input-v3',frame=row['frame'],input=row['supplement']))
                assert value.document()==PublicInputV3.capture(value.envelope()).document()
                history=value.history()
                memory=memories.setdefault(history['stream'],PublicHistoryV3())
                memory.ingest(history)
                assert memory.ingest(history)['accepted']==0
                assert PublicHistoryV3.restore(memory.export()).export()==memory.export()
                checks+=4
            except (ValueError,AssertionError) as e: errors.append(row['label']+':'+str(e))
        files=[ROOT/'scripts/ai/ptcgdap/public_input_v3.py',ROOT/'runtime/godot/PublicInputV3.gd',ROOT/'tools/public_input_v3_probe.gd',ROOT/'contracts/ptcgdap/public_input_v3.json']
        result=dict(status='passed' if process.returncode==0 and not errors and evidence['rows'] else 'failed',errors=errors,
            snapshots=len(evidence['rows']),native_assertions=evidence['assertions'],python_checks=checks,
            files={p.relative_to(ROOT).as_posix():sha(p) for p in files},godot_sha256=sha(godot))
        engine_files=sorted(list((runtime/'scripts').rglob('*.gd'))+list((runtime/'data/bundled_user/cards').glob('*.json')))
        atomic_json(output/'engine-source-manifest.json',{p.relative_to(runtime).as_posix():sha(p) for p in engine_files})
        result['engine_source_manifest_sha256']=sha(output/'engine-source-manifest.json')
        result['engine_evidence_sha256']=sha(output/'engine.json') if (output/'engine.json').exists() else None
        result['scope']='constructed positions, real engine methods/effects/bridge, both-view public Host envelopes; no production or CABT parity claim'
        atomic_json(output/'acceptance.json',result)
        print(json.dumps(result,ensure_ascii=False))
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('runtime','output','godot'): parser.add_argument('--'+key,required=True)
    result=run(**vars(parser.parse_args()))
    sys.exit(0 if result['status']=='passed' else 1)
