from __future__ import annotations

import ast
import binascii
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
from types import MappingProxyType
from typing import Any, Mapping
import unicodedata
import zipfile

from scripts.ai.ptcgdap.source_lock import canonical_json_v1_bytes, load_json_bytes_strict


_SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$")
_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)
_ROOT_FILES = frozenset(
    {"manifest.json", "deck.csv", "runtime-lock.json", "content-manifest.json"}
)
_V1_FILES = frozenset({"manifest.json", "main.py", "deck.csv"})
_MANIFEST_V2_KEYS = {
    "document_type",
    "schema_version",
    "identity",
    "deck",
    "runtime",
    "compatibility",
    "qualification",
}
_IDENTITY_KEYS = {
    "strategy_id",
    "release_version",
    "author_id",
    "display_name",
    "summary",
}
_DECK_KEYS = {
    "path",
    "sha256",
    "card_count",
    "card_id_domain",
    "deck_id",
    "archetype_id",
    "display_name",
}
_RUNTIME_KEYS = {
    "kind",
    "entrypoint",
    "runtime_lock_path",
    "runtime_lock_sha256",
    "content_manifest_path",
    "content_manifest_sha256",
    "source_manifest_sha256",
    "resource_manifest_sha256",
    "runtime_profile_id",
    "runtime_profile_sha256",
    "python_abi",
    "sdk_contract_sha256",
}
_COMPATIBILITY_KEYS = {
    "environment",
    "engine_family",
    "engine_build_sha256",
    "observation_contract_sha256",
    "card_catalog_sha256",
    "required_capabilities",
}
_QUALIFICATION_KEYS = {
    "profile_id",
    "profile_sha256",
    "deterministic_replay_required",
}
_CONTENT_ITEM_KEYS = {
    "path",
    "sha256",
    "bytes",
    "kind",
    "media_type",
    "loader_capability",
    "executable",
}


class CompetitionBundleError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class CompetitionReleaseHandle:
    archive_bytes: bytes
    archive_sha256: str
    schema_generation: int
    canonical_zip_profile_generation: int
    manifest: dict[str, Any]
    manifest_canonical_sha256: str
    runtime_kind: str
    main_sha256: str
    deck_sha256: str
    deck_cards: tuple[int, ...]
    paths: tuple[str, ...]
    metadata: dict[str, Any]
    _files: Mapping[str, bytes]

    def file_bytes(self, path: str) -> bytes:
        try:
            return bytes(self._files[path])
        except KeyError as error:
            raise CompetitionBundleError("competition_bundle_member_missing") from error


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return canonical_json_v1_bytes(value)
    except (TypeError, ValueError, UnicodeError) as error:
        raise CompetitionBundleError("competition_json_invalid") from error


