"""Verify a built wheel outside the source tree using the current core deps."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="forge-wheel-verification-") as name:
        root = Path(name)
        target = root / "installed"
        subprocess.run([sys.executable, "-B", "-m", "pip", "install", "--no-deps", "--no-compile",
                        "--target", str(target), str(wheel)], check=True, stdout=subprocess.DEVNULL)
        code = """
import ast, json, sys
from pathlib import Path
sys.modules.update({name: None for name in ('numpy', 'onnx', 'onnxruntime')})
from ptcg_strategy_forge import StrategyWorkspace
from ptcg_strategy_forge.resources import resource_root
from ptcg_strategy_forge.provenance import verify_snapshot
from ptcg_strategy_forge.application import doctor
for module in resource_root().parent.glob('*.py'):
    ast.parse(module.read_text(encoding='utf-8'), filename=str(module))
workspace = StrategyWorkspace.create(Path('nested/deck'), author_id='local.dev')
snapshot = verify_snapshot(resource_root())
assert snapshot['accepted'], snapshot['failures']
assert '_bundle' in resource_root().parts
assert workspace.status()['status'] == 'ready'
health = doctor()
assert health['status'] == 'passed', health
print(json.dumps({'status': 'passed', 'snapshot_file_count': snapshot['file_count'], 'rules_without_model_dependencies': True, 'doctor': health['status']}))
"""
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=root,
                                env={**os.environ, "PYTHONPATH": str(target)}, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        print(json.dumps({"document_type": "forge_installed_wheel_check_v1", **json.loads(result.stdout),
                          "scope": "checkout_independent_install_with_current_interpreter_core_dependencies"}))


if __name__ == "__main__":
    main()
