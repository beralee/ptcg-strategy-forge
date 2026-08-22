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

from ptcg_strategy_forge.cli import _emit, doctor, run_suite  # noqa: E402
from ptcg_strategy_forge.provenance import load_manifest, verify_snapshot  # noqa: E402
from ptcg_strategy_forge.scenarios import (  # noqa: E402
    assert_public_report,
    generate_demo_scenarios,
    write_json,
)
from tools.ptcgdap.author_strategy_developer import validate_development_package  # noqa: E402
from tools.ptcgdap.author_strategy_developer import build_development_package  # noqa: E402


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
            package = root / "integration.ptcgai"
            build_development_package(workspace / "package", package)
            report = run_suite(package, workspace / "scenario-suite.json")
            self.assertEqual("passed", report["status"])
            self.assertEqual((10, 10), (report["passed_count"], report["case_count"]))

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
        markdown_files = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "TODO.md", *sorted((ROOT / "docs").glob("*.md"))]
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
        rows = re.findall(r"^\| (T\d{2}) \|.*\| (DONE|PENDING) \|", text, flags=re.MULTILINE)
        self.assertEqual(12, len(rows))
        self.assertEqual(12, len({row[0] for row in rows}))


if __name__ == "__main__":
    unittest.main()
