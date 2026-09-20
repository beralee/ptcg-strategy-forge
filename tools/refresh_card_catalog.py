"""Refresh only public card bytes and their qualified UCIS contracts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_developer_supported_cards import validate_card_sources


def refresh(source: Path) -> None:
    source = source.resolve(strict=True)
    if source == ROOT or not (source / "project.godot").is_file():
        raise ValueError("card_refresh_public_game_source_required")
    # This fails before copying if the source resource set, effects, or receipt
    # drifted after the real engine qualification.
    subprocess.run([sys.executable, str(source / "tools/ptcgdap/refresh_developer_card_catalog.py")], cwd=source, check=True)
    catalog = json.loads((source / "contracts/ptcgdap/ucis_card_catalog_v1.json").read_text(encoding="utf-8"))
    validate_card_sources(source, catalog)
    files = {row["source_path"]: row["source_path"] for row in catalog["cards"]}
    for path in (source / "contracts/ptcgdap").glob("ucis_*_v1.json"):
        relative = path.relative_to(source).as_posix()
        files[relative] = relative
    for name in ("ucis_catalog_qualification_v1.json", "ucis_performance_qualification_v1.json"):
        files["evidence/ptcgdap/ucis/" + name] = "contracts/ptcgdap/" + name
    files["evidence/ptcgdap/a3/corresponding_card_whole_battle_input_index_v1.json"] = "contracts/ptcgdap/corresponding_card_whole_battle_input_index_v1.json"
    # A catalog refresh cannot silently upgrade the policy interpreter.
    for name in ("ucis.py", "ucis_sdk.py"):
        relative = "scripts/ai/ptcgdap/" + name
        if (source / relative).read_bytes() != (ROOT / relative).read_bytes():
            raise ValueError(f"card_refresh_sdk_compiler_review_required:{name}")
    pinned = []
    for origin, destination in sorted(files.items()):
        path = source / origin
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"card_refresh_source_missing:{origin}")
        pinned.append((path, ROOT / destination, hashlib.sha256(path.read_bytes()).hexdigest().upper()))
    for path, target, expected in pinned:
        if hashlib.sha256(path.read_bytes()).hexdigest().upper() != expected:
            raise ValueError("card_refresh_source_changed")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    registry = json.loads((ROOT / "contracts/ptcgdap/ucis_registry_v1.json").read_text(encoding="utf-8"))
    canonical = json.dumps(registry, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    helper = ROOT / "src/ptcg_strategy_forge/ucis_runtime.py"
    text, count = re.subn(r'^REGISTRY_SHA256 = "[0-9A-F]{64}"$',
        'REGISTRY_SHA256 = "' + hashlib.sha256(canonical).hexdigest().upper() + '"',
        helper.read_text(encoding="utf-8"), flags=re.MULTILINE)
    if count != 1:
        raise ValueError("card_refresh_runtime_registry_pin_missing")
    helper.write_text(text, encoding="utf-8")
    for script in ("build_developer_supported_cards.py", "build_sdk_snapshot.py"):
        subprocess.run([sys.executable, str(ROOT / "tools" / script)], cwd=ROOT, check=True)
    print(json.dumps({"status": "refreshed", "cards": len(catalog["cards"]), "files": len(pinned)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    refresh(parser.parse_args().source)
