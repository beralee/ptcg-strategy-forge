from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


MANIFEST_PATH = Path("vendor/ptcgdap-sdk-manifest.json")
SNAPSHOT_PREFIXES = (
    Path("scripts/ai/ptcgdap"),
    Path("contracts/ptcgdap"),
    Path("data/ptcgdap"),
    Path("data/bundled_user"),
    Path("tools/ptcgdap"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_PATH
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        type(value) is not dict
        or value.get("document_type") != "ptcg_strategy_forge_sdk_snapshot_v1"
        or type(value.get("files")) is not list
    ):
        raise ValueError("sdk_manifest_invalid")
    return value


def verify_snapshot(root: Path) -> dict[str, object]:
    manifest = load_manifest(root)
    failures: list[dict[str, object]] = []
    seen: set[str] = set()
    seen_casefolded: set[str] = set()
    for row in manifest["files"]:
        if type(row) is not dict or set(row) != {"path", "bytes", "sha256"}:
            raise ValueError("sdk_manifest_invalid")
        relative = row["path"]
        if (
            type(relative) is not str
            or relative in seen
            or relative.casefold() in seen_casefolded
            or "\\" in relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise ValueError("sdk_manifest_invalid")
        seen.add(relative)
        seen_casefolded.add(relative.casefold())
        path = root / relative
        if not path.is_file() or path.is_symlink():
            failures.append({"path": relative, "error_code": "sdk_file_missing"})
            continue
        actual_size = path.stat().st_size
        actual_hash = sha256_file(path)
        if actual_size != row["bytes"] or actual_hash != row["sha256"]:
            failures.append(
                {
                    "path": relative,
                    "error_code": "sdk_file_hash_mismatch",
                    "expected_bytes": row["bytes"],
                    "actual_bytes": actual_size,
                    "expected_sha256": row["sha256"],
                    "actual_sha256": actual_hash,
                }
            )
    actual: set[str] = set()
    for prefix in SNAPSHOT_PREFIXES:
        for path in (root / prefix).rglob("*"):
            if "__pycache__" in path.parts:
                continue
            if path.is_symlink():
                relative = path.relative_to(root).as_posix()
                failures.append({"path": relative, "error_code": "sdk_symlink_forbidden"})
                continue
            if path.is_file():
                actual.add(path.relative_to(root).as_posix())
    for relative in sorted(actual - seen):
        failures.append({"path": relative, "error_code": "sdk_file_unmanifested"})
    return {
        "accepted": not failures,
        "file_count": len(seen),
        "failures": failures,
        "source": manifest.get("source", {}),
    }