class CompetitionBundleOwner:
    """The only v1/v2 archive, closure, extraction, and release-handle owner."""

    def __init__(self, repository_root: Path, profile: Mapping[str, Any], runtime_lock: Mapping[str, Any]) -> None:
        self.repository_root = repository_root
        self.profile = dict(profile)
        self.runtime_lock = dict(runtime_lock)
        self.runtime_lock_bytes = canonical_json_bytes(self.runtime_lock)
        self.runtime_lock_sha256 = _sha256(self.runtime_lock_bytes)
        self.profile_sha256 = _sha256(canonical_json_bytes(self.profile))
        self._validate_profile()

    @classmethod
    def load_default(cls, repository_root: str | Path) -> CompetitionBundleOwner:
        root = Path(repository_root).resolve()
        try:
            profile = load_json_bytes_strict(
                (root / "contracts/ptcgdap/competition_bundle_v2_profile.json").read_bytes()
            )
            runtime_lock = load_json_bytes_strict(
                (root / "contracts/ptcgdap/competition_runtime_lock_v2.json").read_bytes()
            )
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
            raise CompetitionBundleError("competition_bundle_contract_invalid") from error
        return cls(root, profile, runtime_lock)

    def validate(self, archive_bytes: bytes) -> CompetitionReleaseHandle:
        if type(archive_bytes) is not bytes or not archive_bytes:
            raise CompetitionBundleError("competition_archive_invalid")
        if len(archive_bytes) > self._limit("max_archive_bytes"):
            raise CompetitionBundleError("competition_archive_too_large")
        try:
            files = self._read_canonical_archive(archive_bytes)
        except CompetitionBundleError as canonical_error:
            files = self._read_legacy_v1_archive(archive_bytes, canonical_error)
        return self._validate_files(files, archive_bytes=archive_bytes)

    def validate_files(self, files: Mapping[str, bytes]) -> CompetitionReleaseHandle:
        copied = self._copy_file_mapping(files)
        return self._validate_files(copied, archive_bytes=b"")

    def validate_directory(self, directory: str | Path) -> CompetitionReleaseHandle:
        root = Path(directory)
        if root.is_symlink() or not root.is_dir():
            raise CompetitionBundleError("competition_bundle_directory_invalid")
        resolved = root.resolve()
        files: dict[str, bytes] = {}
        for path in resolved.rglob("*"):
            if path.is_symlink():
                raise CompetitionBundleError("competition_bundle_path_unsafe")
            if path.is_dir():
                continue
            if not path.is_file():
                raise CompetitionBundleError("competition_bundle_path_unsafe")
            relative = path.relative_to(resolved).as_posix()
            files[relative] = path.read_bytes()
        return self.validate_files(files)

    def build(self, source_dir: str | Path, metadata: Mapping[str, Any]) -> bytes:
        source = Path(source_dir)
        if source.is_symlink() or not source.is_dir():
            raise CompetitionBundleError("competition_source_invalid")
        source = source.resolve()
        deck_path = source / "deck.csv"
        src_root = source / "src"
        resources_root = source / "resources"
        if deck_path.is_symlink() or not deck_path.is_file() or src_root.is_symlink() or not src_root.is_dir():
            raise CompetitionBundleError("competition_source_file_set_invalid")
        files: dict[str, bytes] = {"deck.csv": _canonical_project_text(deck_path.read_bytes(), "ascii")}
        for root, prefix in ((src_root, "src"), (resources_root, "resources")):
            if root == resources_root and not root.exists():
                continue
            if root.is_symlink() or not root.is_dir():
                raise CompetitionBundleError("competition_source_file_set_invalid")
            for path in root.rglob("*"):
                if path.is_symlink():
                    raise CompetitionBundleError("competition_bundle_path_unsafe")
                if path.is_dir():
                    continue
                if not path.is_file():
                    raise CompetitionBundleError("competition_bundle_path_unsafe")
                relative = f"{prefix}/{path.relative_to(root).as_posix()}"
                body = path.read_bytes()
                if relative.startswith("src/") or path.suffix.casefold() in {".csv", ".json", ".txt"}:
                    body = _canonical_project_text(body, "utf-8")
                files[relative] = body
        self._validate_paths(tuple(files))
        content = self._build_content_manifest(files)
        content_bytes = canonical_json_bytes(content)
        files["content-manifest.json"] = content_bytes
        files["runtime-lock.json"] = self.runtime_lock_bytes
        deck_cards = self._validate_deck(files["deck.csv"])
        manifest = self._build_manifest(metadata, files, content, deck_cards)
        files["manifest.json"] = canonical_json_bytes(manifest)
        archive = _canonical_zip(files, self.profile)
        self.validate(archive)
        return archive

    def extract(self, handle: CompetitionReleaseHandle, destination: str | Path) -> None:
        if type(handle) is not CompetitionReleaseHandle:
            raise CompetitionBundleError("competition_bundle_handle_invalid")
        if handle.archive_bytes:
            rebound = self.validate(handle.archive_bytes)
            if rebound.archive_sha256 != handle.archive_sha256:
                raise CompetitionBundleError("competition_bundle_handle_invalid")
        target = Path(destination)
        if target.exists() or target.is_symlink() or not target.parent.is_dir():
            raise CompetitionBundleError("competition_bundle_extract_target_invalid")
        target.mkdir()
        try:
            for name in handle.paths:
                path = target.joinpath(*name.split("/"))
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as stream:
                    stream.write(handle.file_bytes(name))
        except BaseException:
            _remove_created_tree(target)
            raise

    def _validate_files(
        self, files: Mapping[str, bytes], *, archive_bytes: bytes
    ) -> CompetitionReleaseHandle:
        copied = self._copy_file_mapping(files)
        self._validate_paths(tuple(copied))
        if "manifest.json" not in copied:
            raise CompetitionBundleError("competition_archive_file_set_invalid")
        manifest = _strict_canonical_json(
            copied["manifest.json"], self._limit("max_manifest_bytes"), "competition_manifest_invalid"
        )
        if type(manifest) is not dict:
            raise CompetitionBundleError("competition_manifest_invalid")
        dispatch = (manifest.get("document_type"), manifest.get("schema_version"))
        if dispatch == ("ptcgdap_competition_strategy_v1", 1):
            return self._validate_v1(copied, manifest, archive_bytes)
        if dispatch == ("ptcgdap_competition_strategy_v2", 2):
            return self._validate_v2(copied, manifest, archive_bytes)
        raise CompetitionBundleError("competition_bundle_dispatch_invalid")

    def _validate_v2(
        self, files: dict[str, bytes], manifest: dict[str, Any], archive_bytes: bytes
    ) -> CompetitionReleaseHandle:
        if set(manifest) != _MANIFEST_V2_KEYS:
            raise CompetitionBundleError("competition_manifest_invalid")
        identity = manifest["identity"]
        deck = manifest["deck"]
        runtime = manifest["runtime"]
        compatibility = manifest["compatibility"]
        qualification = manifest["qualification"]
        if type(identity) is not dict or set(identity) != _IDENTITY_KEYS:
            raise CompetitionBundleError("competition_identity_invalid")
        if not _identifier(identity["strategy_id"]) or not _identifier(identity["author_id"]):
            raise CompetitionBundleError("competition_identity_invalid")
        if type(identity["release_version"]) is not str or not _VERSION_RE.fullmatch(identity["release_version"]):
            raise CompetitionBundleError("competition_version_invalid")
        if not _text(identity["display_name"], 120) or not _text(identity["summary"], 2000):
            raise CompetitionBundleError("competition_metadata_invalid")
        if type(deck) is not dict or set(deck) != _DECK_KEYS:
            raise CompetitionBundleError("competition_deck_manifest_invalid")
        if (
            deck["path"] != "deck.csv"
            or deck["card_count"] != 60
            or deck["card_id_domain"] != "official_cabt_card_id"
            or not _identifier(deck["deck_id"])
            or not _identifier(deck["archetype_id"])
            or not _text(deck["display_name"], 120)
            or deck["sha256"] != _sha256(files.get("deck.csv", b""))
        ):
            raise CompetitionBundleError("competition_deck_manifest_invalid")
        deck_cards = self._validate_deck(files.get("deck.csv", b""))
        if type(runtime) is not dict or set(runtime) != _RUNTIME_KEYS:
            raise CompetitionBundleError("competition_runtime_manifest_invalid")
        lock = _strict_canonical_json(
            files.get("runtime-lock.json", b""), self._limit("max_manifest_bytes"), "competition_runtime_lock_invalid"
        )
        if files.get("runtime-lock.json") != self.runtime_lock_bytes or lock != self.runtime_lock:
            raise CompetitionBundleError("competition_runtime_lock_mismatch")
        content = _strict_canonical_json(
            files.get("content-manifest.json", b""), self._limit("max_manifest_bytes"), "competition_content_manifest_invalid"
        )
        source_hash, resource_hash = self._validate_content_manifest(content, files)
        if (
            runtime["kind"] != "cabt_python_agent_v2"
            or runtime["entrypoint"] != "submission.main:agent"
            or runtime["runtime_lock_path"] != "runtime-lock.json"
            or runtime["runtime_lock_sha256"] != self.runtime_lock_sha256
            or runtime["content_manifest_path"] != "content-manifest.json"
            or runtime["content_manifest_sha256"] != _sha256(files["content-manifest.json"])
            or runtime["source_manifest_sha256"] != source_hash
            or runtime["resource_manifest_sha256"] != resource_hash
            or runtime["runtime_profile_id"] != self.runtime_lock["runtime_profile_id"]
            or runtime["runtime_profile_sha256"] != self.profile_sha256
            or runtime["python_abi"] != self.runtime_lock["platform"]["python_abi"]
            or runtime["sdk_contract_sha256"] != self.runtime_lock["sdk"]["contract_sha256"]
        ):
            raise CompetitionBundleError("competition_runtime_manifest_invalid")
        self._validate_compatibility(compatibility)
        profile = self.profile["qualification_profile"]
        if (
            type(qualification) is not dict
            or set(qualification) != _QUALIFICATION_KEYS
            or qualification["profile_id"] != profile["profile_id"]
            or qualification["profile_sha256"] != profile["profile_sha256"]
            or qualification["deterministic_replay_required"] is not True
        ):
            raise CompetitionBundleError("competition_qualification_manifest_invalid")
        main = files.get("src/submission/main.py", b"")
        self._validate_sources(files)
        metadata = {
            **identity,
            "deck": dict(deck),
            "runtime": dict(runtime),
            "compatibility": dict(compatibility),
            "qualification": dict(qualification),
        }
        return self._handle(
            archive_bytes,
            files,
            manifest,
            2,
            "cabt_python_agent_v2",
            _sha256(main),
            _sha256(files["deck.csv"]),
            deck_cards,
            metadata,
        )

    def _validate_v1(
        self, files: dict[str, bytes], manifest: dict[str, Any], archive_bytes: bytes
    ) -> CompetitionReleaseHandle:
        if set(files) != _V1_FILES:
            raise CompetitionBundleError("competition_archive_file_set_invalid")
        required = {
            "document_type", "schema_version", "strategy_id", "release_version", "author_id",
            "display_name", "summary", "deck", "runtime", "compatibility",
        }
        if set(manifest) != required:
            raise CompetitionBundleError("competition_manifest_invalid")
        if not _identifier(manifest["strategy_id"]) or not _identifier(manifest["author_id"]):
            raise CompetitionBundleError("competition_identity_invalid")
        if type(manifest["release_version"]) is not str or not _VERSION_RE.fullmatch(manifest["release_version"]):
            raise CompetitionBundleError("competition_version_invalid")
        deck = manifest["deck"]
        runtime = manifest["runtime"]
        compatibility = manifest["compatibility"]
        if (
            type(deck) is not dict
            or set(deck) != {"deck_id", "archetype_id", "display_name", "path", "sha256"}
            or deck["path"] != "deck.csv"
            or deck["sha256"] != _sha256(files["deck.csv"])
        ):
            raise CompetitionBundleError("competition_deck_manifest_invalid")
        if (
            type(runtime) is not dict
            or set(runtime) != {"kind", "entrypoint", "sha256"}
            or runtime["kind"] != "cabt_python_agent_v1"
            or runtime["entrypoint"] != "main.py"
            or runtime["sha256"] != _sha256(files["main.py"])
        ):
            raise CompetitionBundleError("competition_runtime_manifest_invalid")
        if (
            type(compatibility) is not dict
            or set(compatibility) != {"environment", "engine_family", "observation_contract_sha256"}
            or compatibility["environment"] != "cabt"
            or compatibility["engine_family"] != "official_cabt"
            or not _sha256_value(compatibility["observation_contract_sha256"])
        ):
            raise CompetitionBundleError("competition_compatibility_invalid")
        deck_cards = self._validate_deck_v1(files["deck.csv"])
        self._validate_agent_source(files["main.py"], "main.py", require_entrypoint=True)
        return self._handle(
            archive_bytes,
            files,
            manifest,
            1,
            "cabt_python_agent_v1",
            _sha256(files["main.py"]),
            _sha256(files["deck.csv"]),
            deck_cards,
            dict(manifest),
        )

    def _validate_content_manifest(
        self, value: Any, files: Mapping[str, bytes]
    ) -> tuple[str, str]:
        if (
            type(value) is not dict
            or set(value) != {"document_type", "schema_version", "files"}
            or value["document_type"] != "ptcgdap_competition_content_manifest_v2"
            or value["schema_version"] != 2
            or type(value["files"]) is not list
        ):
            raise CompetitionBundleError("competition_content_manifest_invalid")
        items = value["files"]
        paths = [item.get("path") if type(item) is dict else None for item in items]
        if paths != sorted(paths, key=lambda item: item.encode("utf-8") if type(item) is str else b""):
            raise CompetitionBundleError("competition_content_manifest_invalid")
        expected = set(files) - _ROOT_FILES
        if set(paths) != expected or len(paths) != len(set(paths)):
            raise CompetitionBundleError("competition_content_closure_mismatch")
        source_items: list[dict[str, Any]] = []
        resource_items: list[dict[str, Any]] = []
        for item in items:
            if type(item) is not dict or set(item) != _CONTENT_ITEM_KEYS:
                raise CompetitionBundleError("competition_content_manifest_invalid")
            path = item["path"]
            body = files[path]
            if item["sha256"] != _sha256(body) or item["bytes"] != len(body):
                raise CompetitionBundleError("competition_content_hash_mismatch")
            expected_item = self._content_item(path, body)
            if item != expected_item:
                raise CompetitionBundleError("competition_content_manifest_invalid")
            if path.startswith("src/"):
                source_items.append(item)
            else:
                resource_items.append(item)
        return _manifest_partition_hash("source", source_items), _manifest_partition_hash("resource", resource_items)

    def _build_content_manifest(self, files: Mapping[str, bytes]) -> dict[str, Any]:
        items = [
            self._content_item(path, files[path])
            for path in sorted(files, key=lambda value: value.encode("utf-8"))
            if path.startswith("src/") or path.startswith("resources/")
        ]
        return {
            "document_type": "ptcgdap_competition_content_manifest_v2",
            "schema_version": 2,
            "files": items,
        }

    def _content_item(self, path: str, body: bytes) -> dict[str, Any]:
        if path.startswith("src/"):
            if not path.endswith(".py"):
                raise CompetitionBundleError("competition_source_type_forbidden")
            return {
                "path": path,
                "sha256": _sha256(body),
                "bytes": len(body),
                "kind": "python_source",
                "media_type": "text/x-python",
                "loader_capability": "python_source_utf8_v1",
                "executable": True,
            }
        if not path.startswith("resources/"):
            raise CompetitionBundleError("competition_content_manifest_invalid")
        suffix = PurePosixPath(path).suffix.casefold()
        media = self.profile["resources"]["allowed_media_types"].get(suffix)
        loader = self.profile["resources"]["loader_capabilities"].get(suffix)
        if type(media) is not str or type(loader) is not str:
            raise CompetitionBundleError("competition_resource_type_forbidden")
        self._validate_resource(path, body, suffix)
        return {
            "path": path,
            "sha256": _sha256(body),
            "bytes": len(body),
            "kind": "resource",
            "media_type": media,
            "loader_capability": loader,
            "executable": False,
        }

    def _build_manifest(
        self,
        metadata: Mapping[str, Any],
        files: Mapping[str, bytes],
        content: Mapping[str, Any],
        deck_cards: tuple[int, ...],
    ) -> dict[str, Any]:
        required = {
            "strategy_id", "release_version", "author_id", "display_name", "summary",
            "deck_id", "archetype_id", "deck_display_name", "engine_build_sha256",
            "observation_contract_sha256", "card_catalog_sha256", "required_capabilities",
            "qualification_profile_id", "qualification_profile_sha256",
        }
        if type(metadata) is not dict or set(metadata) != required:
            raise CompetitionBundleError("competition_metadata_invalid")
        content_items = content["files"]
        source_items = [item for item in content_items if item["kind"] == "python_source"]
        resource_items = [item for item in content_items if item["kind"] == "resource"]
        return {
            "document_type": "ptcgdap_competition_strategy_v2",
            "schema_version": 2,
            "identity": {
                "strategy_id": metadata["strategy_id"],
                "release_version": metadata["release_version"],
                "author_id": metadata["author_id"],
                "display_name": metadata["display_name"],
                "summary": metadata["summary"],
            },
            "deck": {
                "path": "deck.csv",
                "sha256": _sha256(files["deck.csv"]),
                "card_count": len(deck_cards),
                "card_id_domain": "official_cabt_card_id",
                "deck_id": metadata["deck_id"],
                "archetype_id": metadata["archetype_id"],
                "display_name": metadata["deck_display_name"],
            },
            "runtime": {
                "kind": "cabt_python_agent_v2",
                "entrypoint": "submission.main:agent",
                "runtime_lock_path": "runtime-lock.json",
                "runtime_lock_sha256": self.runtime_lock_sha256,
                "content_manifest_path": "content-manifest.json",
                "content_manifest_sha256": _sha256(canonical_json_bytes(content)),
                "source_manifest_sha256": _manifest_partition_hash("source", source_items),
                "resource_manifest_sha256": _manifest_partition_hash("resource", resource_items),
                "runtime_profile_id": self.runtime_lock["runtime_profile_id"],
                "runtime_profile_sha256": self.profile_sha256,
                "python_abi": self.runtime_lock["platform"]["python_abi"],
                "sdk_contract_sha256": self.runtime_lock["sdk"]["contract_sha256"],
            },
            "compatibility": {
                "environment": "cabt",
                "engine_family": "official_cabt",
                "engine_build_sha256": metadata["engine_build_sha256"],
                "observation_contract_sha256": metadata["observation_contract_sha256"],
                "card_catalog_sha256": metadata["card_catalog_sha256"],
                "required_capabilities": (
                    sorted(metadata["required_capabilities"])
                    if type(metadata["required_capabilities"]) is list
                    else metadata["required_capabilities"]
                ),
            },
            "qualification": {
                "profile_id": metadata["qualification_profile_id"],
                "profile_sha256": metadata["qualification_profile_sha256"],
                "deterministic_replay_required": True,
            },
        }

    def _validate_compatibility(self, value: Any) -> None:
        if (
            type(value) is not dict
            or set(value) != _COMPATIBILITY_KEYS
            or value["environment"] != "cabt"
            or value["engine_family"] != "official_cabt"
            or any(
                not _sha256_value(value[field])
                for field in ("engine_build_sha256", "observation_contract_sha256", "card_catalog_sha256")
            )
            or type(value["required_capabilities"]) is not list
            or any(not _identifier(item) for item in value["required_capabilities"])
            or len(value["required_capabilities"]) != len(set(value["required_capabilities"]))
            or value["required_capabilities"] != sorted(value["required_capabilities"])
        ):
            raise CompetitionBundleError("competition_compatibility_invalid")

    def _validate_sources(self, files: Mapping[str, bytes]) -> None:
        source_paths = sorted(path for path in files if path.startswith("src/"))
        required = set(self.profile["required_source_files"])
        if not required.issubset(source_paths):
            raise CompetitionBundleError("competition_source_file_set_invalid")
        source_total = 0
        reserved = {name.casefold() for name in self.profile["source"]["reserved_top_level_modules"]}
        forbidden_suffixes = tuple(self.profile["source"]["forbidden_suffixes"])
        for path in source_paths:
            body = files[path]
            source_total += len(body)
            if len(body) > self._limit("max_source_file_bytes") or source_total > self._limit("max_source_total_bytes"):
                raise CompetitionBundleError("competition_source_size_invalid")
            parts = path.split("/")
            top = parts[1].removesuffix(".py").casefold() if len(parts) > 1 else ""
            basename = parts[-1].removesuffix(".py").casefold()
            if top in reserved or basename in {"sitecustomize", "usercustomize"}:
                raise CompetitionBundleError("competition_source_module_reserved")
            if not path.endswith(".py") or any(path.casefold().endswith(suffix) for suffix in forbidden_suffixes):
                raise CompetitionBundleError("competition_source_type_forbidden")
            self._validate_agent_source(body, path, require_entrypoint=path == "src/submission/main.py")

    def _validate_agent_source(self, source: bytes, path: str, *, require_entrypoint: bool) -> None:
        try:
            text = source.decode("utf-8", errors="strict")
            if text.startswith("\ufeff") or "\x00" in text:
                raise ValueError
            tree = ast.parse(text, filename=path, mode="exec")
        except (UnicodeDecodeError, SyntaxError, ValueError) as error:
            raise CompetitionBundleError("competition_source_invalid") from error
        if not require_entrypoint:
            return
        definitions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "agent"]
        if len(definitions) != 1 or not isinstance(definitions[0], ast.FunctionDef):
            raise CompetitionBundleError("competition_agent_entrypoint_invalid")
        function = definitions[0]
        if any(isinstance(node, (ast.Yield, ast.YieldFrom)) for node in ast.walk(function)):
            raise CompetitionBundleError("competition_agent_entrypoint_invalid")
        if len(function.args.args) != 1 or function.args.vararg is not None or function.args.kwarg is not None:
            raise CompetitionBundleError("competition_agent_entrypoint_invalid")

    def _validate_resource(self, path: str, body: bytes, suffix: str) -> None:
        if len(body) > self._limit("max_resource_file_bytes"):
            raise CompetitionBundleError("competition_resource_size_invalid")
        if suffix in {".json", ".csv", ".txt"}:
            try:
                text = body.decode("utf-8", errors="strict")
            except UnicodeDecodeError as error:
                raise CompetitionBundleError("competition_resource_invalid") from error
            if text.startswith("\ufeff") or "\x00" in text:
                raise CompetitionBundleError("competition_resource_invalid")
            if suffix == ".json":
                value = _strict_canonical_json(body, self._limit("max_resource_file_bytes"), "competition_resource_invalid")
                canonical_json_bytes(value)
            return
        if suffix == ".npy":
            _validate_npy(body)
            return
        raise CompetitionBundleError("competition_resource_type_forbidden")

    def _validate_deck(self, body: bytes) -> tuple[int, ...]:
        if not body or len(body) > self._limit("max_deck_bytes"):
            raise CompetitionBundleError("competition_deck_invalid")
        try:
            text = body.decode("ascii", errors="strict")
        except UnicodeDecodeError as error:
            raise CompetitionBundleError("competition_deck_invalid") from error
        if "\r" in text or not text.endswith("\n"):
            raise CompetitionBundleError("competition_deck_invalid")
        lines = text[:-1].split("\n")
        if len(lines) != 60 or any(not line or not line.isdecimal() or not line.isascii() for line in lines):
            raise CompetitionBundleError("competition_deck_invalid")
        cards = tuple(int(line) for line in lines)
        if any(card < 1 or card > 2**31 - 1 for card in cards):
            raise CompetitionBundleError("competition_deck_invalid")
        return cards

    @staticmethod
    def _validate_deck_v1(body: bytes) -> tuple[int, ...]:
        try:
            lines = body.decode("ascii", errors="strict").splitlines()
        except UnicodeDecodeError as error:
            raise CompetitionBundleError("competition_deck_invalid") from error
        if len(lines) != 60 or any(not line or not line.isascii() or not line.isdigit() for line in lines):
            raise CompetitionBundleError("competition_deck_invalid")
        cards = tuple(int(line) for line in lines)
        if any(card < 1 or card > 2**31 - 1 for card in cards):
            raise CompetitionBundleError("competition_deck_invalid")
        return cards

    def _validate_paths(self, paths: tuple[str, ...]) -> None:
        if not paths or len(paths) > self._limit("max_file_count"):
            raise CompetitionBundleError("competition_archive_file_set_invalid")
        seen: set[str] = set()
        for path in paths:
            if type(path) is not str or not _safe_path(path, self._limit("max_path_bytes")):
                raise CompetitionBundleError("competition_archive_path_unsafe")
            folded = unicodedata.normalize("NFC", path).casefold()
            if folded in seen:
                raise CompetitionBundleError("competition_archive_path_collision")
            seen.add(folded)

    def _read_canonical_archive(self, body: bytes) -> dict[str, bytes]:
        try:
            files = _parse_stored_zip(body, self.profile, self._limit("max_file_count"), self._limit("max_uncompressed_bytes"))
            self._validate_paths(tuple(files))
            if _canonical_zip(files, self.profile) != body:
                raise CompetitionBundleError("competition_archive_noncanonical")
            return files
        except CompetitionBundleError:
            raise
        except (KeyError, UnicodeError, ValueError, struct.error, binascii.Error) as error:
            raise CompetitionBundleError("competition_archive_invalid") from error

    def _read_legacy_v1_archive(
        self, body: bytes, canonical_error: CompetitionBundleError
    ) -> dict[str, bytes]:
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                infos = archive.infolist()
                if len(infos) != 3:
                    raise canonical_error
                files: dict[str, bytes] = {}
                total = 0
                for info in infos:
                    mode = (info.external_attr >> 16) & 0o170000
                    if (
                        info.is_dir()
                        or info.filename not in _V1_FILES
                        or info.filename in files
                        or info.flag_bits & 0x1
                        or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                        or mode == 0o120000
                    ):
                        raise canonical_error
                    total += info.file_size
                    if total > self._limit("max_uncompressed_bytes"):
                        raise CompetitionBundleError("competition_archive_expansion_limit")
                    files[info.filename] = archive.read(info)
        except CompetitionBundleError:
            raise
        except Exception as error:
            raise CompetitionBundleError("competition_archive_invalid") from error
        if set(files) != _V1_FILES:
            raise canonical_error
        try:
            manifest = _strict_canonical_json(
                files["manifest.json"], self._limit("max_manifest_bytes"), "competition_manifest_invalid"
            )
        except CompetitionBundleError:
            raise canonical_error
        if (
            type(manifest) is not dict
            or manifest.get("document_type") != "ptcgdap_competition_strategy_v1"
            or manifest.get("schema_version") != 1
        ):
            raise canonical_error
        return files

    def _copy_file_mapping(self, files: Mapping[str, bytes]) -> dict[str, bytes]:
        if not isinstance(files, Mapping):
            raise CompetitionBundleError("competition_archive_invalid")
        copied: dict[str, bytes] = {}
        for path, body in files.items():
            if type(path) is not str or type(body) is not bytes or path in copied:
                raise CompetitionBundleError("competition_archive_invalid")
            copied[path] = bytes(body)
        return copied

    def _handle(
        self,
        archive_bytes: bytes,
        files: Mapping[str, bytes],
        manifest: dict[str, Any],
        schema_generation: int,
        runtime_kind: str,
        main_sha256: str,
        deck_sha256: str,
        deck_cards: tuple[int, ...],
        metadata: dict[str, Any],
    ) -> CompetitionReleaseHandle:
        archive_sha = _sha256(archive_bytes) if archive_bytes else _sha256(_canonical_zip(files, self.profile))
        return CompetitionReleaseHandle(
            archive_bytes=bytes(archive_bytes),
            archive_sha256=archive_sha,
            schema_generation=schema_generation,
            canonical_zip_profile_generation=(
                self.profile["canonical_zip_profile_generation"] if schema_generation == 2 else 0
            ),
            manifest=json.loads(json.dumps(manifest)),
            manifest_canonical_sha256=_sha256(canonical_json_bytes(manifest)),
            runtime_kind=runtime_kind,
            main_sha256=main_sha256,
            deck_sha256=deck_sha256,
            deck_cards=tuple(deck_cards),
            paths=tuple(sorted(files, key=lambda value: value.encode("utf-8"))),
            metadata=json.loads(json.dumps(metadata)),
            _files=MappingProxyType({path: bytes(value) for path, value in files.items()}),
        )

    def _limit(self, name: str) -> int:
        value = self.profile["limits"].get(name)
        if type(value) is not int or value < 1:
            raise CompetitionBundleError("competition_bundle_contract_invalid")
        return value

    def _validate_profile(self) -> None:
        try:
            qualification = self.profile["qualification_profile"]
            qualification_path = self.repository_root / qualification["path"]
            qualification_value = load_json_bytes_strict(qualification_path.read_bytes())
            rpc_path = (
                self.repository_root
                / "contracts/ptcgdap"
                / self.runtime_lock["rpc"]["contract"]
            )
            rpc_value = load_json_bytes_strict(rpc_path.read_bytes())
            a1_candidates = (
                self.repository_root / "evidence/ptcgdap/a1/scope_v2.json",
                self.repository_root / "contracts/ptcgdap/cabt_a1_scope_report_v2.json",
            )
            a1_values = [
                load_json_bytes_strict(path.read_bytes())
                for path in a1_candidates
                if path.is_file() and not path.is_symlink()
            ]
            sdk = self.runtime_lock["sdk"]
            valid = (
                self.profile["document_type"] == "ptcgdap_competition_bundle_profile_v2"
                and self.profile["schema_version"] == 2
                and self.profile["bundle_schema_generation"] == 2
                and self.profile["canonical_zip_profile_generation"] == 1
                and set(self.profile["required_root_files"]) == _ROOT_FILES
                and self.runtime_lock["document_type"] == "ptcgdap_competition_runtime_lock_v2"
                and self.runtime_lock["schema_version"] == 2
                and self.runtime_lock["authority"]["production_multi_tenant_isolation"] is False
                and self.runtime_lock["authority"]["official_engine_claim"] is False
                and qualification["profile_id"] == qualification_value["profile_id"]
                and qualification["profile_sha256"]
                == _sha256(canonical_json_bytes(qualification_value))
                and self.runtime_lock["rpc"]["contract_sha256"]
                == _sha256(canonical_json_bytes(rpc_value))
                and set(sdk) == {
                    "module", "contract_sha256", "distribution",
                    "a1_scope_sha256", "time_profile_sha256", "search_capability",
                }
                and sdk["search_capability"] == self.runtime_lock["capabilities"]["search"]
                and bool(a1_values)
                and all(
                    value.get("document_type") == "ptcgdap_a1_scope_report_v2"
                    and value.get("core_selection_interface_aligned") is True
                    and value.get("scope_sha256") == sdk["a1_scope_sha256"]
                    and value.get("search_capability") == sdk["search_capability"]
                    and value.get("time_profile", {}).get("profile_hash")
                    == sdk["time_profile_sha256"]
                    for value in a1_values
                )
            )
        except (KeyError, OSError, TypeError, ValueError):
            valid = False
        if not valid:
            raise CompetitionBundleError("competition_bundle_contract_invalid")


