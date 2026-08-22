from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFIXES = (
    Path("scripts/ai/ptcgdap"),
    Path("contracts/ptcgdap"),
    Path("data/ptcgdap"),
    Path("data/bundled_user"),
    Path("tools/ptcgdap"),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def build() -> dict[str, object]:
    files: list[dict[str, object]] = []
    for prefix in PREFIXES:
        for path in sorted((ROOT / prefix).rglob("*"), key=lambda value: value.as_posix().encode("utf-8")):
            if not path.is_file() or path.is_symlink() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(ROOT).as_posix()
            files.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha(path)})
    return {
        "document_type": "ptcg_strategy_forge_sdk_snapshot_v1",
        "schema_version": 1,
        "source": {
            "repository": "https://github.com/beralee/PtcgDeckAgent",
            "worktree": "PtcgDAP",
            "base_commit": "3534d22b28d2895d5de5bf12cd35836d686714aa",
            "captured_on": "2026-08-23",
            "scope": "author-strategy development, validation, simulation, and publishing",
            "note": "Snapshot captured from the reviewed local PtcgDAP worktree; each distributed byte is pinned below.",
        },
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = ROOT / "vendor/ptcgdap-sdk-manifest.json"
    expected = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.check:
        if not path.is_file() or path.read_bytes() != expected:
            raise SystemExit("sdk snapshot manifest drift")
        print("sdk snapshot manifest ok")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(expected)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
