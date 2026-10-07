"""Install reviewed v3 hooks only in a sealed isolated Forge runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from public_input_v2_runtime import patched_owner, OWNER

ROOT = Path(__file__).resolve().parents[1]


def install(runtime):
    runtime = Path(runtime).resolve()
    if not runtime.is_relative_to(ROOT / 'work') or not (runtime / 'sealed-inputs.json').is_file():
        raise ValueError('public_input_v3_not_isolated')
    receipt = runtime / 'public-input-v3-install.json'
    if receipt.exists(): raise ValueError('public_input_v3_install_exists')
    paths = [OWNER, 'scripts/engine/GameStateMachine.gd']
    originals = {}
    for name in paths:
        path = runtime / name
        if path.is_symlink() or path.stat().st_nlink != 1: raise ValueError('public_input_v3_shared_source')
        originals[name] = path.read_bytes()
    owner_text = originals[OWNER].decode('utf-8')
    if 'var public_input_v2:' not in owner_text: owner_text = patched_owner(owner_text)
    owner_text = owner_text.replace('var last_public_input_v2: Dictionary = {}', 'var last_public_input_v2: Dictionary = {}\nvar last_public_observation: Dictionary = {}')
    owner_text = owner_text.replace('public/PublicInputV2.gd', 'public/PublicInputV3.gd')
    anchor = '\t\tlast_public_input_v2 = public_input_v2.capture(self, frame)'
    if owner_text.count(anchor) != 1: raise ValueError('public_input_v3_owner_drift')
    owner_text = owner_text.replace(anchor, anchor + '\n\t\tlast_public_observation = public_input_v2.make_observation(frame, last_public_input_v2)')
    gsm = originals[paths[1]].decode('utf-8').replace('\r\n', '\n')
    anchor = '\t\t"ability_name": ability_name,\n\t\t"source_slot_runtime_id": int(pokemon.get_instance_id()),'
    if gsm.count(anchor) != 1: raise ValueError('public_input_v3_ability_hook_drift')
    gsm = gsm.replace(anchor, '\t\t"public_ability_index": ability_index,\n' + anchor)
    backup = runtime / 'public-input-v3-originals'
    backup.mkdir()
    for name, content in originals.items():
        dest = backup / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    for name, content in [(OWNER, owner_text), (paths[1], gsm)]:
        (runtime/name).write_text(content, encoding='utf-8', newline='\n')
    for version in (2, 3):
        shutil.copyfile(ROOT/f'runtime/godot/PublicInputV{version}.gd', runtime/f'scripts/ai/ptcgdap/public/PublicInputV{version}.gd')
    result = dict(version=3, production=False, original_sha256={k: hashlib.sha256(v).hexdigest().upper() for k,v in originals.items()})
    receipt.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


def upgrade_transport(runtime):
    """One reviewed migration for already installed development v3 runtimes."""
    runtime=Path(runtime).resolve()
    if not runtime.is_relative_to(ROOT/'work') or not (runtime/'public-input-v3-install.json').is_file():
        raise ValueError('public_input_v3_not_isolated')
    path=runtime/OWNER
    if path.is_symlink() or path.stat().st_nlink != 1: raise ValueError('public_input_v3_shared_source')
    old=path.read_bytes();text=old.decode('utf-8')
    anchor='last_public_observation = {"profile": "ptcg-public-input-v3", "frame": frame.duplicate(true), "input": last_public_input_v2.duplicate(true)}'
    replacement='last_public_observation = public_input_v2.make_observation(frame, last_public_input_v2)'
    if text.count(replacement)==1: return
    if text.count(anchor)!=1: raise ValueError('public_input_v3_transport_drift')
    backup=runtime/'public-input-v3-transport-original.gd'
    if backup.exists(): raise ValueError('public_input_v3_transport_backup_exists')
    backup.write_bytes(old)
    path.write_text(text.replace(anchor,replacement),encoding='utf-8',newline='\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True)
    print(json.dumps(install(parser.parse_args().runtime), indent=2))
