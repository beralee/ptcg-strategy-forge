from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.ptcgdap.build_author_strategy_package import (
    _read_private_key,
    build_package_bytes,
    read_source_directory,
    sha256_bytes,
)
from tools.ptcgdap.author_strategy_developer import validate_development_package


def _public_identity(private_key: bytes) -> tuple[bytes, str, str]:
    public_key = (
        Ed25519PrivateKey.from_private_bytes(private_key)
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    )
    fingerprint = hashlib.sha256(public_key).hexdigest().upper()
    return public_key, fingerprint, "signing-" + fingerprint[:24].lower()


def generate_release_key(private_key_path: Path, public_key_path: Path) -> dict[str, object]:
    private_key_path = Path(private_key_path)
    public_key_path = Path(public_key_path)
    if private_key_path.resolve(strict=False) == public_key_path.resolve(strict=False):
        raise ValueError("release_key_paths_conflict")
    if private_key_path.exists() or public_key_path.exists():
        raise ValueError("release_key_path_exists")
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    public_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate().private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key, fingerprint, key_id = _public_identity(private_key)
    public_document = {
        "document_type": "ptcgdap_developer_signing_public_key_v1",
        "schema_version": 1,
        "algorithm": "ed25519",
        "key_id": key_id,
        "public_key_base64": base64.b64encode(public_key).decode("ascii"),
        "fingerprint_sha256": fingerprint,
    }
    try:
        with private_key_path.open("xb") as stream:
            stream.write(private_key)
        os.chmod(private_key_path, 0o600)
        with public_key_path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(public_document, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
    except Exception:
        if private_key_path.exists() and not public_key_path.exists():
            private_key_path.unlink()
        raise
    return {
        "document_type": "ptcg_strategy_forge_release_key_generation_v1",
        "schema_version": 1,
        "status": "generated",
        "algorithm": "ed25519",
        "key_id": key_id,
        "fingerprint_sha256": fingerprint,
        "public_key_base64": public_document["public_key_base64"],
        "private_key_path": str(private_key_path.resolve()),
        "public_key_path": str(public_key_path.resolve()),
        "private_key_exported": False,
    }


def build_registered_release(
    source: Path, output: Path, private_key_path: Path
) -> dict[str, object]:
    source = Path(source)
    output = Path(output)
    if output.exists():
        raise ValueError("release_output_exists")
    private_key = _read_private_key(Path(private_key_path))
    payloads = read_source_directory(source)
    return _build_registered_payloads(
        payloads, output, private_key, source_archive_sha256=None
    )


def resign_registered_release(
    package: Path, output: Path, private_key_path: Path
) -> dict[str, object]:
    package = Path(package)
    validation = validate_development_package(package)
    if validation.get("status") != "valid":
        raise ValueError("release_source_package_invalid")
    try:
        with zipfile.ZipFile(package, "r") as archive:
            payloads = {
                name: archive.read(name)
                for name in archive.namelist()
                if name not in {"files.sha256.json", "signature.json"}
            }
    except (OSError, KeyError, zipfile.BadZipFile) as error:
        raise ValueError("release_source_package_invalid") from error
    report = _build_registered_payloads(
        payloads,
        Path(output),
        _read_private_key(Path(private_key_path)),
        source_archive_sha256=hashlib.sha256(package.read_bytes()).hexdigest().upper(),
    )
    report["document_type"] = "ptcg_strategy_forge_registered_release_resign_v1"
    report["payload_preserved"] = True
    return report


def _build_registered_payloads(
    payloads: dict[str, bytes],
    output: Path,
    private_key: bytes,
    *,
    source_archive_sha256: str | None,
) -> dict[str, object]:
    output = Path(output)
    if output.exists():
        raise ValueError("release_output_exists")
    public_key, fingerprint, key_id = _public_identity(private_key)
    archive = build_package_bytes(payloads, private_key, key_id=key_id)
    if archive != build_package_bytes(payloads, private_key, key_id=key_id):
        raise ValueError("release_build_not_deterministic")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(archive)
    report: dict[str, object] = {
        "document_type": "ptcg_strategy_forge_registered_release_build_v1",
        "schema_version": 1,
        "status": "built",
        "package_id": json.loads(payloads["strategy_package.json"])["package_id"],
        "package_version": json.loads(payloads["strategy_package.json"])["package_version"],
        "archive_path": str(output.resolve()),
        "archive_bytes": len(archive),
        "archive_sha256": sha256_bytes(archive),
        "signature_algorithm": "ed25519",
        "signature_key_id": key_id,
        "signing_key_fingerprint_sha256": fingerprint,
        "public_key_base64": base64.b64encode(public_key).decode("ascii"),
        "deterministic": True,
        "signature_scope": "developer_registered_release",
        "private_key_exported": False,
    }
    if source_archive_sha256 is not None:
        report["source_archive_sha256"] = source_archive_sha256
    return report


__all__ = [
    "build_registered_release",
    "generate_release_key",
    "resign_registered_release",
]
