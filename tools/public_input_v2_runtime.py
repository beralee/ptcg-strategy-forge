"""Install the public-input companion in a new isolated Forge research runtime."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
OWNER = 'scripts/ai/ptcgdap/host/godot/PtcgDAPAuthorDevelopmentBattleOwner.gd'
MODULE = 'scripts/ai/ptcgdap/public/PublicInputV2.gd'


def patched_owner(text):
    if 'var public_input_v2:' in text:
        raise ValueError('public_input_v2_already_installed')
    anchors = ['var _match_id := ""', '\tif not competitive:\n\t\tframe["strategy_id"]', '\t_gsm = null']
    if any(text.count(a) != 1 for a in anchors):
        raise ValueError('public_input_v2_owner_drift')
    text = text.replace(anchors[0], anchors[0] + '\nvar public_input_v2: Variant = null\nvar last_public_input_v2: Dictionary = {}\nvar _public_input_bridge: Variant = null')
    run_anchor = 'func run_single_step(battle_scene: Control, gsm: GameStateMachine) -> bool:\n'
    if text.count(run_anchor) != 1:
        raise ValueError('public_input_v2_owner_drift')
    text = text.replace(run_anchor, run_anchor + '\t_public_input_bridge = battle_scene\n')
    text = text.replace(anchors[1], '\tif competitive:\n\t\tif public_input_v2 == null:\n\t\t\tpublic_input_v2 = load("res://' + MODULE + '").new()\n\t\t\tpublic_input_v2.bind(_gsm, _match_id, player_index)\n\t\tlast_public_input_v2 = public_input_v2.capture(self, frame)\n' + anchors[1])
    return text.replace(anchors[2], '\tif public_input_v2 != null: public_input_v2.close()\n' + anchors[2])


def install(runtime):
    runtime = Path(runtime).resolve()
    if not runtime.is_relative_to(ROOT / 'work') or not (runtime / 'sealed-inputs.json').is_file():
        raise ValueError('public_input_v2_not_isolated')
    receipt = runtime / 'public-input-v2-install.json'
    if receipt.exists():
        raise ValueError('public_input_v2_install_exists')
    owner = runtime / OWNER
    if owner.is_symlink() or owner.stat().st_nlink != 1:
        raise ValueError('public_input_v2_shared_owner')
    original = owner.read_bytes()
    changed = patched_owner(original.decode('utf-8'))
    target = runtime / MODULE
    if target.exists():
        raise ValueError('public_input_v2_module_exists')
    (runtime / 'public-input-v2-owner-original.gd').write_bytes(original)
    shutil.copyfile(ROOT / 'runtime/godot/PublicInputV2.gd', target)
    owner.write_text(changed, encoding='utf-8', newline='\n')
    result = dict(version=2, original_owner_sha256=hashlib.sha256(original).hexdigest(),
        files={name: hashlib.sha256((runtime/name).read_bytes()).hexdigest() for name in (OWNER, MODULE)},
        production=False, transport='Host.last_public_input_v2 companion; unchanged v1 frame')
    receipt.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True)
    print(json.dumps(install(parser.parse_args().runtime), ensure_ascii=False, indent=2))
