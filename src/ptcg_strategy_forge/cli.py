from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ptcgdap.author_strategy_developer import (  # noqa: E402
    DeveloperToolError,
    build_development_package,
    install_development_package,
    scaffold_workspace,
    simulate_public_window,
    validate_development_package,
)
from tools.ptcgdap.build_author_strategy_package import write_or_check_contracts  # noqa: E402
from tools.ptcgdap.publish_strategy_release import PublishError, publish  # noqa: E402

from .provenance import verify_snapshot
from .scenarios import (
    SUITE_DOCUMENT_TYPE,
    assert_public_report,
    generate_demo_scenarios,
    load_json,
    write_json,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _emit(report: dict[str, object], report_path: Path | None) -> None:
    if report_path is not None:
        write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _customize_workspace(
    workspace: Path,
    package_id: str,
    package_version: str,
    author_id: str,
    author_name: str,
    strategy_name: str | None,
    summary: str | None,
) -> None:
    path = workspace / "package/strategy_package.json"
    manifest = load_json(path)
    manifest["package_id"] = package_id
    manifest["package_version"] = package_version
    manifest["author"] = {"author_id": author_id, "display_name": author_name}
    manifest["strategy"] = {
        "display_name": strategy_name or package_id,
        "summary": summary or "Data-only current-window strategy developed with PTCG Strategy Forge.",
    }
    write_json(path, manifest)


def doctor() -> dict[str, object]:
    checks: list[dict[str, object]] = []
    version_ok = sys.version_info >= (3, 13)
    checks.append({"id": "python", "accepted": version_ok, "version": sys.version.split()[0]})
    try:
        snapshot = verify_snapshot(ROOT)
    except (OSError, UnicodeError, ValueError) as error:
        snapshot = {"accepted": False, "file_count": 0, "failures": [{"error_code": str(error)}]}
    checks.append({"id": "sdk-snapshot", **snapshot})
    try:
        write_or_check_contracts(check=True)
        contract_ok = True
        contract_error = ""
    except SystemExit as error:
        contract_ok = False
        contract_error = str(error)
    checks.append({"id": "contract-drift", "accepted": contract_ok, "error_code": contract_error})
    try:
        template = validate_development_package(
            ROOT / "data/ptcgdap/author_strategy_packages/ptcgdap-author-strategy-release-candidate.ptcgai"
        )
        template_ok = template.get("status") == "valid"
    except (DeveloperToolError, OSError):
        template_ok = False
    checks.append({"id": "template-package", "accepted": template_ok})
    return {
        "document_type": "ptcg_strategy_forge_doctor_report_v1",
        "schema_version": 1,
        "status": "passed" if all(bool(row.get("accepted")) for row in checks) else "failed",
        "checks": checks,
    }


def run_suite(package_path: Path, suite_path: Path) -> dict[str, object]:
    if not suite_path.is_file() or suite_path.is_symlink():
        raise ValueError("scenario_suite_invalid")
    suite_path = suite_path.resolve()
    suite_root = suite_path.parent
    suite = load_json(suite_path)
    if (
        type(suite) is not dict
        or suite.get("document_type") != SUITE_DOCUMENT_TYPE
        or suite.get("schema_version") != 1
        or type(suite.get("cases")) is not list
        or not 1 <= len(suite["cases"]) <= 1000
    ):
        raise ValueError("scenario_suite_invalid")
    results: list[dict[str, object]] = []
    case_ids: set[str] = set()
    for case in suite["cases"]:
        if type(case) is not dict or set(case) != {"id", "path", "expect"} or type(case["expect"]) is not dict:
            raise ValueError("scenario_suite_invalid")
        case_id = case["id"]
        relative = case["path"]
        expected = case["expect"]
        if (
            type(case_id) is not str
            or not case_id.strip()
            or case_id in case_ids
            or type(relative) is not str
            or not relative
            or "\\" in relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or set(expected) - {"status", "error_code", "selected_indexes", "matched_rule_id", "selected_source"}
            or expected.get("status") not in {"passed", "error"}
        ):
            raise ValueError("scenario_suite_invalid")
        case_ids.add(case_id)
        scenario_path = (suite_root / relative).resolve()
        try:
            scenario_path.relative_to(suite_root)
        except ValueError as error:
            raise ValueError("scenario_suite_invalid") from error
        if not scenario_path.is_file() or scenario_path.is_symlink():
            raise ValueError("scenario_suite_invalid")
        try:
            simulation = simulate_public_window(package_path, scenario_path)
            assert_public_report(simulation)
            observed = {
                "status": simulation["status"],
                "error_code": simulation.get("error_code", ""),
                "selected_indexes": simulation["decision"]["selected_indexes"],
                "matched_rule_ids": [row["rule_id"] for row in simulation["adapter"]["matched_rules"]],
                "selected_source": simulation["adjudication"]["selected_source"],
                "claims": simulation["claims"],
            }
        except DeveloperToolError as error:
            observed = {"status": "error", "error_code": error.code}
        accepted = observed.get("status") == expected.get("status")
        for key in ("error_code", "selected_indexes", "selected_source"):
            if key in expected and observed.get(key) != expected.get(key):
                accepted = False
        if "matched_rule_id" in expected and expected["matched_rule_id"] not in observed.get("matched_rule_ids", []):
            accepted = False
        claims = observed.get("claims")
        if isinstance(claims, dict) and (
            claims.get("engine_execution") is not False
            or claims.get("production_authority") is not False
            or claims.get("classic_fallback_used") is not False
        ):
            accepted = False
        results.append({"id": case["id"], "accepted": accepted, "expected": expected, "observed": observed})
    return {
        "document_type": "ptcg_strategy_forge_scenario_report_v1",
        "schema_version": 1,
        "status": "passed" if all(row["accepted"] for row in results) else "failed",
        "package_sha256": _sha(package_path),
        "case_count": len(results),
        "passed_count": sum(bool(row["accepted"]) for row in results),
        "cases": results,
    }


def run_demo(output: Path) -> dict[str, object]:
    if output.exists() or output.is_symlink():
        raise ValueError("demo_output_exists")
    output.mkdir(parents=True)
    demo_root = ROOT / "demo/marnie-forge"
    source = demo_root / "package"
    suite = demo_root / "scenario-suite.json"
    baseline_source = output / "baseline-source"
    shutil.copytree(source, baseline_source)
    shutil.copy2(demo_root / "optimization/baseline_adapter.json", baseline_source / "policy/adapter.json")
    baseline_package = output / "baseline.ptcgai"
    build_development_package(baseline_source, baseline_package)
    positive_scenario = demo_root / "scenarios/01-positive.json"
    baseline_simulation = simulate_public_window(baseline_package, positive_scenario)
    baseline_red = baseline_simulation.get("status") == "failed" and baseline_simulation.get("error_code") == "simulation_expectation_failed"

    final_a = output / "forge-demo-a.ptcgai"
    final_b = output / "forge-demo-b.ptcgai"
    build_a = build_development_package(source, final_a)
    build_b = build_development_package(source, final_b)
    deterministic = final_a.read_bytes() == final_b.read_bytes()
    validation = validate_development_package(final_a)
    scenarios = run_suite(final_a, suite)
    accepted = bool(
        baseline_red
        and deterministic
        and validation.get("status") == "valid"
        and scenarios.get("status") == "passed"
    )
    report = {
        "document_type": "ptcg_strategy_forge_demo_report_v1",
        "schema_version": 1,
        "status": "passed" if accepted else "failed",
        "optimization": {
            "baseline_red": baseline_red,
            "baseline_selected_indexes": baseline_simulation.get("decision", {}).get("selected_indexes", []),
            "final_scenario_passed": scenarios.get("passed_count", 0),
            "final_scenario_total": scenarios.get("case_count", 0),
        },
        "build": {
            "package_id": build_a["package_id"],
            "package_version": build_a["package_version"],
            "archive_sha256": build_a["archive_sha256"],
            "archive_bytes": build_a["archive_bytes"],
            "second_archive_sha256": build_b["archive_sha256"],
            "deterministic": deterministic,
        },
        "validation": validation,
        "scenarios": scenarios,
        "claims": {
            "development_only": True,
            "production_ready": False,
            "engine_authority": False,
            "cabt_engine_parity": False,
        },
    }
    write_json(output / "demo-report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Develop, test, optimize, install, and publish PtcgDAP data-only strategies.")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor_parser = commands.add_parser("doctor")
    doctor_parser.add_argument("--report", type=Path)
    new = commands.add_parser("new")
    new.add_argument("--output", type=Path, required=True)
    new.add_argument("--package-id", required=True)
    new.add_argument("--package-version", default="0.1.0")
    new.add_argument("--author-id", required=True)
    new.add_argument("--author-name", required=True)
    new.add_argument("--strategy-name")
    new.add_argument("--summary")
    new.add_argument("--report", type=Path)
    build = commands.add_parser("build")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--report", type=Path)
    validate = commands.add_parser("validate")
    validate.add_argument("--package", type=Path, required=True)
    validate.add_argument("--report", type=Path)
    simulate = commands.add_parser("simulate")
    simulate.add_argument("--package", type=Path, required=True)
    simulate.add_argument("--scenario", type=Path, required=True)
    simulate.add_argument("--report", type=Path)
    test = commands.add_parser("test")
    test.add_argument("--package", type=Path, required=True)
    test.add_argument("--suite", type=Path, required=True)
    test.add_argument("--report", type=Path)
    install = commands.add_parser("install")
    install.add_argument("--package", type=Path, required=True)
    install.add_argument("--report", type=Path)
    publish_parser = commands.add_parser("publish")
    publish_parser.add_argument("--endpoint", required=True)
    publish_parser.add_argument("--strategy-id", required=True)
    publish_parser.add_argument("--package", type=Path, required=True)
    publish_parser.add_argument("--allow-insecure-loopback", action="store_true")
    publish_parser.add_argument("--report", type=Path)
    demo = commands.add_parser("demo")
    demo.add_argument("--output", type=Path, required=True)
    demo.add_argument("--report", type=Path)
    regenerate = commands.add_parser("regenerate-demo-scenarios")
    regenerate.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            report = doctor()
        elif args.command == "new":
            report = scaffold_workspace(args.output)
            _customize_workspace(
                args.output,
                args.package_id,
                args.package_version,
                args.author_id,
                args.author_name,
                args.strategy_name,
                args.summary,
            )
            report["customized_identity"] = {"package_id": args.package_id, "package_version": args.package_version, "author_id": args.author_id}
            report["scenario_suite"] = generate_demo_scenarios(
                args.output,
                matched_rule_id="marnie.morgrem.evolve",
                scenario_namespace="workspace",
            )
        elif args.command == "build":
            report = build_development_package(args.source, args.output)
        elif args.command == "validate":
            report = validate_development_package(args.package)
        elif args.command == "simulate":
            report = simulate_public_window(args.package, args.scenario)
        elif args.command == "test":
            report = run_suite(args.package, args.suite)
        elif args.command == "install":
            report = install_development_package(args.package)
        elif args.command == "publish":
            token = os.environ.get("PTCGDAP_PLATFORM_WRITE_TOKEN", "")
            report = publish(
                endpoint=args.endpoint,
                strategy_id=args.strategy_id,
                package_path=args.package,
                token=token,
                allow_insecure_loopback=args.allow_insecure_loopback,
            )
        elif args.command == "demo":
            report = run_demo(args.output)
        else:
            report = {"document_type": "ptcg_strategy_forge_demo_generation_v1", "schema_version": 1, "status": "generated", **generate_demo_scenarios(ROOT / "demo/marnie-forge")}
        _emit(report, getattr(args, "report", None))
        return 0 if report.get("status") not in {"failed", "error"} else 2
    except (DeveloperToolError, PublishError, ValueError, OSError) as error:
        code = error.code if isinstance(error, DeveloperToolError) else str(error)
        report = {
            "document_type": "ptcg_strategy_forge_error_v1",
            "schema_version": 1,
            "status": "error",
            "error_code": code,
            "credential_persisted": False,
            "production_authority": False,
        }
        _emit(report, getattr(args, "report", None))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
