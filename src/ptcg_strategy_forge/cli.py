from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
from .resources import resource_root
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = resource_root()
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
from tools.ptcgdap.build_competitive_policy_v2_contract import (  # noqa: E402
    write_or_check as write_or_check_competitive_v2_contract,
)
from tools.build_developer_supported_cards import verify_supported_cards_delivery  # noqa: E402
from tools.ptcgdap.publish_strategy_release import PublishError, publish  # noqa: E402
from scripts.ai.ptcgdap.ucis_sdk import UcisDeveloperSdk, UcisSdkError  # noqa: E402
from scripts.ai.ptcgdap.author_strategy_package import (  # noqa: E402
    CABT_CONTRACT_SHA256,
    CARD_CATALOG_SHA256,
)
from scripts.ai.ptcgdap.ptcgai_model_actor import PublicActorTensorizer  # noqa: E402
from scripts.ai.ptcgdap.ptcgai_model_package import (  # noqa: E402
    build_model_manifest,
    canonical_bytes,
)

from .provenance import verify_snapshot
from .ptcgai_ort import (
    OrtActorError,
    conformance as model_conformance,
    import_onnx_to_ort,
    inspect_onnx,
    inspect_ort,
    write_linear_actor_onnx,
)
from .reviewed_decks import customize_reviewed_workspace, reviewed_deck_ids
from .release_signing import (
    build_registered_release,
    generate_release_key,
    resign_registered_release,
)
from .sdk import StrategyWorkspace, WorkspaceError
from .ucis_runtime import PublicBattleFacts, UcisRuntimeError
from .scenarios import (
    SUITE_DOCUMENT_TYPE,
    assert_public_report,
    generate_demo_scenarios,
    is_competitive_scenario,
    load_json,
    simulate_competitive_public_frame,
    write_json,
)


