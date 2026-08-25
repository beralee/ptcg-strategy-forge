from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ptcg_strategy_forge.cli import _emit, check_workspace, doctor, run_suite  # noqa: E402
from ptcg_strategy_forge.provenance import load_manifest, verify_snapshot  # noqa: E402
from ptcg_strategy_forge.scenarios import (  # noqa: E402
    assert_public_report,
    generate_demo_scenarios,
    write_json,
)
from tools.ptcgdap.author_strategy_developer import validate_development_package  # noqa: E402


RELEASE = ROOT / "demo/releases/strategy-forge-marnie-demo-1.0.0.ptcgai"
EXPECTED_RELEASE_SHA256 = "7F53F2DC698B0290DFC46C5E439B02439E4849B9522235B547EE5649EDA0D33A"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def all_keys(value: object) -> set[str]:
    found: set[str] = set()
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            found.update(str(key).casefold() for key in current)
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return found


class ForgeTests(unittest.TestCase):
    def test_console_report_falls_back_to_ascii_on_legacy_code_page(self) -> None:
        raw = io.BytesIO()
        console = io.TextIOWrapper(raw, encoding="cp1252", errors="strict", newline="\n")
        with mock.patch("ptcg_strategy_forge.cli.sys.stdout", console):
            _emit({"status": "passed", "strategy": "魔法少女"}, None)
            console.flush()
        rendered = raw.getvalue().decode("cp1252")
        self.assertEqual("魔法少女", json.loads(rendered)["strategy"])
        self.assertIn("\\u", rendered)

    def test_doctor_passes_on_python_313_and_pinned_sdk(self) -> None:
        report = doctor()
        self.assertEqual("passed", report["status"])
        checks = {row["id"]: row for row in report["checks"]}
        self.assertTrue(checks["python"]["accepted"])
        self.assertGreaterEqual(checks["sdk-snapshot"]["file_count"], 276)
        self.assertTrue(checks["contract-drift"]["accepted"])
        self.assertTrue(checks["template-package"]["accepted"])

    def test_sdk_manifest_rejects_unmanifested_file(self) -> None:
        manifest = load_manifest(ROOT)
        with tempfile.TemporaryDirectory() as temp_name:
            clone = Path(temp_name)
            target_manifest = clone / "vendor/ptcgdap-sdk-manifest.json"
            target_manifest.parent.mkdir(parents=True)
            shutil.copy2(ROOT / "vendor/ptcgdap-sdk-manifest.json", target_manifest)
            for row in manifest["files"]:
                source = ROOT / row["path"]
                target = clone / row["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            self.assertTrue(verify_snapshot(clone)["accepted"])
            extra = clone / "tools/ptcgdap/unreviewed.py"
            extra.write_text("pass\n", encoding="utf-8")
            result = verify_snapshot(clone)
            self.assertFalse(result["accepted"])
            self.assertIn("sdk_file_unmanifested", {row["error_code"] for row in result["failures"]})

    def test_demo_release_is_strictly_valid(self) -> None:
        self.assertEqual(EXPECTED_RELEASE_SHA256, sha(RELEASE))
        report = validate_development_package(RELEASE)
        self.assertEqual("valid", report["status"])
        self.assertEqual("dev.beralee.marnie-forge-demo", report["package_id"])
        self.assertEqual("test_fixture_only", report["signature_scope"])
        self.assertFalse(report["execution_trusted"])
        self.assertFalse(report["production_ready"])

    def test_green_demo_evidence_proves_red_green_and_determinism(self) -> None:
        report = json.loads((ROOT / "evidence/demo-workflow-green.json").read_text(encoding="utf-8"))
        self.assertEqual("passed", report["status"])
        self.assertTrue(report["optimization"]["baseline_red"])
        self.assertEqual((10, 10), (report["optimization"]["final_scenario_passed"], report["optimization"]["final_scenario_total"]))
        self.assertEqual("passed", report["ucis_sdk"]["status"])
        self.assertEqual([0, 2, 4], report["ucis_sdk"]["exact_quantity"]["first_indexes"])
        self.assertEqual([4, 2, 0], report["ucis_sdk"]["exact_quantity"]["reordered_indexes"])
        self.assertTrue(report["build"]["deterministic"])
        self.assertEqual(EXPECTED_RELEASE_SHA256, report["build"]["archive_sha256"])
        self.assertEqual(report["build"]["archive_sha256"], report["build"]["second_archive_sha256"])
        self.assertFalse(report["claims"]["production_ready"])

    def test_demo_scenario_generation_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            demo = Path(temp_name) / "demo"
            shutil.copytree(ROOT / "demo/marnie-forge", demo)
            generate_demo_scenarios(demo)
            first = {path.relative_to(demo).as_posix(): path.read_bytes() for path in sorted((demo / "scenarios").glob("*.json"))}
            first["scenario-suite.json"] = (demo / "scenario-suite.json").read_bytes()
            generate_demo_scenarios(demo)
            second = {path.relative_to(demo).as_posix(): path.read_bytes() for path in sorted((demo / "scenarios").glob("*.json"))}
            second["scenario-suite.json"] = (demo / "scenario-suite.json").read_bytes()
            self.assertEqual(first, second)
            self.assertEqual(10, len(list((demo / "scenarios").glob("*.json"))))

    def test_new_workspace_builds_and_passes_generated_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            workspace = root / "workspace"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "forge.py"),
                    "new",
                    "--output",
                    str(workspace),
                    "--package-id",
                    "dev.example.integration",
                    "--author-id",
                    "example.integration",
                    "--author-name",
                    "Integration Test",
                    "--strategy-name",
                    "Integration Strategy",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            manifest = json.loads((workspace / "package/strategy_package.json").read_text(encoding="utf-8"))
            self.assertEqual("Integration Strategy", manifest["strategy"]["display_name"])
            blueprint = (workspace / "STRATEGY-BLUEPRINT.md").read_text(encoding="utf-8")
            self.assertIn("Integration Strategy", blueprint)
            self.assertIn("攻击窗口", blueprint)
            self.assertIn("信息动作", blueprint)
            self.assertIn("重观察", blueprint)
            self.assertIn("Base Graph", blueprint)
            sdk_guide = (workspace / "UCIS-SDK.md").read_text(encoding="utf-8")
            self.assertIn("ucis inspect", sdk_guide)
            self.assertIn("不会装进游戏", sdk_guide)
            package = root / "integration.ptcgai"
            report = check_workspace(workspace, output=package)
            self.assertEqual("passed", report["status"])
            self.assertTrue(report["build"]["deterministic"])
            self.assertEqual("valid", report["validation"]["status"])
            self.assertEqual((10, 10), (report["scenarios"]["passed_count"], report["scenarios"]["case_count"]))
            self.assertEqual(sha(package), report["build"]["archive_sha256"])
            self.assertFalse(report["claims"]["production_ready"])

    def test_new_workspace_supports_reviewed_non_marnie_deck(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            workspace = root / "gardevoir"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "forge.py"),
                    "new",
                    "--output",
                    str(workspace),
                    "--deck-id",
                    "800017097",
                    "--package-id",
                    "dev.example.gardevoir",
                    "--package-version",
                    "1.0.0",
                    "--author-id",
                    "example.integration",
                    "--author-name",
                    "Integration Test",
                    "--strategy-name",
                    "18.0 无碟沙奈朵策略",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            manifest = json.loads((workspace / "package/strategy_package.json").read_text(encoding="utf-8"))
            deck = json.loads((workspace / "package/deck/deck_manifest.json").read_text(encoding="utf-8"))
            adapter = json.loads((workspace / "package/policy/adapter.json").read_text(encoding="utf-8"))
            suite = json.loads((workspace / "scenario-suite.json").read_text(encoding="utf-8"))
            self.assertEqual("18.0 无碟沙奈朵", manifest["deck"]["display_name"])
            self.assertEqual(800017097, deck["source_deck_id"])
            self.assertEqual(60, deck["card_count"])
            self.assertEqual(24, deck["unique_card_count"])
            self.assertIn("gardevoir.kirlia.evolve", {row["rule_id"] for row in adapter["rules"]})
            self.assertEqual(10, len(suite["cases"]))
            report = check_workspace(workspace, output=root / "gardevoir.ptcgai")
            self.assertEqual("passed", report["status"])
            self.assertEqual((10, 10), (report["scenarios"]["passed_count"], report["scenarios"]["case_count"]))

    def test_suite_rejects_path_traversal_before_simulation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            write_json(root / "suite.json", {
                "document_type": "ptcg_strategy_forge_scenario_suite_v1",
                "schema_version": 1,
                "cases": [{"id": "escape", "path": "../outside.json", "expect": {"status": "passed"}}],
            })
            with self.assertRaisesRegex(ValueError, "scenario_suite_invalid"):
                run_suite(RELEASE, root / "suite.json")

    def test_workspace_check_does_not_publish_when_scenarios_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            workspace = root / "workspace"
            (workspace / "package").mkdir(parents=True)
            (workspace / "scenario-suite.json").write_text("{}\n", encoding="utf-8")
            artifact = root / "rejected.ptcgai"

            def fake_build(_source: Path, output: Path) -> dict[str, object]:
                output.write_bytes(b"deterministic-package")
                return {
                    "package_id": "dev.example.rejected",
                    "package_version": "0.1.0",
                    "archive_sha256": "A" * 64,
                    "archive_bytes": 21,
                }

            with (
                mock.patch("ptcg_strategy_forge.cli.build_development_package", side_effect=fake_build),
                mock.patch("ptcg_strategy_forge.cli.validate_development_package", return_value={"status": "valid"}),
                mock.patch(
                    "ptcg_strategy_forge.cli.run_suite",
                    return_value={"status": "failed", "case_count": 1, "passed_count": 0, "cases": []},
                ),
            ):
                report = check_workspace(workspace, output=artifact)

            self.assertEqual("failed", report["status"])
            self.assertFalse(report["artifact"]["written"])
            self.assertFalse(artifact.exists())

    def test_workspace_check_rejects_existing_output_before_building(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            workspace = root / "workspace"
            (workspace / "package").mkdir(parents=True)
            (workspace / "scenario-suite.json").write_text("{}\n", encoding="utf-8")
            artifact = root / "existing.ptcgai"
            artifact.write_bytes(b"preserve-me")

            with mock.patch("ptcg_strategy_forge.cli.build_development_package") as build:
                with self.assertRaisesRegex(ValueError, "workspace_check_output_exists"):
                    check_workspace(workspace, output=artifact)
                build.assert_not_called()

            self.assertEqual(b"preserve-me", artifact.read_bytes())

    def test_private_keys_are_rejected_from_reports(self) -> None:
        for key in ("raw_observation", "opponent_hand", "search_begin_input", "ticket", "command"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "simulation_report_private_key"):
                assert_public_report({"safe": [{key: "secret"}]})

    def test_publish_receipt_is_bound_and_contains_no_credentials(self) -> None:
        receipt = json.loads((ROOT / "evidence/demo-publish-receipt.json").read_text(encoding="utf-8"))
        self.assertEqual(EXPECTED_RELEASE_SHA256, receipt["release"]["archive_sha256"])
        self.assertEqual("submitted", receipt["release"]["release_state"])
        self.assertFalse(receipt["credential_persisted"])
        self.assertFalse(receipt["production_authority"])
        self.assertEqual([], receipt["grants"])
        forbidden = {"token", "password", "secret", "authorization"}
        self.assertTrue(all(not any(word in key for word in forbidden) for key in all_keys(receipt)))

    def test_documentation_relative_links_exist(self) -> None:
        markdown_files = [ROOT / "AGENTS.md", ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "TODO.md", *sorted((ROOT / "docs").glob("*.md"))]
        pattern = re.compile(r"\[[^]]+\]\((?!https?://)([^)#]+)(?:#[^)]*)?\)")
        missing: list[str] = []
        for markdown in markdown_files:
            text = markdown.read_text(encoding="utf-8")
            for target in pattern.findall(text):
                path = (markdown.parent / target).resolve()
                if not path.exists():
                    missing.append(f"{markdown.relative_to(ROOT)} -> {target}")
        self.assertEqual([], missing)

    def test_todo_statuses_are_machine_auditable(self) -> None:
        text = (ROOT / "TODO.md").read_text(encoding="utf-8")
        rows = re.findall(
            r"^\| (T\d{2}) \|.*\| (DONE|PENDING|BLOCKED|OUT OF SCOPE) \|",
            text,
            flags=re.MULTILINE,
        )
        self.assertEqual({f"T{index:02d}" for index in range(1, 27)}, {row[0] for row in rows})
        statuses = dict(rows)
        self.assertEqual("PENDING", statuses["T19"])
        self.assertEqual("DONE", statuses["T20"])
        self.assertEqual("DONE", statuses["T21"])
        self.assertEqual("DONE", statuses["T22"])
        self.assertEqual("OUT OF SCOPE", statuses["T23"])
        self.assertEqual("DONE", statuses["T24"])
        self.assertEqual("DONE", statuses["T25"])
        self.assertEqual("DONE", statuses["T26"])
        self.assertTrue(all(statuses[f"T{index:02d}"] == "DONE" for index in range(1, 19)))

    def test_root_agent_charter_captures_strategy_and_process_invariants(self) -> None:
        charter = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for required in (
            "agent(raw_observation) -> list[int]",
            "当前 `select.option`",
            "重观察",
            "Base Graph",
            "RED→GREEN",
            "--workers 4",
        ):
            with self.subTest(required=required):
                self.assertIn(required, charter)


if __name__ == "__main__":
    unittest.main()
