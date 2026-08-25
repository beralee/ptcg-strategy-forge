from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, Mapping

from scripts.ai.ptcgdap.source_lock import canonical_json_v1_bytes, load_json_bytes_strict
from scripts.ai.ptcgdap.a1_scope import build_a1_scope
from tools.ptcgdap.competition_bundle import (
    CompetitionBundleError,
    CompetitionBundleOwner,
)
from tools.ptcgdap.competition_rights import CompetitionRightsGate, RightsMode


ROOT = Path(__file__).resolve().parents[2]
PROBE = Path(__file__).with_name("competition_probe.py")
UCIS_RUNTIME_SDK = Path(__file__).with_name("ucis_runtime.py")
CONFIG_KEYS = {"project", "identity", "deck", "compatibility", "rights"}
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class CompetitionToolError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest().upper()


def _canonical(value: Any) -> bytes:
    return canonical_json_v1_bytes(value)


def _write_new(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(body)
    except FileExistsError as error:
        raise CompetitionToolError("competition_output_exists") from error


def _write_atomic(path: Path, body: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise CompetitionToolError("competition_output_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists() or temporary.is_symlink():
        raise CompetitionToolError("competition_output_exists")
    try:
        with temporary.open("xb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _owner() -> CompetitionBundleOwner:
    try:
        return CompetitionBundleOwner.load_default(ROOT)
    except CompetitionBundleError as error:
        raise CompetitionToolError(error.code) from error


def _a1_release_binding(owner: CompetitionBundleOwner | None = None) -> dict[str, Any]:
    runtime = owner or _owner()
    path = ROOT / "contracts/ptcgdap/cabt_a1_scope_report_v2.json"
    try:
        report = load_json_bytes_strict(path.read_bytes())
        generated = build_a1_scope(ROOT)
        sdk = runtime.runtime_lock["sdk"]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise CompetitionToolError("competition_a1_scope_invalid") from error
    valid = (
        report == generated
        and report.get("document_type") == "ptcgdap_a1_scope_report_v2"
        and report.get("core_selection_interface_aligned") is True
        and report.get("full_official_api_aligned") is False
        and report.get("scope_sha256") == sdk.get("a1_scope_sha256")
        and report.get("search_capability") == sdk.get("search_capability")
        and report.get("time_profile", {}).get("profile_hash")
        == sdk.get("time_profile_sha256")
        and runtime.runtime_lock.get("capabilities", {}).get("search")
        == sdk.get("search_capability")
    )
    if not valid:
        raise CompetitionToolError("competition_a1_scope_invalid")
    return {
        "scope_sha256": report["scope_sha256"],
        "claim": report["claim"],
        "search_capability": report["search_capability"],
        "time_profile_sha256": report["time_profile"]["profile_hash"],
        "full_official_api_aligned": False,
    }


def _runtime_python(owner: CompetitionBundleOwner | None = None) -> Path:
    runtime = owner or _owner()
    required = runtime.runtime_lock["platform"]["python_version"]
    candidates: list[Path] = []
    configured = os.environ.get("PTCGBOT_PYTHON")
    if configured:
        candidates.append(Path(configured))
    candidates.append(Path(sys.executable))
    discovered = shutil.which("python3.11")
    if discovered:
        candidates.append(Path(discovered))
    launcher = shutil.which("py")
    if launcher:
        try:
            listed = subprocess.run(
                [launcher, "-0p"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=True,
                text=True,
                timeout=5,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            listed = ""
        for line in listed.splitlines():
            if "3.11" in line:
                candidate = line.strip().split()[-1]
                candidates.append(Path(candidate))
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        try:
            version = subprocess.run(
                [
                    str(resolved),
                    "-I",
                    "-c",
                    "import platform;print(platform.python_version())",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=True,
                text=True,
                timeout=5,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
        if version == required:
            return resolved
    raise CompetitionToolError("competition_runtime_python_unavailable")


def _load_config(workspace: str | Path) -> tuple[Path, dict[str, Any]]:
    root = Path(workspace)
    if root.is_symlink() or not root.is_dir():
        raise CompetitionToolError("competition_workspace_invalid")
    root = root.resolve()
    path = root / "ptcgbot.toml"
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise CompetitionToolError("competition_project_config_invalid") from error
    if type(value) is not dict or set(value) != CONFIG_KEYS:
        raise CompetitionToolError("competition_project_config_invalid")
    expected = {
        "project": {"format", "schema_generation"},
        "identity": {
            "strategy_id",
            "release_version",
            "author_id",
            "display_name",
            "summary",
        },
        "deck": {"deck_id", "archetype_id", "display_name"},
        "compatibility": {
            "engine_build_sha256",
            "observation_contract_sha256",
            "card_catalog_sha256",
            "required_capabilities",
        },
        "rights": {"mode"},
    }
    if any(type(value[key]) is not dict or set(value[key]) != fields for key, fields in expected.items()):
        raise CompetitionToolError("competition_project_config_invalid")
    if value["project"] != {"format": "ptcgbot", "schema_generation": 2}:
        raise CompetitionToolError("competition_project_config_invalid")
    if value["rights"]["mode"] not in tuple(mode.value for mode in RightsMode):
        raise CompetitionToolError("competition_project_config_invalid")
    capabilities = value["compatibility"]["required_capabilities"]
    if type(capabilities) is not list or any(type(item) is not str for item in capabilities):
        raise CompetitionToolError("competition_project_config_invalid")
    return root, value


def _metadata(config: Mapping[str, Any], owner: CompetitionBundleOwner) -> dict[str, Any]:
    identity = config["identity"]
    deck = config["deck"]
    compatibility = config["compatibility"]
    qualification = owner.profile["qualification_profile"]
    return {
        **identity,
        "deck_id": deck["deck_id"],
        "archetype_id": deck["archetype_id"],
        "deck_display_name": deck["display_name"],
        **compatibility,
        "qualification_profile_id": qualification["profile_id"],
        "qualification_profile_sha256": qualification["profile_sha256"],
    }


def scaffold(
    output: str | Path,
    *,
    strategy_id: str,
    author_id: str,
    display_name: str,
) -> dict[str, Any]:
    root = Path(output)
    if root.exists() or root.is_symlink():
        raise CompetitionToolError("competition_output_exists")
    if (
        _IDENTIFIER_RE.fullmatch(strategy_id) is None
        or _IDENTIFIER_RE.fullmatch(author_id) is None
        or not 1 <= len(display_name) <= 120
        or "\x00" in display_name
    ):
        raise CompetitionToolError("competition_identity_invalid")
    owner = _owner()
    root.mkdir(parents=True)
    try:
        (root / "src/submission").mkdir(parents=True)
        (root / "resources").mkdir()
        (root / "tests").mkdir()
        (root / "scenarios").mkdir()
        config = f'''[project]
format = "ptcgbot"
schema_generation = 2

[identity]
strategy_id = {json.dumps(strategy_id, ensure_ascii=False)}
release_version = "0.1.0"
author_id = {json.dumps(author_id, ensure_ascii=False)}
display_name = {json.dumps(display_name, ensure_ascii=False)}
summary = "Kaggle-style synchronous CABT competition strategy."

[deck]
deck_id = "deck.unconfigured"
archetype_id = "archetype.unconfigured"
display_name = "Unconfigured 60-card deck"

[compatibility]
engine_build_sha256 = "C932B8667506BAF6C5F8E573962647EF133547E79D75ACF6DC741E9AA69CBB6C"
observation_contract_sha256 = "2CD02F54538985426EFDB057F3A6BDA4AD154DD171BCC03667D42D102982D294"
card_catalog_sha256 = "AB8CF10465F492A98DA8247A84572AECEE281D0726F7BB7B8E5DBC03A6AC70D4"
required_capabilities = ["current_option_indexes", "raw_observation"]

[rights]
mode = "clean_room"
'''.encode("utf-8")
        _write_new(root / "ptcgbot.toml", config)
        _write_new(root / "deck.csv", b"1\n" * 60)
        _write_new(root / "runtime-lock.json", owner.runtime_lock_bytes)
        _write_new(root / "src/submission/__init__.py", b"")
        _write_new(root / "src/submission/ucis.py", UCIS_RUNTIME_SDK.read_bytes())
        _write_new(
            root / "src/submission/main.py",
            (
                "from pathlib import Path\n\n"
                "from .ucis import SelectionWindow, semantic_key\n\n"
                "_DECK = [int(value) for value in Path('deck.csv').read_text(encoding='ascii').splitlines()]\n\n"
                "_SEARCH_TARGET = semantic_key('CARD', area=2, index=20, playerIndex=0)\n\n"
                "def agent(raw_observation):\n"
                "    select = raw_observation.get('select')\n"
                "    if select is None and raw_observation.get('current') is None:\n"
                "        return list(_DECK)\n"
                "    window = SelectionWindow.parse(raw_observation)\n"
                "    if window.context_name == 'TO_HAND':\n"
                "        return window.rebind([_SEARCH_TARGET])\n"
                "    return window.first_legal()\n"
            ).encode("utf-8"),
        )
        bootstrap = {"select": None, "current": None, "logs": []}
        first = {
            "select": {
                "type": 1,
                "context": 7,
                "minCount": 1,
                "maxCount": 1,
                "remainDamageCounter": 0,
                "remainEnergyCost": 0,
                "option": [
                    {"type": 3, "area": 2, "index": 10, "playerIndex": 0},
                    {"type": 3, "area": 2, "index": 20, "playerIndex": 0},
                ],
                "deck": None,
                "contextCard": None,
                "effect": None,
            },
            "current": {},
            "logs": [],
        }
        reordered = json.loads(json.dumps(first))
        reordered["select"]["option"].reverse()
        suite = {
            "document_type": "ptcgbot_scenario_suite_v2",
            "schema_version": 2,
            "cases": [
                {"id": "bootstrap", "observation": bootstrap, "expected": [1] * 60},
                {"id": "preferred", "observation": first, "expected": [1]},
                {"id": "preferred-reordered", "observation": reordered, "expected": [0]},
            ],
        }
        _write_new(root / "scenarios/smoke.json", _canonical(suite))
        _write_new(
            root / "tests/README.md",
            (
                "# Tests\n\n"
                "`scenarios/smoke.json` is the executable starting point. Add one RED case first, "
                "then cover the GREEN decision, semantic option reorder, a one-fact metamorphic "
                "flip, invalid output, and unknown UCIS shape.\n"
            ).encode("utf-8"),
        )
        _write_new(
            root / "STRATEGY-BLUEPRINT.md",
            (
                "# Strategy blueprint\n\n"
                "Record match agenda, prize schedule, resource debt, credible response, "
                "information checkpoints, typed interactions, and rollback identity. "
                "Never persist an old option index across callbacks.\n"
            ).encode("utf-8"),
        )
        _write_new(
            root / "README.md",
            (
                "# PTCG competition strategy\n\n"
                "Start in `src/submission/main.py`; `src/submission/ucis.py` is the pinned, "
                "dependency-free current-window helper. It uses named contexts/options, exact "
                "cardinality, semantic rebind, deterministic fallback, prize clock, and energy "
                "debt helpers without engine authority.\n\n"
                "Run `forge.py competition test --workspace .`, then "
                "`forge.py competition check --workspace .` and "
                "`forge.py competition prequalify --workspace .`. The result is "
                "developer-local evidence, not production sandbox or official parity authority.\n"
            ).encode("utf-8"),
        )
    except BaseException:
        shutil.rmtree(root)
        raise
    return {
        "document_type": "ptcgbot_workspace_init_v2",
        "schema_version": 2,
        "status": "created",
        "workspace": str(root.resolve()),
        "rights_mode": "clean_room",
        "production_authority": False,
    }


def _rights(root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    mode = RightsMode(config["rights"]["mode"])
    if mode is not RightsMode.CLEAN_ROOM:
        raise CompetitionToolError("rights_external_receipt_or_private_root_required")
    gate = CompetitionRightsGate.clean_room_default()
    distribution = gate.audit_distribution(root)
    operation = gate.authorize(operation="developer_local_build")
    if not distribution.accepted or not operation.accepted:
        raise CompetitionToolError(distribution.error_code or operation.error_code)
    return {
        "mode": mode.value,
        "distribution_clean": True,
        "claims": operation.claims,
    }


def _require_ucis_runtime_sdk(root: Path) -> str:
    path = root / "src/submission/ucis.py"
    try:
        expected = UCIS_RUNTIME_SDK.read_bytes()
        actual = path.read_bytes()
    except OSError as error:
        raise CompetitionToolError("competition_ucis_runtime_sdk_mismatch") from error
    if path.is_symlink() or not path.is_file() or actual != expected:
        raise CompetitionToolError("competition_ucis_runtime_sdk_mismatch")
    return _sha(expected)


def doctor(workspace: str | Path | None = None) -> dict[str, Any]:
    owner = _owner()
    a1 = _a1_release_binding(owner)
    snapshot = load_json_bytes_strict((ROOT / "vendor/ptcgdap-sdk-manifest.json").read_bytes())
    root = None
    rights: dict[str, Any]
    if workspace is None:
        decision = CompetitionRightsGate.clean_room_default().audit_distribution(ROOT)
        rights = {"mode": "clean_room", "distribution_clean": decision.accepted}
    else:
        root, config = _load_config(workspace)
        rights = _rights(root, config)
    ucis_sdk_pinned = UCIS_RUNTIME_SDK.is_file() and (
        root is None or bool(_require_ucis_runtime_sdk(root))
    )
    try:
        runtime_python = _runtime_python(owner)
    except CompetitionToolError:
        runtime_python = None
    gates = {
        "python_abi": runtime_python is not None,
        "bundle_contract": owner.profile["bundle_schema_generation"] == 2,
        "runtime_lock": owner.runtime_lock["schema_version"] == 2,
        "rpc_contract_pinned": bool(owner.runtime_lock.get("rpc", {}).get("contract_sha256")),
        "a1_scope_pinned": bool(a1["scope_sha256"]),
        "search_capability_pinned": a1["search_capability"] == "none",
        "time_profile_pinned": bool(a1["time_profile_sha256"]),
        "sdk_snapshot": snapshot.get("document_type") == "ptcg_strategy_forge_sdk_snapshot_v1",
        "rights": rights["distribution_clean"],
        "probe": PROBE.is_file(),
        "ucis_runtime_sdk_pinned": ucis_sdk_pinned,
    }
    return {
        "document_type": "ptcgbot_doctor_report_v2",
        "schema_version": 2,
        "status": "passed" if all(gates.values()) else "failed",
        "workspace": str(root) if root else None,
        "gates": gates,
        "rights": rights,
        "runtime_profile_sha256": owner.profile_sha256,
        "runtime_lock_sha256": owner.runtime_lock_sha256,
        "runtime_python": str(runtime_python) if runtime_python else None,
        "a1": a1,
        "authority": "development_only",
    }


def build(workspace: str | Path, output: str | Path) -> dict[str, Any]:
    root, config = _load_config(workspace)
    rights = _rights(root, config)
    ucis_runtime_sdk_sha256 = _require_ucis_runtime_sdk(root)
    owner = _owner()
    a1 = _a1_release_binding(owner)
    lock = root / "runtime-lock.json"
    if not lock.is_file() or lock.is_symlink() or lock.read_bytes() != owner.runtime_lock_bytes:
        raise CompetitionToolError("competition_runtime_lock_mismatch")
    try:
        archive = owner.build(root, _metadata(config, owner))
        handle = owner.validate(archive)
    except CompetitionBundleError as error:
        raise CompetitionToolError(error.code) from error
    target = Path(output)
    _write_atomic(target, archive)
    receipt = {
        "document_type": "ptcgbot_build_receipt_v2",
        "schema_version": 2,
        "status": "built",
        "archive": str(target.resolve()),
        "archive_sha256": handle.archive_sha256,
        "archive_bytes": len(archive),
        "manifest_sha256": handle.manifest_canonical_sha256,
        "bundle_schema_generation": handle.schema_generation,
        "canonical_zip_profile_generation": handle.canonical_zip_profile_generation,
        "a1_scope_sha256": a1["scope_sha256"],
        "ucis_runtime_sdk_sha256": ucis_runtime_sdk_sha256,
        "rights": rights,
        "authority": "development_only",
    }
    _write_atomic(target.with_suffix(target.suffix + ".build.json"), _canonical(receipt))
    return receipt


def _transcript_from_suite(path: Path) -> tuple[list[dict[str, Any]], list[list[int]]]:
    try:
        suite = load_json_bytes_strict(path.read_bytes())
    except (OSError, UnicodeError, ValueError) as error:
        raise CompetitionToolError("competition_scenario_suite_invalid") from error
    if (
        type(suite) is not dict
        or set(suite) != {"document_type", "schema_version", "cases"}
        or suite["document_type"] != "ptcgbot_scenario_suite_v2"
        or suite["schema_version"] != 2
        or type(suite["cases"]) is not list
        or not suite["cases"]
    ):
        raise CompetitionToolError("competition_scenario_suite_invalid")
    observations: list[dict[str, Any]] = []
    expected: list[list[int]] = []
    for case in suite["cases"]:
        if (
            type(case) is not dict
            or set(case) != {"id", "observation", "expected"}
            or type(case["id"]) is not str
            or type(case["observation"]) is not dict
            or type(case["expected"]) is not list
            or any(type(item) is not int for item in case["expected"])
        ):
            raise CompetitionToolError("competition_scenario_suite_invalid")
        observations.append(case["observation"])
        expected.append(case["expected"])
    return observations, expected


def _clean_environment(scratch: Path) -> dict[str, str]:
    allowed: dict[str, str] = {}
    for key in ("SystemRoot", "WINDIR", "PATH", "Path", "PATHEXT"):
        if os.environ.get(key):
            allowed[key] = os.environ[key]
    allowed.update(
        {
            "PYTHONNOUSERSITE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONIOENCODING": "utf-8",
            "TEMP": str(scratch),
            "TMP": str(scratch),
            "TZ": "UTC",
        }
    )
    return allowed


def _probe_archive(
    archive: bytes,
    observations: list[dict[str, Any]],
    *,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    owner = _owner()
    handle = owner.validate(archive)
    runtime_python = _runtime_python(owner)
    with tempfile.TemporaryDirectory(prefix="ptcgbot-probe-") as temporary:
        scratch = Path(temporary)
        package = scratch / "package"
        owner.extract(handle, package)
        transcript = scratch / "transcript.json"
        output = scratch / "output.json"
        transcript.write_bytes(_canonical({"observations": observations}))
        try:
            completed = subprocess.run(
                [
                    str(runtime_python),
                    "-I",
                    str(PROBE),
                    "--package",
                    str(package),
                    "--transcript",
                    str(transcript),
                    "--output",
                    str(output),
                ],
                cwd=package,
                env=_clean_environment(scratch),
                timeout=timeout_seconds,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise CompetitionToolError("agent_timeout") from error
        if len(completed.stdout) > 1024 * 1024 or len(completed.stderr) > 1024 * 1024:
            raise CompetitionToolError("competition_agent_output_limit")
        if completed.returncode != 0 or not output.is_file():
            raise CompetitionToolError("competition_agent_probe_failed")
        try:
            report = load_json_bytes_strict(output.read_bytes())
        except (OSError, UnicodeError, ValueError) as error:
            raise CompetitionToolError("competition_agent_probe_failed") from error
        if type(report) is not dict or report.get("status") != "passed":
            raise CompetitionToolError("competition_agent_probe_failed")
        return report


def test(workspace: str | Path, suite_path: str | Path | None = None) -> dict[str, Any]:
    root, config = _load_config(workspace)
    _rights(root, config)
    _require_ucis_runtime_sdk(root)
    owner = _owner()
    archive = owner.build(root, _metadata(config, owner))
    suite = Path(suite_path) if suite_path is not None else root / "scenarios/smoke.json"
    observations, expected = _transcript_from_suite(suite)
    probe = _probe_archive(archive, observations)
    actual = [item["result"] for item in probe["trace"]]
    failures = [index for index, pair in enumerate(zip(actual, expected)) if pair[0] != pair[1]]
    return {
        "document_type": "ptcgbot_scenario_report_v2",
        "schema_version": 2,
        "status": "passed" if not failures else "failed",
        "case_count": len(expected),
        "passed_count": len(expected) - len(failures),
        "failed_ordinals": failures,
        "trace_sha256": _sha(_canonical(probe["trace"])),
        "authority": "development_only",
    }


def trace(
    package: str | Path,
    suite_path: str | Path,
    *,
    public: bool,
) -> dict[str, Any]:
    archive = Path(package).read_bytes()
    observations, _expected = _transcript_from_suite(Path(suite_path))
    probe = _probe_archive(archive, observations)
    if public:
        entries = [
            {
                "ordinal": item["ordinal"],
                "call_kind": item["call_kind"],
                "response_domain": item["response_domain"],
                "option_fingerprint": item["option_fingerprint"],
                "result": item["result"],
            }
            for item in probe["trace"]
        ]
    else:
        entries = probe["trace"]
    return {
        "document_type": "ptcgbot_public_trace_v2" if public else "ptcgbot_private_trace_v2",
        "schema_version": 2,
        "status": "passed",
        "trace": entries,
        "hidden_fields_included": False,
        "credentials_included": False,
        "authority": "development_only",
    }


def replay(package: str | Path, suite_path: str | Path) -> dict[str, Any]:
    observations, expected = _transcript_from_suite(Path(suite_path))
    probe = _probe_archive(Path(package).read_bytes(), observations)
    first = None
    for ordinal, (item, wanted) in enumerate(zip(probe["trace"], expected)):
        if item["result"] != wanted:
            first = {
                "ordinal": ordinal,
                "expected": wanted,
                "actual": item["result"],
                "option_fingerprint": item["option_fingerprint"],
            }
            break
    return {
        "document_type": "ptcgbot_replay_diagnosis_v2",
        "schema_version": 2,
        "status": "passed" if first is None else "diverged",
        "first_policy_divergence": first,
        "authority": "development_only",
    }


def check(workspace: str | Path) -> dict[str, Any]:
    root, config = _load_config(workspace)
    rights = _rights(root, config)
    ucis_runtime_sdk_sha256 = _require_ucis_runtime_sdk(root)
    owner = _owner()
    metadata = _metadata(config, owner)
    try:
        first = owner.build(root, metadata)
        second = owner.build(root, metadata)
        first_handle = owner.validate(first)
        second_handle = owner.validate(second)
    except CompetitionBundleError as error:
        raise CompetitionToolError(error.code) from error
    scenario = test(root)
    gates = {
        "rights": rights["distribution_clean"],
        "canonical_exact_rebuild": first == second,
        "archive_hash_stable": first_handle.archive_sha256 == second_handle.archive_sha256,
        "shared_owner_validation": first_handle.schema_generation == 2,
        "scenario_suite": scenario["status"] == "passed",
        "ucis_runtime_sdk_pinned": bool(ucis_runtime_sdk_sha256),
    }
    return {
        "document_type": "ptcgbot_workspace_check_v2",
        "schema_version": 2,
        "status": "passed" if all(gates.values()) else "failed",
        "gates": gates,
        "archive_sha256": first_handle.archive_sha256,
        "archive_bytes": len(first),
        "ucis_runtime_sdk_sha256": ucis_runtime_sdk_sha256,
        "scenario": scenario,
        "authority": "development_only",
    }


def _deck_legality(deck: tuple[int, ...], catalog_path: Path | None) -> dict[str, Any]:
    if len(deck) != 60 or any(type(card) is not int or card < 1 for card in deck):
        return {"accepted": False, "authority": "format_only", "error_code": "deck_invalid"}
    if catalog_path is None:
        return {
            "accepted": True,
            "authority": "format_only_clean_room",
            "catalog_checked": False,
            "official_format_legality_claim": False,
        }
    if catalog_path.is_symlink() or not catalog_path.is_file():
        raise CompetitionToolError("competition_catalog_invalid")
    try:
        with catalog_path.open("r", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
    except (OSError, UnicodeError, csv.Error) as error:
        raise CompetitionToolError("competition_catalog_invalid") from error
    id_fields = ("Card ID", "card_id", "CardId", "ID", "id")
    ids: set[int] = set()
    for row in rows:
        raw = next((row.get(field) for field in id_fields if row.get(field)), None)
        if raw is not None and raw.isdecimal():
            ids.add(int(raw))
    missing = sorted(set(deck) - ids)
    return {
        "accepted": not missing,
        "authority": "user_supplied_private_catalog",
        "catalog_checked": True,
        "catalog_sha256": _sha(catalog_path.read_bytes()),
        "missing_card_ids": missing[:20],
        "official_format_legality_claim": False,
    }


def _fault_archive(
    source_root: Path,
    config: Mapping[str, Any],
    main_source: str,
) -> bytes:
    owner = _owner()
    with tempfile.TemporaryDirectory(prefix="ptcgbot-fault-source-") as temporary:
        project = Path(temporary) / "project"
        shutil.copytree(source_root, project)
        (project / "src/submission/main.py").write_text(main_source, encoding="utf-8")
        try:
            return owner.build(project, _metadata(config, owner))
        except CompetitionBundleError as error:
            raise CompetitionToolError(error.code) from error


def _expect_fault(
    archive: bytes,
    observations: list[dict[str, Any]],
    expected_code: str,
    *,
    timeout_seconds: int = 5,
) -> dict[str, Any]:
    try:
        _probe_archive(archive, observations, timeout_seconds=timeout_seconds)
    except CompetitionToolError as error:
        return {"accepted": error.code == expected_code, "observed_code": error.code}
    return {"accepted": False, "observed_code": "fault_not_contained"}


def _qualification_fault_probes(
    root: Path,
    config: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    prefix = (
        "from pathlib import Path\n"
        "_DECK=[int(v) for v in Path('deck.csv').read_text(encoding='ascii').splitlines()]\n"
    )
    bootstrap = {"select": None, "current": None, "logs": []}
    selection = {
        "select": {"minCount": 0, "maxCount": 0, "option": []},
        "current": {},
        "logs": [],
    }
    transcript = [bootstrap, selection]
    invalid = _fault_archive(
        root,
        config,
        prefix
        + "def agent(o):\n"
        + "    return list(_DECK) if o.get('select') is None else [True]\n",
    )
    timeout = _fault_archive(
        root,
        config,
        prefix
        + "def agent(o):\n"
        + "    if o.get('select') is None: return list(_DECK)\n"
        + "    while True: pass\n",
    )
    network = _fault_archive(
        root,
        config,
        prefix
        + "import socket\n"
        + "def agent(o):\n"
        + "    if o.get('select') is None: return list(_DECK)\n"
        + "    socket.socket()\n"
        + "    return []\n",
    )
    child_process = _fault_archive(
        root,
        config,
        prefix
        + "import subprocess\n"
        + "def agent(o):\n"
        + "    if o.get('select') is None: return list(_DECK)\n"
        + "    subprocess.run(['forbidden'])\n"
        + "    return []\n",
    )
    output = _fault_archive(
        root,
        config,
        prefix
        + "def agent(o):\n"
        + "    if o.get('select') is None: return list(_DECK)\n"
        + "    print('x' * 1048577)\n"
        + "    return []\n",
    )
    sentinel = _fault_archive(
        root,
        config,
        prefix
        + "import os\n"
        + "from pathlib import Path\n"
        + "def agent(o):\n"
        + "    if o.get('select') is None: return list(_DECK)\n"
        + "    leaked = any(k in os.environ for k in "
        + "('PTCGBOT_PRIVATE_SENTINEL','PTCGDAP_DATABASE_URL','AWS_SECRET_ACCESS_KEY'))\n"
        + "    leaked = leaked or Path('../opponent-package').exists()\n"
        + "    return [999999] if leaked else []\n",
    )
    previous = {
        key: os.environ.get(key)
        for key in (
            "PTCGBOT_PRIVATE_SENTINEL",
            "PTCGDAP_DATABASE_URL",
            "AWS_SECRET_ACCESS_KEY",
        )
    }
    os.environ["PTCGBOT_PRIVATE_SENTINEL"] = "private-do-not-copy"
    os.environ["PTCGDAP_DATABASE_URL"] = "private-do-not-copy"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "private-do-not-copy"
    try:
        sentinel_report = _probe_archive(sentinel, transcript)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    sentinel_ok = sentinel_report["trace"][-1]["result"] == []
    return {
        "invalid_output": _expect_fault(
            invalid, transcript, "competition_agent_probe_failed"
        ),
        "timeout": _expect_fault(
            timeout, transcript, "agent_timeout", timeout_seconds=1
        ),
        "network": _expect_fault(
            network, transcript, "competition_agent_probe_failed"
        ),
        "subprocess": _expect_fault(
            child_process, transcript, "competition_agent_probe_failed"
        ),
        "output": _expect_fault(
            output, transcript, "competition_agent_output_limit"
        ),
        "private_sentinel": {
            "accepted": sentinel_ok,
            "observed_code": "sentinel_absent" if sentinel_ok else "sentinel_visible",
        },
    }


def _scratch_cleanup_probe() -> bool:
    holder = tempfile.TemporaryDirectory(prefix="ptcgbot-cleanup-")
    path = Path(holder.name)
    (path / "canary").write_bytes(b"canary")
    holder.cleanup()
    return not path.exists()


def prequalify(
    workspace: str | Path,
    *,
    catalog_path: str | Path | None = None,
) -> dict[str, Any]:
    root, config = _load_config(workspace)
    rights = _rights(root, config)
    ucis_runtime_sdk_sha256 = _require_ucis_runtime_sdk(root)
    owner = _owner()
    a1 = _a1_release_binding(owner)
    metadata = _metadata(config, owner)
    try:
        first = owner.build(root, metadata)
        second = owner.build(root, metadata)
        handle = owner.validate(first)
    except CompetitionBundleError as error:
        raise CompetitionToolError(error.code) from error
    observations, expected = _transcript_from_suite(root / "scenarios/smoke.json")
    traces = [_probe_archive(first, observations)["trace"] for _ in range(3)]
    decisions = [[item["result"] for item in trace_items] for trace_items in traces]
    scenario_ok = all(value == expected for value in decisions)
    deterministic = traces[0] == traces[1] == traces[2]
    legality = _deck_legality(
        handle.deck_cards,
        Path(catalog_path).resolve() if catalog_path is not None else None,
    )
    paired_trace = _probe_archive(first, observations)["trace"]
    paired = traces[0] == paired_trace
    fault_probes = _qualification_fault_probes(root, config)
    invalid_contained = fault_probes["invalid_output"]["accepted"]
    timeout_contained = fault_probes["timeout"]["accepted"]
    output_contained = fault_probes["output"]["accepted"]
    sentinel_denied = fault_probes["private_sentinel"]["accepted"]
    scratch_clean = _scratch_cleanup_probe()
    gates = {
        "canonical_bundle_rebuild": first == second,
        "content_closure": bool(handle.paths),
        "deck_exact_60": len(handle.deck_cards) == 60,
        "deck_catalog_format_legality": legality["accepted"],
        "isolated_import": bool(traces[0]),
        "deck_bootstrap_domain": traces[0][0]["response_domain"] == "official_card_ids",
        "selection_current_window_domain": all(
            item["response_domain"] == "current_option_indexes" for item in traces[0][1:]
        ),
        "semantic_option_reorder": scenario_ok,
        "deterministic_repeat": deterministic,
        "paired_clean_room_smoke": paired,
        "invalid_output_containment": invalid_contained,
        "agent_timeout_containment": timeout_contained,
        "resource_limit_enforced": timeout_contained and output_contained,
        "network_denial": fault_probes["network"]["accepted"],
        "subprocess_denial": fault_probes["subprocess"]["accepted"],
        "private_sentinel_denial": sentinel_denied,
        "cross_seat_denial": sentinel_denied,
        "service_credential_denial": sentinel_denied,
        "scratch_cleanup_zero": scratch_clean,
        "ucis_runtime_sdk_pinned": bool(ucis_runtime_sdk_sha256),
    }
    required = owner.profile["qualification_profile"]
    profile = load_json_bytes_strict((ROOT / required["path"]).read_bytes())
    required_identities = profile["required_identities"]
    sdk = owner.runtime_lock["sdk"]
    gates["release_identity_binding"] = (
        required_identities["agent_rpc_contract_sha256"]
        == owner.runtime_lock["rpc"]["contract_sha256"]
        and required_identities["observation_contract_sha256"]
        == handle.manifest["compatibility"]["observation_contract_sha256"]
        and required_identities["a1_scope_sha256"] == a1["scope_sha256"]
        and required_identities["time_profile_sha256"] == a1["time_profile_sha256"]
        and required_identities["search_capability"] == a1["search_capability"]
        and sdk["a1_scope_sha256"] == a1["scope_sha256"]
    )
    missing_gates = sorted(set(profile["required_gates"]) - set(gates))
    accepted = all(gates.values()) and legality["accepted"] and not missing_gates
    evidence = {
        "archive_sha256": handle.archive_sha256,
        "manifest_sha256": handle.manifest_canonical_sha256,
        "profile_sha256": required["profile_sha256"],
        "runtime_profile_sha256": owner.profile_sha256,
        "runtime_lock_sha256": owner.runtime_lock_sha256,
        "ucis_runtime_sdk_sha256": ucis_runtime_sdk_sha256,
        "a1_scope_sha256": a1["scope_sha256"],
        "a1_claim": a1["claim"],
        "search_capability": a1["search_capability"],
        "time_profile_sha256": a1["time_profile_sha256"],
        "trace_sha256": _sha(_canonical(traces[0])),
        "rights_mode": rights["mode"],
        "deck_legality": legality,
        "gates": gates,
        "fault_probes": fault_probes,
        "missing_profile_gates": missing_gates,
    }
    return {
        "document_type": "ptcgdap_competition_release_qualification_receipt_v2",
        "schema_version": 2,
        "status": "developer_local_qualified" if accepted else "failed",
        "authority": "development_only",
        "production_multi_tenant_isolation": False,
        "official_engine_parity": False,
        "evidence": evidence,
        "evidence_sha256": _sha(_canonical(evidence)),
    }


__all__ = [
    "CompetitionToolError",
    "build",
    "check",
    "doctor",
    "prequalify",
    "replay",
    "scaffold",
    "test",
    "trace",
]