from .application import (
    _sha,
    _ucis_qualification,
    _emit,
    _customize_workspace,
    _write_workspace_guides,
    doctor,
    ucis_catalog_report,
    inspect_ucis_scenario,
    run_ucis_sdk_walkthrough,
    run_suite,
    _checked_artifact_target,
    _publish_checked_artifact,
    check_workspace,
    run_demo,
    _configure_model_workspace,
    _configure_rules_workspace,
    _model_import,
    _model_tensorize,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Develop, verify, build, and install data-only .ptcgai workspaces.",
        epilog="New developers: start with `workspace create`, then `workspace status`.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    doctor_parser = commands.add_parser("doctor", help="Verify Python, pinned SDK bytes, contracts, and template package.")
    doctor_parser.add_argument("--report", type=Path, help="Write the JSON report to this path.")
    new = commands.add_parser(
        "new",
        help="Low-level compatibility entry for explicit workspace scaffolding.",
    )
    new.add_argument("--output", type=Path, required=True, help="New workspace directory; it must not exist.")
    new.add_argument("--package-id", required=True, help="Stable reverse-domain package identifier.")
    new.add_argument("--package-version", default="0.1.0", help="Initial package version (default: 0.1.0).")
    new.add_argument("--author-id", required=True, help="Stable author identifier.")
    new.add_argument("--author-name", required=True, help="Author display name.")
    new.add_argument("--strategy-name", help="Strategy display name.")
    new.add_argument("--summary", help="Short public strategy summary.")
    new.add_argument(
        "--policy-mode",
        choices=("rules", "model"),
        default="rules",
        help="Create a rules-only package or a v2 rules-with-model package.",
    )
    new.add_argument(
        "--deck-id",
        type=int,
        choices=reviewed_deck_ids(),
        help="Use one reviewed exact 18.0 Windows-local deck instead of the Marnie template.",
    )
    new.add_argument("--report", type=Path, help="Write the JSON report to this path.")
    workspace = commands.add_parser(
        "workspace",
        help="Create, understand, check, build, and install one developer workspace.",
    )
    workspace_commands = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_create = workspace_commands.add_parser(
        "create", help="Create a workspace with convention-based identity defaults."
    )
    workspace_create.add_argument("path", type=Path, help="New workspace directory; it must not exist.")
    identity = workspace_create.add_mutually_exclusive_group(required=True)
    identity.add_argument("--author-id", help="Explicit identity for offline development.")
    identity.add_argument("--account", action="store_true", help="Use the authenticated account identity.")
    from .control_workflow import add_auth_arguments
    add_auth_arguments(workspace_create)
    workspace_create.add_argument("--author-name", help="Display name; defaults to --author-id.")
    workspace_create.add_argument("--package-id", help="Defaults to dev.<author-id>.<workspace-name>.")
    workspace_create.add_argument("--package-version", default="0.1.0")
    workspace_create.add_argument("--strategy-name", help="Defaults to the workspace directory name.")
    workspace_create.add_argument("--summary")
    workspace_create.add_argument("--mode", choices=("rules", "model"), default="rules")
    workspace_create.add_argument("--deck-id", type=int, choices=reviewed_deck_ids())
    workspace_create.add_argument("--report", type=Path)
    workspace_status = workspace_commands.add_parser(
        "status", help="Show what to edit, readiness issues, outputs, and next commands."
    )
    workspace_status.add_argument("path", type=Path)
    workspace_status.add_argument("--report", type=Path)
    workspace_inspect = workspace_commands.add_parser(
        "inspect", help="Inspect the first or selected public current-window scenario."
    )
    workspace_inspect.add_argument("path", type=Path)
    workspace_inspect.add_argument("--scenario", type=Path)
    workspace_inspect.add_argument("--report", type=Path)
    workspace_check = workspace_commands.add_parser(
        "check", help="Run all acceptance gates without writing an archive."
    )
    workspace_check.add_argument("path", type=Path)
    workspace_check.add_argument("--report", type=Path)
    workspace_build = workspace_commands.add_parser(
        "build", help="Run acceptance and write the accepted archive and report."
    )
    workspace_build.add_argument("path", type=Path)
    workspace_build.add_argument("--output", type=Path)
    workspace_build.add_argument("--report", type=Path)
    workspace_install = workspace_commands.add_parser(
        "install", help="Build when needed, then validate and install for local development."
    )
    workspace_install.add_argument("path", type=Path)
    workspace_install.add_argument("--artifact", type=Path)
    workspace_install.add_argument("--report", type=Path)
    workspace_model = workspace_commands.add_parser(
        "model", help="Inspect, replace, tensorize, or check this workspace's frozen Actor."
    )
    workspace_model_commands = workspace_model.add_subparsers(
        dest="workspace_model_command", required=True
    )
    workspace_model_inspect = workspace_model_commands.add_parser("inspect")
    workspace_model_inspect.add_argument("path", type=Path)
    workspace_model_inspect.add_argument("--artifact", type=Path)
    workspace_model_inspect.add_argument("--report", type=Path)
    workspace_model_import = workspace_model_commands.add_parser("import")
    workspace_model_import.add_argument("path", type=Path)
    workspace_model_import.add_argument("--source", type=Path, required=True)
    workspace_model_import.add_argument("--model-id")
    workspace_model_import.add_argument(
        "--training-method",
        choices=("bc", "rl", "bc_rl", "hybrid", "other"),
        default="other",
    )
    workspace_model_import.add_argument("--source-run-id", default="developer-import")
    workspace_model_import.add_argument("--report", type=Path)
    workspace_model_tensorize = workspace_model_commands.add_parser("tensorize")
    workspace_model_tensorize.add_argument("path", type=Path)
    workspace_model_tensorize.add_argument("--scenario", type=Path, required=True)
    workspace_model_tensorize.add_argument("--output", type=Path)
    workspace_model_tensorize.add_argument("--report", type=Path)
    workspace_model_check = workspace_model_commands.add_parser("conformance")
    workspace_model_check.add_argument("path", type=Path)
    workspace_model_check.add_argument("--report", type=Path)
    build = commands.add_parser("build", help="Build one deterministic test-fixture .ptcgai archive.")
    build.add_argument("--source", type=Path, required=True, help="Package source directory.")
    build.add_argument("--output", type=Path, required=True, help="New .ptcgai path; it must not exist.")
    build.add_argument("--report", type=Path, help="Write the JSON report to this path.")
    release_key = commands.add_parser(
        "release-key", help="Generate a non-overwriting Ed25519 key for registered releases."
    )
    release_key.add_argument("--private-key", type=Path, required=True)
    release_key.add_argument("--public-key", type=Path, required=True)
    release_key.add_argument("--report", type=Path)
    release_build = commands.add_parser(
        "release-build", help="Build a deterministic .ptcgai with a registered developer key."
    )
    release_build.add_argument("--source", type=Path, required=True)
    release_build.add_argument("--output", type=Path, required=True)
    release_build.add_argument("--private-key", type=Path, required=True)
    release_build.add_argument("--report", type=Path)
    release_resign = commands.add_parser(
        "release-resign", help="Replace only a validated package signature with a registered developer key."
    )
    release_resign.add_argument("--package", type=Path, required=True)
    release_resign.add_argument("--output", type=Path, required=True)
    release_resign.add_argument("--private-key", type=Path, required=True)
    release_resign.add_argument("--report", type=Path)
    validate = commands.add_parser("validate", help="Strictly validate a package through the runtime Host compile path.")
    validate.add_argument("--package", type=Path, required=True, help="Package archive to validate.")
    validate.add_argument("--report", type=Path, help="Write the JSON report to this path.")
    simulate = commands.add_parser("simulate", help="Run one public current-window scenario.")
    simulate.add_argument("--package", type=Path, required=True, help="Package archive to simulate.")
    simulate.add_argument("--scenario", type=Path, required=True, help="Scenario JSON document.")
    simulate.add_argument("--report", type=Path, help="Write the JSON report to this path.")
    test = commands.add_parser("test", help="Run a strict public scenario suite.")
    test.add_argument("--package", type=Path, required=True, help="Package archive under test.")
    test.add_argument("--suite", type=Path, required=True, help="Scenario-suite JSON document.")
    test.add_argument("--report", type=Path, help="Write the JSON report to this path.")
    check = commands.add_parser("check", help="Double-build, validate, and test an entire author workspace.")
    check.add_argument("--workspace", type=Path, required=True, help="Workspace containing package/ and scenario-suite.json.")
    check.add_argument("--output", type=Path, help="Write the accepted package here only after every gate passes.")
    check.add_argument("--report", type=Path, help="Write the JSON acceptance report to this path.")
    install = commands.add_parser("install", help="Validate and install a development-only package into Godot user data.")
    install.add_argument("--package", type=Path, required=True, help="Development package archive to install.")
    install.add_argument("--report", type=Path, help="Write the JSON report to this path.")
    publish_parser = commands.add_parser("publish", help="Submit a validated release to the strategy platform.")
    publish_parser.add_argument("--endpoint", required=True)
    publish_parser.add_argument("--strategy-id", required=True)
    publish_parser.add_argument("--package", type=Path, required=True)
    publish_parser.add_argument("--allow-insecure-loopback", action="store_true")
    publish_parser.add_argument("--report", type=Path)
    demo = commands.add_parser("demo", help="Reproduce the complete Marnie RED-to-GREEN acceptance workflow.")
    demo.add_argument("--output", type=Path, required=True)
    demo.add_argument("--report", type=Path)
    regenerate = commands.add_parser("regenerate-demo-scenarios", help="Deterministically rebuild the demo's ten scenarios.")
    regenerate.add_argument("--report", type=Path)
    ucis = commands.add_parser("ucis", help="Inspect the pinned UCIS catalog and current-window SDK.")
    ucis_commands = ucis.add_subparsers(dest="ucis_command", required=True)
    ucis_catalog = ucis_commands.add_parser(
        "catalog", help="Show generation, primitives, closure, and unsupported effects."
    )
    ucis_catalog.add_argument("--report", type=Path)
    ucis_inspect = ucis_commands.add_parser(
        "inspect", help="Inspect one public Forge scenario without echoing its raw observation."
    )
    ucis_inspect.add_argument("--scenario", type=Path, required=True)
    ucis_inspect.add_argument("--report", type=Path)
    ucis_walkthrough = ucis_commands.add_parser(
        "walkthrough",
        help="Run exact-count, semantic-rebind, public-fact, and fail-closed examples.",
    )
    ucis_walkthrough.add_argument("--report", type=Path)
    model = commands.add_parser(
        "model", help="Low-level artifact operations; prefer `workspace model` for a workspace."
    )
    model_commands = model.add_subparsers(dest="model_command", required=True)
    model_inspect = model_commands.add_parser("inspect")
    model_inspect.add_argument("--artifact", type=Path, required=True)
    model_inspect.add_argument("--report", type=Path)
    model_import = model_commands.add_parser("import")
    model_import.add_argument("--source", type=Path, required=True)
    model_import.add_argument("--output", type=Path, required=True)
    model_import.add_argument("--manifest", type=Path, required=True)
    model_import.add_argument("--model-id", required=True)
    model_import.add_argument("--report", type=Path)
    model_tensorize = model_commands.add_parser("tensorize")
    model_tensorize.add_argument("--context", type=Path, required=True)
    model_tensorize.add_argument("--output", type=Path, required=True)
    model_tensorize.add_argument("--report", type=Path)
    model_check = model_commands.add_parser("conformance")
    model_check.add_argument("--artifact", type=Path, required=True)
    model_check.add_argument("--report", type=Path)
    from .iteration_cli import register
    register(commands, workspace_commands)
    args = parser.parse_args()
    try:
        if hasattr(args, "iteration_handler"):
            report = args.iteration_handler(args)
        elif args.command == "workspace":
            if args.workspace_command == "create":
                if args.account:
                    from .control_workflow import authenticated_client
                    account = authenticated_client(args).me()
                    args.author_id = account['developer_id']
                    args.author_name = args.author_name or account.get('display_name') or args.author_id
                developer_workspace = StrategyWorkspace.create(
                    args.path,
                    author_id=args.author_id,
                    author_name=args.author_name,
                    package_id=args.package_id,
                    package_version=args.package_version,
                    strategy_name=args.strategy_name,
                    summary=args.summary,
                    mode=args.mode,
                    deck_id=args.deck_id,
                )
                status = developer_workspace.status()
                report = {
                    "document_type": "ptcg_strategy_forge_workspace_create_v1",
                    "schema_version": 1,
                    "status": "created",
                    "workspace": {
                        "path": str(developer_workspace.root),
                        **status["package"],
                    },
                    "scenarios": status["scenarios"],
                    "edit": status["edit"],
                    "outputs": status["outputs"],
                    "next_actions": status["next_actions"],
                    "claims": status["claims"],
                }
            else:
                developer_workspace = StrategyWorkspace.open(args.path)
                if args.workspace_command == "status":
                    report = developer_workspace.status()
                elif args.workspace_command == "inspect":
                    report = developer_workspace.inspect(args.scenario)
                elif args.workspace_command == "check":
                    report = developer_workspace.check()
                elif args.workspace_command == "build":
                    report = developer_workspace.build(args.output, report=args.report)
                elif args.workspace_command == "install":
                    report = developer_workspace.install(args.artifact)
                elif args.workspace_model_command == "inspect":
                    report = developer_workspace.model.inspect(args.artifact)
                elif args.workspace_model_command == "import":
                    report = developer_workspace.model.import_actor(
                        args.source,
                        model_id=args.model_id,
                        training_method=args.training_method,
                        source_run_id=args.source_run_id,
                    )
                elif args.workspace_model_command == "tensorize":
                    report = developer_workspace.model.tensorize(args.scenario, args.output)
                else:
                    report = developer_workspace.model.conformance()
        elif args.command == "model":
            if args.model_command == "inspect":
                report = (
                    inspect_onnx(args.artifact)
                    if args.artifact.suffix.casefold() == ".onnx"
                    else inspect_ort(args.artifact)
                )
            elif args.model_command == "import":
                report = _model_import(args.source, args.output, args.manifest, args.model_id)
            elif args.model_command == "tensorize":
                report = _model_tensorize(args.context, args.output)
            else:
                report = model_conformance(args.artifact)
        elif args.command == "ucis":
            if args.ucis_command == "catalog":
                report = ucis_catalog_report()
            elif args.ucis_command == "inspect":
                report = inspect_ucis_scenario(args.scenario)
            else:
                report = run_ucis_sdk_walkthrough()
        elif args.command == "doctor":
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
            report["developer_files"] = _write_workspace_guides(args.output)
            if args.deck_id is None:
                report["scenario_suite"] = generate_demo_scenarios(
                    args.output,
                    matched_rule_id="marnie.morgrem.evolve",
                    scenario_namespace="workspace",
                )
            else:
                reviewed = customize_reviewed_workspace(args.output, args.deck_id, args.package_id)
                report["reviewed_deck"] = reviewed
                report["scenario_suite"] = reviewed["scenario_suite"]
            if args.policy_mode == "model":
                report["model"] = _configure_model_workspace(args.output)
            else:
                report["rules"] = _configure_rules_workspace(args.output)
        elif args.command == "build":
            report = build_development_package(args.source, args.output)
        elif args.command == "release-key":
            report = generate_release_key(args.private_key, args.public_key)
        elif args.command == "release-build":
            report = build_registered_release(args.source, args.output, args.private_key)
        elif args.command == "release-resign":
            report = resign_registered_release(args.package, args.output, args.private_key)
        elif args.command == "validate":
            report = validate_development_package(args.package)
        elif args.command == "simulate":
            scenario_document = load_json(args.scenario)
            report = (
                simulate_competitive_public_frame(args.package, args.scenario)
                if is_competitive_scenario(scenario_document)
                else simulate_public_window(args.package, args.scenario)
            )
        elif args.command == "test":
            report = run_suite(args.package, args.suite)
        elif args.command == "check":
            if args.output is not None and args.report is not None:
                try:
                    if args.output.resolve(strict=False) == args.report.resolve(strict=False):
                        raise ValueError("workspace_check_paths_conflict")
                except OSError as error:
                    raise ValueError("workspace_check_paths_conflict") from error
            report = check_workspace(args.workspace, output=args.output)
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
        if report.get('document_type') == 'forge_release_wait_v1' and report.get('status') != 'passed':
            return 2
        return 0 if report.get("status") not in {"failed", "error", "timeout", "cancelled"} else 2
    except (
        DeveloperToolError,
        OrtActorError,
        PublishError,
        WorkspaceError,
        ValueError,
        OSError,
    ) as error:
        code = error.code if isinstance(error, (DeveloperToolError, OrtActorError, WorkspaceError)) else str(error)
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
