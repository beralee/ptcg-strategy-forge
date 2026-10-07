"""Serial engine-operation witnesses with closed Python/native input validation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from ptcg_strategy_forge.resources_gate import heavy_job
from ptcg_strategy_forge.run_safety import monitor_process, child_environment, child_creation_flags, atomic_json
from scripts.ai.ptcgdap.public_input_v2 import PublicInputV2, PublicEventMemory, contract


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def run(runtime, output, godot):
    runtime, output, godot = map(lambda p: Path(p).resolve(), (runtime, output, godot))
    if not runtime.is_relative_to(ROOT / 'work') or not (runtime / 'public-input-v2-install.json').exists():
        raise ValueError('public_input_v2_not_isolated')
    if output.exists():
        raise ValueError('public_input_v2_output_exists')
    output.mkdir(parents=True)
    with heavy_job(output_path=output) as admission:
        # Refresh only this task's input module in the isolated operation probe.
        module = runtime / 'scripts/ai/ptcgdap/public/PublicInputV2.gd'
        if module.is_symlink() or module.stat().st_nlink != 1:
            raise ValueError('public_input_v2_shared_module')
        shutil.copyfile(ROOT / 'runtime/godot/PublicInputV2.gd', module)
        shutil.copyfile(ROOT / 'tools/public_input_v2_probe.gd', runtime / 'public_input_v2_probe.gd')
        atomic_json(runtime / 'public_input_v2_contract.json', contract())
        atomic_json(output / 'admission.json', admission)
        with (output / 'engine.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen([str(godot), '--headless', '--path', str(runtime), '--script',
                'res://public_input_v2_probe.gd', '--', str(output / 'engine.json')],
                stdout=log, stderr=subprocess.STDOUT, env=child_environment(), creationflags=child_creation_flags())
            monitor_process(process, output, storage_targets=admission['storage_targets'], max_seconds=60,
                            output_limit_bytes=32*1024*1024)
        evidence = json.loads((output / 'engine.json').read_bytes()) if (output/'engine.json').exists() else dict(rows=[], failures=['engine_result_missing'], assertions=0)
        errors = list(evidence['failures'])
        memories = {}
        checks = 0
        for row in evidence['rows']:
            try:
                value = PublicInputV2.capture(row['frame'], row['supplement'])
                # Round trip preserves values, zero/false/presence and source annotations.
                assert PublicInputV2.capture(value.base.frame(), value.payload()).input_sha256 == value.input_sha256
                assert not value.coverage()['training_ready']
                memory = memories.setdefault(row['supplement']['history']['stream'], PublicEventMemory())
                report = memory.ingest(row['supplement']['history'])
                assert memory.ingest(row['supplement']['history'])['accepted'] == 0
                assert PublicEventMemory.restore(memory.export()).export() == memory.export()
                checks += 5
            except (ValueError, AssertionError) as error:
                errors.append(row['label'] + ':' + str(error))
        result = dict(status='passed' if process.returncode == 0 and not errors and evidence['rows'] else 'failed',
            engine_assertions=evidence['assertions'], python_checks=checks, snapshots=len(evidence['rows']), errors=errors,
            files={str(p.relative_to(ROOT)): sha(p) for p in [ROOT/'runtime/godot/PublicInputV2.gd', ROOT/'tools/public_input_v2_probe.gd', ROOT/'scripts/ai/ptcgdap/public_input_v2.py']},
            godot_sha256=sha(godot), engine_evidence_sha256=sha(output/'engine.json') if (output/'engine.json').exists() else None,
            scope='constructed positions followed by real Godot operations/effect handlers and Host projection; no complete game or production claim')
        engine_files = sorted(list((runtime/'scripts').rglob('*.gd')) + list((runtime/'data/bundled_user/cards').glob('*.json')))
        source_manifest = {p.relative_to(runtime).as_posix(): sha(p) for p in engine_files}
        atomic_json(output/'engine-source-manifest.json', source_manifest)
        result['engine_source_manifest_sha256'] = sha(output/'engine-source-manifest.json')
        result['contract_sha256'] = sha(ROOT/'contracts/ptcgdap/public_input_v2.json')
        atomic_json(output/'acceptance.json', result)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'output', 'godot'): parser.add_argument('--'+name, required=True)
    result = run(**vars(parser.parse_args()))
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result['status'] == 'passed' else 1)
