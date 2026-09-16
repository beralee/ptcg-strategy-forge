"""Bundle only reviewed snapshot bytes and explicit developer resources."""
import hashlib
import json
from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent


class BuildWithSnapshot(build_py):
    def run(self):
        super().run()
        target = Path(self.build_lib) / "ptcg_strategy_forge/_bundle"
        manifest = ROOT / "vendor/ptcgdap-sdk-manifest.json"
        files = [manifest, ROOT / "tools/build_developer_supported_cards.py", ROOT / "README.md"]
        for entry in json.loads(manifest.read_text(encoding="utf-8"))["files"]:
            path = (ROOT / entry["path"]).resolve()
            path.relative_to(ROOT)
            if hashlib.sha256(path.read_bytes()).hexdigest().upper() != entry["sha256"].upper():
                raise ValueError("sdk_snapshot_hash_mismatch")
            files.append(path)
        for directory in ("data/developer", "docs", "demo/marnie-forge"):
            files.extend(path for path in (ROOT / directory).rglob("*")
                         if path.is_file() and path.suffix in {".json", ".md", ".py"} and "__pycache__" not in path.parts)
        for path in files:
            destination = target / path.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, destination)


setup(cmdclass={"build_py": BuildWithSnapshot})
