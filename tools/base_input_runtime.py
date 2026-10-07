"""Reviewed input-only overlay for newly cloned learning runtimes."""
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
import hashlib
import json

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest().upper()

def read(path):
    # Godot JSON writes integral seeds and seats as floating point numbers.
    def number(s):
        n=float(s)
        return int(n) if n.is_integer() else n
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),parse_float=number)

def pinned(path,expected,kind):
    if not Path(path).is_file() or sha(path)!=str(expected).upper():raise ValueError('learning_'+kind+'_changed')
from ptcg_strategy_forge.run_safety import atomic_json

CORE='scripts/ai/ptcgdap/public/CompetitivePolicyV2.gd'
MODULE='scripts/ai/ptcgdap/public/BaseInputV1.gd'
CONTRACT='contracts/ptcgdap/base_input_v1.json'
MARKER='# Forge BaseInput v1'


def patched_core(text):
    if MARKER in text:raise ValueError('base_input_runtime_already_patched')
    anchor='\tvar turn_program_frame: Dictionary = frame_value.duplicate(true)'
    output='\t\t"model_frontier": _base_model_frontier('
    if text.count(anchor)!=1 or text.count(output)!=1:
        raise ValueError('base_input_runtime_owner_changed')
    prefix='\n'.join([
        '\t'+MARKER,
        '\tvar input_script = load("res://'+MODULE+'")',
        '\tvar input_contract: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://'+CONTRACT+'"))',
        '\tvar base_input: Dictionary = input_script.capture_validated(frame_value, input_contract, "res://data/bundled_user/cards")',
        '\tif not base_input.accepted: return _decision_error(base_input.error_code)',
    ])
    return text.replace(anchor,prefix+'\n'+anchor).replace(output,'\t\t"base_input": base_input,\n'+output)


def install(runtime):
    runtime=Path(runtime).resolve()
    if (not runtime.is_relative_to((ROOT/'work').resolve()) or not (runtime/'sealed-inputs.json').is_file()):
        raise ValueError('base_input_runtime_not_isolated')
    receipt=runtime/'base-input-install.json'
    if receipt.exists():
        saved=read(receipt)
        for name,value in saved['files'].items():pinned(runtime/name,value,'base_input_runtime')
        for name,value in saved['source_files'].items():pinned(ROOT/name,value,'base_input_source')
        return saved
    core=runtime/CORE
    # Clones copy code; reject a shared hard link instead of mutating its source.
    if core.is_symlink() or core.stat().st_nlink!=1:raise ValueError('base_input_shared_core')
    before=sha(core);revised=patched_core(core.read_text(encoding='utf-8'))
    sources={'runtime/godot/BaseInputV1.gd':MODULE,CONTRACT:CONTRACT}
    for source,target in sources.items():
        dest=runtime/target
        if dest.exists():raise ValueError('base_input_runtime_target_exists')
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/source,dest)
    core.write_text(revised,encoding='utf-8',newline='\n')
    result=dict(version=1,reviewed_core_before_sha256=before,files={p:sha(runtime/p) for p in (CORE,MODULE,CONTRACT)},
        source_files={p:sha(ROOT/p) for p in sources},installer_sha256=sha(__file__),production_approved=False)
    atomic_json(receipt,result)
    return result
