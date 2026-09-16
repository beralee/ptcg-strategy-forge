"""Content-addressed, immutable acceptance receipts for local workspaces."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity(root: Path) -> str:
    entries = {}
    for directory in (root / "package", root / "scenarios"):
        if directory.is_symlink():
            raise ValueError("workspace_source_symlink_forbidden")
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError("workspace_source_symlink_forbidden")
            if path.is_file():
                entries[path.relative_to(root).as_posix()] = digest(path)
    entries["scenario-suite.json"] = digest(root / "scenario-suite.json")
    from .resources import resource_root
    entries["sdk_snapshot"] = digest(resource_root() / "vendor/ptcgdap-sdk-manifest.json")
    for path in sorted(Path(__file__).parent.glob("*.py")):
        entries["sdk/" + path.name] = digest(path)
    return hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()


def record(root: Path, artifact: Path, source: str, result: dict) -> dict:
    artifact_hash = digest(artifact)
    relative = "build/archives/" + artifact_hash + ".ptcgai"
    archive = root / relative
    archive.parent.mkdir(parents=True, exist_ok=True)
    try:
        with archive.open("xb") as stream:
            stream.write(artifact.read_bytes())
    except FileExistsError:
        if digest(archive) != artifact_hash:
            raise ValueError("workspace_archive_collision")
    document = {
        "document_type": "forge_acceptance_receipt_v1",
        "source_sha256": source,
        "artifact_sha256": artifact_hash,
        "archive_relative_path": relative,
        "artifact_path": str(artifact.resolve()),
        "acceptance": result,
    }
    payload = json.dumps(document, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
    identity = hashlib.sha256(payload).hexdigest()
    path = root / "build" / "records" / (identity + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError:
        if path.read_bytes() != payload:
            raise ValueError("workspace_receipt_collision")
    return {"id": identity, "path": str(path)}


def acceptance(root: Path, artifact: Path, report: Path) -> dict:
    if not report.is_file():
        return {"status": "unchecked"}
    try:
        latest = json.loads(report.read_text(encoding="utf-8"))
        identity = latest["record"]["id"]
        if not isinstance(identity, str) or len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity):
            raise ValueError("invalid_id")
        path = root / "build" / "records" / (identity + ".json")
        if digest(path) != identity:
            raise ValueError("invalid_receipt")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        valid = (receipt["source_sha256"] == source_identity(root)
                 and receipt["artifact_sha256"] == digest(artifact)
                 and receipt["artifact_path"] == str(artifact.resolve()))
        if "archive_relative_path" in receipt:
            relative = "build/archives/" + receipt["artifact_sha256"] + ".ptcgai"
            valid = valid and receipt["archive_relative_path"] == relative and digest(root / relative) == receipt["artifact_sha256"]
        return {"status": "current" if valid else "stale", "record_id": identity}
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "stale"}
