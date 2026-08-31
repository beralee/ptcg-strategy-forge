"""Public developer SDK for the complete ``.ptcgai`` workspace lifecycle.

The SDK intentionally presents workspaces rather than individual package-tool
functions.  Existing low-level helpers remain available through the CLI for
automation compatibility, while new integrations can use one stable object.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Literal

from scripts.ai.ptcgdap.author_strategy_package import (
    CABT_CONTRACT_SHA256,
    CARD_CATALOG_SHA256,
)
from scripts.ai.ptcgdap.ptcgai_model_package import (
    build_model_manifest,
    canonical_bytes,
)
from scripts.ai.ptcgdap.ptcgai_model_actor import (
    ModelActorError,
    PublicActorTensorizer,
)
from scripts.ai.ptcgdap.cabt_envelope import parse_raw_cabt_envelope
from scripts.ai.ptcgdap.public_observation_firewall import PublicObservationFirewall
from tools.ptcgdap.author_strategy_developer import (
    DeveloperToolError,
    install_development_package,
    scaffold_workspace,
)

from .ptcgai_ort import (
    OrtActorError,
    conformance as model_conformance,
    import_onnx_to_ort,
    inspect_onnx,
    inspect_ort,
)
from .reviewed_decks import customize_reviewed_workspace
from .scenarios import generate_demo_scenarios, load_json, write_json


WorkspaceMode = Literal["rules", "model"]
_SAFE_COMPONENT = re.compile(r"[^a-z0-9-]+")
_PACKAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,47}$")
_PACKAGE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,47}$")
_ROOT = Path(__file__).resolve().parents[2]


class WorkspaceError(ValueError):
    """A fail-closed developer-workspace error with a stable public code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _raise(code: str) -> None:
    raise WorkspaceError(code)