def _strict_canonical_json(body: bytes, maximum: int, code: str) -> Any:
    if type(body) is not bytes or not body or len(body) > maximum:
        raise CompetitionBundleError(code)
    try:
        value = load_json_bytes_strict(body)
    except (UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise CompetitionBundleError(code) from error
    if canonical_json_bytes(value) != body:
        raise CompetitionBundleError(code)
    return value


def _canonical_project_text(body: bytes, encoding: str) -> bytes:
    try:
        text = body.decode(encoding, errors="strict")
    except UnicodeDecodeError as error:
        raise CompetitionBundleError("competition_source_invalid") from error
    if text.startswith("\ufeff") or "\x00" in text:
        raise CompetitionBundleError("competition_source_invalid")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode(encoding)


def _manifest_partition_hash(kind: str, items: list[dict[str, Any]]) -> str:
    return _sha256(
        canonical_json_bytes(
            {"document_type": f"ptcgdap_competition_{kind}_manifest_v2", "schema_version": 2, "files": items}
        )
    )


def _safe_path(path: str, maximum_bytes: int) -> bool:
    try:
        encoded = path.encode("utf-8", errors="strict")
    except UnicodeError:
        return False
    if not encoded or len(encoded) > maximum_bytes or unicodedata.normalize("NFC", path) != path:
        return False
    if path.startswith(("/", "\\")) or "\\" in path or ":" in path or path.endswith("/"):
        return False
    if any(ord(character) < 32 or ord(character) == 127 for character in path):
        return False
    parts = path.split("/")
    if any(not part or part in {".", ".."} or part.endswith((".", " ")) for part in parts):
        return False
    if any(part.split(".", 1)[0].upper() in _WINDOWS_RESERVED for part in parts):
        return False
    return not PurePosixPath(path).is_absolute()


def _canonical_zip(files: Mapping[str, bytes], profile: Mapping[str, Any]) -> bytes:
    zip_profile = profile["canonical_zip"]
    flags = int(zip_profile["utf8_flag"])
    method = 0
    dos_time = int(zip_profile["dos_time"])
    dos_date = int(zip_profile["dos_date"])
    external_attr = int(zip_profile["regular_file_mode"]) << 16
    local_parts: list[bytes] = []
    central_parts: list[bytes] = []
    offset = 0
    ordered = sorted(files, key=lambda value: value.encode("utf-8"))
    for path in ordered:
        name = path.encode("utf-8")
        data = files[path]
        crc = binascii.crc32(data) & 0xFFFFFFFF
        local = struct.pack(
            "<IHHHHHIIIHH",
            0x04034B50,
            20,
            flags,
            method,
            dos_time,
            dos_date,
            crc,
            len(data),
            len(data),
            len(name),
            0,
        ) + name + data
        central = struct.pack(
            "<IHHHHHHIIIHHHHHII",
            0x02014B50,
            (3 << 8) | 20,
            20,
            flags,
            method,
            dos_time,
            dos_date,
            crc,
            len(data),
            len(data),
            len(name),
            0,
            0,
            0,
            0,
            external_attr,
            offset,
        ) + name
        local_parts.append(local)
        central_parts.append(central)
        offset += len(local)
    central = b"".join(central_parts)
    eocd = struct.pack(
        "<IHHHHIIH",
        0x06054B50,
        0,
        0,
        len(ordered),
        len(ordered),
        len(central),
        offset,
        0,
    )
    return b"".join(local_parts) + central + eocd


def _parse_stored_zip(
    body: bytes,
    profile: Mapping[str, Any],
    max_files: int,
    max_uncompressed: int,
) -> dict[str, bytes]:
    if len(body) < 22 or body[-22:-18] != b"PK\x05\x06":
        raise CompetitionBundleError("competition_archive_invalid")
    signature, disk, cd_disk, disk_count, total_count, cd_size, cd_offset, comment_len = struct.unpack_from(
        "<IHHHHIIH", body, len(body) - 22
    )
    if (
        signature != 0x06054B50
        or disk != 0
        or cd_disk != 0
        or disk_count != total_count
        or not 1 <= total_count <= max_files
        or comment_len != 0
        or cd_offset + cd_size != len(body) - 22
        or cd_offset >= len(body) - 22
    ):
        raise CompetitionBundleError("competition_archive_invalid")
    zip_profile = profile["canonical_zip"]
    expected_flags = int(zip_profile["utf8_flag"])
    expected_date = int(zip_profile["dos_date"])
    expected_time = int(zip_profile["dos_time"])
    expected_external = int(zip_profile["regular_file_mode"]) << 16
    cursor = cd_offset
    entries: list[tuple[str, int, int, int, int]] = []
    seen: set[str] = set()
    total = 0
    for _ in range(total_count):
        if cursor + 46 > cd_offset + cd_size:
            raise CompetitionBundleError("competition_archive_invalid")
        values = struct.unpack_from("<IHHHHHHIIIHHHHHII", body, cursor)
        (
            sig, made, needed, flags, method, mtime, mdate, crc, compressed, uncompressed,
            name_len, extra_len, file_comment_len, start_disk, internal_attr, external_attr, local_offset,
        ) = values
        cursor += 46
        if cursor + name_len + extra_len + file_comment_len > cd_offset + cd_size:
            raise CompetitionBundleError("competition_archive_invalid")
        name_bytes = body[cursor : cursor + name_len]
        cursor += name_len + extra_len + file_comment_len
        try:
            name = name_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise CompetitionBundleError("competition_archive_path_unsafe") from error
        if (
            sig != 0x02014B50
            or made != (3 << 8) | 20
            or needed != 20
            or flags != expected_flags
            or method != 0
            or mtime != expected_time
            or mdate != expected_date
            or compressed != uncompressed
            or extra_len != 0
            or file_comment_len != 0
            or start_disk != 0
            or internal_attr != 0
            or external_attr != expected_external
            or name in seen
        ):
            raise CompetitionBundleError("competition_archive_noncanonical")
        seen.add(name)
        total += uncompressed
        if total > max_uncompressed:
            raise CompetitionBundleError("competition_archive_expansion_limit")
        entries.append((name, local_offset, crc, compressed, uncompressed))
    if cursor != cd_offset + cd_size:
        raise CompetitionBundleError("competition_archive_invalid")
    files: dict[str, bytes] = {}
    local_cursor = 0
    for name, local_offset, crc, compressed, uncompressed in entries:
        if local_offset != local_cursor or local_offset + 30 > cd_offset:
            raise CompetitionBundleError("competition_archive_overlap")
        values = struct.unpack_from("<IHHHHHIIIHH", body, local_offset)
        sig, needed, flags, method, mtime, mdate, local_crc, local_compressed, local_uncompressed, name_len, extra_len = values
        name_start = local_offset + 30
        data_start = name_start + name_len + extra_len
        data_end = data_start + local_compressed
        if (
            sig != 0x04034B50
            or needed != 20
            or flags != expected_flags
            or method != 0
            or mtime != expected_time
            or mdate != expected_date
            or local_crc != crc
            or local_compressed != compressed
            or local_uncompressed != uncompressed
            or extra_len != 0
            or data_end > cd_offset
            or body[name_start : name_start + name_len] != name.encode("utf-8")
        ):
            raise CompetitionBundleError("competition_archive_local_header_mismatch")
        data = body[data_start:data_end]
        if (binascii.crc32(data) & 0xFFFFFFFF) != crc:
            raise CompetitionBundleError("competition_archive_crc_invalid")
        files[name] = data
        local_cursor = data_end
    if local_cursor != cd_offset:
        raise CompetitionBundleError("competition_archive_overlap")
    return files


def _validate_npy(body: bytes) -> None:
    if len(body) < 10 or not body.startswith(b"\x93NUMPY"):
        raise CompetitionBundleError("competition_resource_invalid")
    major, minor = body[6], body[7]
    if (major, minor) == (1, 0):
        header_len = struct.unpack_from("<H", body, 8)[0]
        offset = 10
    elif (major, minor) in {(2, 0), (3, 0)}:
        header_len = struct.unpack_from("<I", body, 8)[0]
        offset = 12
    else:
        raise CompetitionBundleError("competition_resource_invalid")
    if header_len < 1 or offset + header_len > len(body) or header_len > 65536:
        raise CompetitionBundleError("competition_resource_invalid")
    try:
        header = ast.literal_eval(body[offset : offset + header_len].decode("latin1").strip())
    except (SyntaxError, ValueError) as error:
        raise CompetitionBundleError("competition_resource_invalid") from error
    if type(header) is not dict or set(header) != {"descr", "fortran_order", "shape"}:
        raise CompetitionBundleError("competition_resource_invalid")
    descriptor = header["descr"]
    match = re.fullmatch(r"[<>=|]?([biufc])(\d{1,2})", descriptor) if type(descriptor) is str else None
    if match is None or type(header["fortran_order"]) is not bool or type(header["shape"]) is not tuple:
        raise CompetitionBundleError("competition_resource_invalid")
    item_size = int(match.group(2))
    if item_size not in {1, 2, 4, 8, 16} or any(type(value) is not int or value < 0 for value in header["shape"]):
        raise CompetitionBundleError("competition_resource_invalid")
    count = 1
    for dimension in header["shape"]:
        count *= dimension
        if count > 16_777_216:
            raise CompetitionBundleError("competition_resource_size_invalid")
    if offset + header_len + count * item_size != len(body):
        raise CompetitionBundleError("competition_resource_invalid")


def _remove_created_tree(root: Path) -> None:
    if not root.exists() or root.is_symlink():
        return
    for path in sorted(root.rglob("*"), key=lambda value: len(value.parts), reverse=True):
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            path.rmdir()
    root.rmdir()


def _identifier(value: object) -> bool:
    return type(value) is str and _IDENTIFIER_RE.fullmatch(value) is not None


def _text(value: object, maximum: int) -> bool:
    return type(value) is str and 1 <= len(value) <= maximum and "\x00" not in value


def _sha256_value(value: object) -> bool:
    return type(value) is str and _SHA256_RE.fullmatch(value) is not None


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest().upper()


__all__ = [
    "CompetitionBundleError",
    "CompetitionBundleOwner",
    "CompetitionReleaseHandle",
    "canonical_json_bytes",
]