def _slug(value: str) -> str:
    slug = _SAFE_COMPONENT.sub("-", value.casefold()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    if not slug:
        _raise("workspace_name_invalid")
    return slug


def _title(value: str) -> str:
    words = [word for word in re.split(r"[-_\s]+", value.strip()) if word]
    return " ".join(word[:1].upper() + word[1:] for word in words)


def _default_package_id(author_id: str, workspace_name: str) -> str:
    author = author_id.strip().strip(".")
    if not author or not _PACKAGE_ID.fullmatch(author):
        _raise("workspace_author_id_invalid")
    package_id = f"dev.{author}.{_slug(workspace_name)}"
    if not _PACKAGE_ID.fullmatch(package_id):
        _raise("workspace_package_id_required")
    return package_id


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _scenario_actor_context(document: dict[str, Any]) -> tuple[dict[str, Any], dict[int, str]]:
    """Project one strict developer scenario into the public Actor profile."""

    try:
        raw = document["raw_observation"]
        current = raw["current"]
        select = raw["select"]
        chooser = current["yourIndex"]
        opponent = 1 - chooser
        players = current["players"]
        context = {
            "clocks": {
                "turn": current["turn"],
                "turn_action_count": current["turnActionCount"],
                "remaining_overage_time": raw["remainingOverageTime"],
                "acting_prizes_remaining": len(players[chooser]["prize"]),
                "opponent_prizes_remaining": len(players[opponent]["prize"]),
                "acting_deck_count": players[chooser]["deckCount"],
                "opponent_deck_count": players[opponent]["deckCount"],
                "acting_hand_count": players[chooser]["handCount"],
                "opponent_hand_count": players[opponent]["handCount"],
            },
            "public_state": {
                "turn_flags": {
                    "first_player": current["firstPlayer"],
                    "result": current["result"],
                    "supporter_played": current["supporterPlayed"],
                    "stadium_played": current["stadiumPlayed"],
                    "energy_attached": current["energyAttached"],
                    "retreated": current["retreated"],
                }
            },
            "select_semantics": {
                "select_type_raw": select["type"],
                "select_context_raw": select["context"],
                "min_count": select["minCount"],
                "max_count": select["maxCount"],
                "remain_damage_counter": select["remainDamageCounter"],
                "remain_energy_cost": select["remainEnergyCost"],
                "options": [
                    {"index": index, "fingerprint": "0" * 64, "raw": option}
                    for index, option in enumerate(select["option"])
                ],
            },
        }
        local_uids = {
            row["index"]: row["local_card_uid"]
            for row in document["local_uid_bindings"]["options"]
            if row["local_card_uid"] is not None
        }
    except (IndexError, KeyError, TypeError) as error:
        raise WorkspaceError("workspace_scenario_invalid") from error
    return context, local_uids


@dataclass(frozen=True)
class StrategyWorkspace:
    """One Forge author workspace and its supported developer operations."""

    root: Path

    @classmethod
    def create(
        cls,
        path: str | Path,
        *,
        author_id: str,
        author_name: str | None = None,
        package_id: str | None = None,
        package_version: str = "0.1.0",
        strategy_name: str | None = None,
        summary: str | None = None,
        mode: WorkspaceMode = "rules",
        deck_id: int | None = None,
    ) -> "StrategyWorkspace":
        """Create a non-overwriting workspace using convention-based defaults."""

        output = Path(path)
        if mode not in {"rules", "model"}:
            _raise("workspace_mode_invalid")
        resolved_package_id = package_id or _default_package_id(author_id, output.name)
        if not _PACKAGE_ID.fullmatch(resolved_package_id):
            _raise("workspace_package_id_invalid")
        if not _PACKAGE_VERSION.fullmatch(package_version):
            _raise("workspace_package_version_invalid")
        resolved_author_name = author_name or author_id
        resolved_strategy_name = strategy_name or _title(output.name)

        try:
            if output.exists() or output.is_symlink():
                _raise("developer_output_exists")
            parent = output.parent.resolve(strict=True)
            target = parent / output.name
            with tempfile.TemporaryDirectory(
                prefix=f".{_slug(output.name)}-create-",
                dir=parent,
            ) as temp_name:
                staging = Path(temp_name) / "workspace"
                scaffold_workspace(staging)
                # These helpers own the current package-template transformation.
                # They are imported lazily so the public SDK stays independent from
                # argparse and the CLI can itself delegate to this class.
                from .cli import (  # pylint: disable=import-outside-toplevel
                    _configure_model_workspace,
                    _configure_rules_workspace,
                    _customize_workspace,
                    _write_workspace_guides,
                )

                _customize_workspace(
                    staging,
                    resolved_package_id,
                    package_version,
                    author_id,
                    resolved_author_name,
                    resolved_strategy_name,
                    summary,
                )
                _write_workspace_guides(staging)
                if deck_id is None:
                    generate_demo_scenarios(
                        staging,
                        matched_rule_id="marnie.morgrem.evolve",
                        scenario_namespace="workspace",
                    )
                else:
                    customize_reviewed_workspace(staging, deck_id, resolved_package_id)
                if mode == "model":
                    _configure_model_workspace(staging)
                else:
                    _configure_rules_workspace(staging)
                cls.open(staging)
                if target.exists() or target.is_symlink():
                    _raise("developer_output_exists")
                os.replace(staging, target)
        except WorkspaceError:
            raise
        except (DeveloperToolError, OrtActorError) as error:
            _raise(error.code)
        except (KeyError, OSError, TypeError, ValueError) as error:
            code = str(error)
            _raise(code if code and " " not in code else "workspace_create_failed")
        return cls.open(target)

    @classmethod
    def open(cls, path: str | Path) -> "StrategyWorkspace":
        """Open an existing workspace after checking its structural boundary."""

        candidate = Path(path)
        if candidate.is_symlink():
            _raise("workspace_path_invalid")
        try:
            root = candidate.resolve(strict=True)
        except OSError:
            _raise("workspace_missing")
        if not root.is_dir():
            _raise("workspace_path_invalid")
        manifest_path = root / "package/strategy_package.json"
        if not manifest_path.is_file():
            _raise("workspace_manifest_missing")
        try:
            manifest = load_json(manifest_path)
        except (OSError, UnicodeError, ValueError):
            _raise("workspace_manifest_invalid")
        package_id = manifest.get("package_id")
        package_version = manifest.get("package_version")
        if (
            manifest.get("document_type")
            not in {"strategy_package_v1", "strategy_package_v2"}
            or not isinstance(package_id, str)
            or not _PACKAGE_ID.fullmatch(package_id)
            or not isinstance(package_version, str)
            or not _PACKAGE_VERSION.fullmatch(package_version)
        ):
            _raise("workspace_manifest_invalid")
        return cls(root)

    @property
    def manifest_path(self) -> Path:
        return self.root / "package/strategy_package.json"

    @property
    def manifest(self) -> dict[str, Any]:
        try:
            document = load_json(self.manifest_path)
        except (OSError, UnicodeError, ValueError):
            _raise("workspace_manifest_invalid")
        if not isinstance(document, dict):
            _raise("workspace_manifest_invalid")
        return document

    @property
    def package_id(self) -> str:
        value = self.manifest.get("package_id")
        if not isinstance(value, str) or not value:
            _raise("workspace_manifest_invalid")
        return value

    @property
    def package_version(self) -> str:
        value = self.manifest.get("package_version")
        if not isinstance(value, str) or not value:
            _raise("workspace_manifest_invalid")
        return value

    @property
    def strategy_name(self) -> str:
        value = self.manifest.get("strategy", {}).get("display_name")
        if not isinstance(value, str) or not value:
            _raise("workspace_manifest_invalid")
        return value

    @property
    def policy_mode(self) -> str:
        value = self.manifest.get("policy", {}).get("policy_mode", "rules_only")
        if value not in {"rules_only", "rules_with_model"}:
            _raise("workspace_policy_mode_invalid")
        return str(value)

    @property
    def default_artifact(self) -> Path:
        filename = f"{self.package_id}-{self.package_version}.ptcgai"
        return self.root / "build" / filename

    @property
    def default_report(self) -> Path:
        return self.root / "build/workspace-check.json"

    @property
    def model(self) -> "WorkspaceModel":
        if self.policy_mode != "rules_with_model":
            _raise("workspace_model_not_enabled")
        return WorkspaceModel(self)

    def status(self) -> dict[str, object]:
        """Return a concise, non-mutating developer readiness report."""

        suite_path = self.root / "scenario-suite.json"
        scenarios_root = self.root / "scenarios"
        suite_cases: list[object] = []
        issues: list[str] = []
        try:
            suite = load_json(suite_path)
            raw_cases = suite.get("cases", [])
            if isinstance(raw_cases, list):
                suite_cases = raw_cases
            else:
                issues.append("workspace_scenario_suite_invalid")
        except (OSError, UnicodeError, ValueError):
            issues.append("workspace_scenario_suite_invalid")

        required = [
            self.root / "package/policy/adapter.json",
            self.root / "package/policy/policy_ir.json",
            self.root / "STRATEGY-BLUEPRINT.md",
            suite_path,
        ]
        if self.policy_mode == "rules_with_model":
            required.extend(
                [
                    self.root / "package/model/actor.ort",
                    self.root / "package/model/model_manifest.json",
                ]
            )
        for path in required:
            if not path.is_file():
                issues.append(f"workspace_required_file_missing:{_relative(self.root, path)}")

        model_status: dict[str, object] = {"required": False, "status": "not_applicable"}
        if self.policy_mode == "rules_with_model":
            try:
                conformance = self.model.conformance()
                model_status = {
                    "required": True,
                    "status": "ready" if conformance.get("status") == "passed" else "failed",
                    "conformance_status": conformance.get("status", "failed"),
                }
                if conformance.get("status") != "passed":
                    issues.append("workspace_model_conformance_failed")
            except (WorkspaceError, OrtActorError):
                model_status = {"required": True, "status": "failed"}
                issues.append("workspace_model_conformance_failed")

        root_text = str(self.root)
        next_actions = [
            {
                "action": "status",
                "command": f'python forge.py workspace status "{root_text}"',
            },
            {
                "action": "inspect",
                "command": f'python forge.py workspace inspect "{root_text}"',
            },
            {
                "action": "check",
                "command": f'python forge.py workspace check "{root_text}"',
            },
            {
                "action": "build",
                "command": f'python forge.py workspace build "{root_text}"',
            },
            {
                "action": "install",
                "command": f'python forge.py workspace install "{root_text}"',
            },
        ]
        return {
            "document_type": "ptcg_strategy_forge_workspace_status_v1",
            "schema_version": 1,
            "status": "ready" if not issues else "needs_attention",
            "workspace": str(self.root),
            "package": {
                "package_id": self.package_id,
                "package_version": self.package_version,
                "strategy_name": self.strategy_name,
                "policy_mode": self.policy_mode,
            },
            "scenarios": {
                "count": len(suite_cases),
                "directory": _relative(self.root, scenarios_root),
                "suite": _relative(self.root, suite_path),
            },
            "model": model_status,
            "edit": {
                "strategy": "STRATEGY-BLUEPRINT.md",
                "rules": "package/policy/adapter.json",
                "scenarios": "scenarios/",
                "model": (
                    "package/model/actor.ort"
                    if self.policy_mode == "rules_with_model"
                    else None
                ),
            },
            "references": {
                "supported_cards": (
                    "SUPPORTED-CARDS.json"
                    if (self.root / "SUPPORTED-CARDS.json").is_file()
                    else "data/developer/supported-cards-v1.json"
                ),
                "ucis_guide": "UCIS-SDK.md",
            },
            "outputs": {
                "artifact": _relative(self.root, self.default_artifact),
                "report": _relative(self.root, self.default_report),
            },
            "issues": sorted(set(issues)),
            "next_actions": next_actions,
            "claims": {
                "development_only": True,
                "production_ready": False,
            },
        }

    def inspect(self, scenario: str | Path | None = None) -> dict[str, object]:
        """Inspect one scenario through the public current-window SDK."""

        from .cli import inspect_ucis_scenario  # pylint: disable=import-outside-toplevel

        if scenario is None:
            suite = load_json(self.root / "scenario-suite.json")
            cases = suite.get("cases", [])
            if not isinstance(cases, list) or not cases:
                _raise("workspace_scenario_missing")
            row = cases[0]
            relative = row.get("path") if isinstance(row, dict) else None
            if not isinstance(relative, str):
                _raise("workspace_scenario_suite_invalid")
            scenario_path = self.root / relative
        else:
            candidate = Path(scenario)
            scenario_path = candidate if candidate.is_absolute() else self.root / candidate
        try:
            resolved = scenario_path.resolve(strict=True)
            resolved.relative_to(self.root)
        except (OSError, ValueError):
            _raise("workspace_scenario_invalid")
        return inspect_ucis_scenario(resolved)

    def check(self) -> dict[str, object]:
        """Run all acceptance gates without writing an installable artifact."""

        from .cli import check_workspace  # pylint: disable=import-outside-toplevel

        return check_workspace(self.root)

    def build(
        self,
        output: str | Path | None = None,
        *,
        report: str | Path | None = None,
    ) -> dict[str, object]:
        """Run acceptance and write the exact accepted archive and report."""

        from .cli import check_workspace  # pylint: disable=import-outside-toplevel

        artifact = Path(output) if output is not None else self.default_artifact
        report_path = Path(report) if report is not None else self.default_report
        result = check_workspace(self.root, output=artifact)
        write_json(report_path, result)
        return result

    def install(self, artifact: str | Path | None = None) -> dict[str, object]:
        """Validate and install an accepted development artifact."""

        package = Path(artifact) if artifact is not None else self.default_artifact
        if not package.is_file():
            self.build(package)
        return install_development_package(package)


@dataclass(frozen=True)
class WorkspaceModel:
    """Frozen ORT actor operations scoped to one model workspace."""

    workspace: StrategyWorkspace

    @property
    def artifact(self) -> Path:
        return self.workspace.root / "package/model/actor.ort"

    @property
    def manifest(self) -> Path:
        return self.workspace.root / "package/model/model_manifest.json"

    def inspect(self, path: str | Path | None = None) -> dict[str, object]:
        candidate = Path(path) if path is not None else self.artifact
        try:
            return inspect_onnx(candidate) if candidate.suffix.casefold() == ".onnx" else inspect_ort(candidate)
        except OrtActorError as error:
            _raise(error.code)

    def conformance(self) -> dict[str, object]:
        try:
            return model_conformance(self.artifact)
        except OrtActorError as error:
            _raise(error.code)

    def tensorize(
        self,
        scenario: str | Path,
        output: str | Path | None = None,
    ) -> dict[str, object]:
        """Write the fixed public Actor tensors for one workspace scenario."""

        candidate = Path(scenario)
        context = candidate if candidate.is_absolute() else self.workspace.root / candidate
        try:
            resolved = context.resolve(strict=True)
            resolved.relative_to(self.workspace.root)
        except (OSError, ValueError):
            _raise("workspace_scenario_invalid")
        target = (
            Path(output)
            if output is not None
            else self.workspace.root / "build" / f"{resolved.stem}-tensors.json"
        )
        if target.exists() or target.is_symlink():
            _raise("model_output_exists")
        try:
            document = load_json(resolved)
            local_uids: dict[int, str] | None = None
            allowed_uids: set[str] | None = None
            if document.get("document_type") == "author_strategy_developer_scenario_v1":
                try:
                    parsed = parse_raw_cabt_envelope(
                        copy.deepcopy(document["raw_observation"]),
                        contract_root=_ROOT / "contracts/ptcgdap",
                    )
                    firewall = PublicObservationFirewall.load_default().project(parsed)
                    if not firewall.accepted:
                        _raise("model_hidden_field")
                except WorkspaceError:
                    raise
                except (KeyError, TypeError, ValueError):
                    _raise("workspace_scenario_invalid")
                context, local_uids = _scenario_actor_context(document)
                deck = load_json(self.workspace.root / "package/deck/deck_manifest.json")
                allowed_uids = {
                    row["local_card_uid"]
                    for row in deck.get("cards", [])
                    if isinstance(row, dict) and isinstance(row.get("local_card_uid"), str)
                }
            else:
                context = document
            tensors = PublicActorTensorizer.tensorize(
                context,
                local_option_uids=local_uids,
                allowed_card_uids=allowed_uids,
            )
        except (ModelActorError, OrtActorError) as error:
            _raise(error.code)
        tensor_document = {
            "document_type": "ptcgai_public_actor_tensors_v1",
            "schema_version": 1,
            "profile_id": tensors.profile_id,
            "frame_i32": [list(tensors.frame_i32)],
            "frame_presence_i32": [list(tensors.frame_presence_i32)],
            "option_i32": [[list(row) for row in tensors.option_i32]],
            "option_presence_i32": [[list(row) for row in tensors.option_presence_i32]],
            "option_mask_i32": [list(tensors.option_mask_i32)],
            "row_to_current_index": list(tensors.row_to_current_index),
            "semantic_keys": list(tensors.semantic_keys),
            "public_only": True,
        }
        payload = canonical_bytes(tensor_document)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return {
            "document_type": "ptcgai_model_tensorize_report_v1",
            "status": "written",
            "output": str(target.resolve()),
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest().upper(),
            "option_count": len(tensors.row_to_current_index),
            "public_only": True,
        }

    def import_actor(
        self,
        source: str | Path,
        *,
        model_id: str | None = None,
        training_method: str = "other",
        source_run_id: str = "developer-import",
    ) -> dict[str, object]:
        """Validate then replace this workspace's frozen actor and manifest."""

        source_path = Path(source)
        model_root = self.artifact.parent
        model_root.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix=".ptcgai-model-import-", dir=model_root) as temp_name:
                staged_actor = Path(temp_name) / "actor.ort"
                report = import_onnx_to_ort(source_path, staged_actor)
                conformance = model_conformance(staged_actor)
                document = build_model_manifest(
                    staged_actor.read_bytes(),
                    model_id=model_id or f"{self.workspace.package_id}.actor",
                    cabt_contract_sha256=CABT_CONTRACT_SHA256,
                    card_catalog_sha256=CARD_CATALOG_SHA256,
                    training_method=training_method,
                    source_run_id=source_run_id,
                )
                staged_manifest = Path(temp_name) / "model_manifest.json"
                staged_manifest.write_bytes(canonical_bytes(document))
                actor_backup = Path(temp_name) / "previous.ort"
                manifest_backup = Path(temp_name) / "previous.json"
                if self.artifact.exists():
                    actor_backup.write_bytes(self.artifact.read_bytes())
                if self.manifest.exists():
                    manifest_backup.write_bytes(self.manifest.read_bytes())
                try:
                    os.replace(staged_actor, self.artifact)
                    os.replace(staged_manifest, self.manifest)
                except OSError:
                    if actor_backup.exists():
                        os.replace(actor_backup, self.artifact)
                    if manifest_backup.exists():
                        os.replace(manifest_backup, self.manifest)
                    raise
        except OrtActorError as error:
            _raise(error.code)
        return {
            **report,
            "status": "imported",
            "conformance": conformance,
            "model_manifest": str(self.manifest.resolve()),
        }


__all__ = [
    "StrategyWorkspace",
    "WorkspaceError",
    "WorkspaceMode",
    "WorkspaceModel",
]
