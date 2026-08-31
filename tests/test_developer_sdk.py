from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ptcg_strategy_forge import StrategyWorkspace, WorkspaceError  # noqa: E402


class DeveloperSdkTests(unittest.TestCase):
    def test_create_rules_workspace_has_convention_defaults_and_next_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "my-deck"
            workspace = StrategyWorkspace.create(path, author_id="alice.dev")

            self.assertEqual(path.resolve(), workspace.root)
            self.assertEqual("dev.alice.dev.my-deck", workspace.package_id)
            self.assertEqual("My Deck", workspace.strategy_name)
            self.assertEqual("rules_only", workspace.policy_mode)

            status = workspace.status()
            self.assertEqual("ptcg_strategy_forge_workspace_status_v1", status["document_type"])
            self.assertEqual("ready", status["status"])
            self.assertEqual(10, status["scenarios"]["count"])
            self.assertEqual("package/policy/adapter.json", status["edit"]["rules"])
            self.assertEqual("STRATEGY-BLUEPRINT.md", status["edit"]["strategy"])
            self.assertEqual(
                "build/dev.alice.dev.my-deck-0.1.0.ptcgai",
                status["outputs"]["artifact"],
            )
            self.assertEqual(
                ["status", "inspect", "check", "build", "install"],
                [row["action"] for row in status["next_actions"]],
            )
            inspected = workspace.inspect()
            self.assertEqual(
                "ptcg_strategy_forge_ucis_scenario_inspection_v1",
                inspected["document_type"],
            )
            self.assertEqual("passed", inspected["status"])

            guide = (path / "README.md").read_text(encoding="utf-8")
            self.assertIn("forge.py workspace status", guide)
            self.assertIn("forge.py workspace check", guide)
            self.assertIn("forge.py workspace build", guide)

    def test_create_model_workspace_exposes_model_facade(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workspace = StrategyWorkspace.create(
                Path(temp_name) / "actor-policy",
                author_id="alice",
                mode="model",
            )

            self.assertEqual("rules_with_model", workspace.policy_mode)
            status = workspace.status()
            self.assertEqual("package/model/actor.ort", status["edit"]["model"])
            self.assertEqual("ready", status["model"]["status"])
            self.assertEqual("passed", workspace.model.conformance()["status"])

            imported = workspace.model.import_actor(
                workspace.root / "model-source/actor.onnx",
                training_method="bc",
                source_run_id="unit-test-bc",
            )
            self.assertEqual("imported", imported["status"])
            self.assertEqual("passed", imported["conformance"]["status"])
            manifest = json.loads(
                (workspace.root / "package/model/model_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual("bc", manifest["provenance"]["training_method"])
            tensors = workspace.model.tensorize("scenarios/01-positive.json")
            self.assertEqual("written", tensors["status"])
            self.assertTrue((workspace.root / "build/01-positive-tensors.json").is_file())
            with self.assertRaises(WorkspaceError) as hidden:
                workspace.model.tensorize("scenarios/10-hidden-field.json")
            self.assertEqual("model_hidden_field", hidden.exception.code)
            with self.assertRaises(WorkspaceError) as unknown:
                workspace.model.tensorize("scenarios/09-unknown-uid.json")
            self.assertEqual("model_unknown_uid", unknown.exception.code)

    def test_open_fails_closed_with_stable_error_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            with self.assertRaises(WorkspaceError) as raised:
                StrategyWorkspace.open(Path(temp_name))
            self.assertEqual("workspace_manifest_missing", raised.exception.code)

    def test_failed_create_does_not_leave_a_partial_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "invalid-deck"
            with self.assertRaises(WorkspaceError):
                StrategyWorkspace.create(path, author_id="alice", deck_id=-1)
            self.assertFalse(path.exists())
            invalid_version = Path(temp_name) / "invalid-version"
            with self.assertRaises(WorkspaceError) as raised:
                StrategyWorkspace.create(
                    invalid_version,
                    author_id="alice",
                    package_version="../escape",
                )
            self.assertEqual("workspace_package_version_invalid", raised.exception.code)
            self.assertFalse(invalid_version.exists())

    def test_open_rejects_unsafe_artifact_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workspace = StrategyWorkspace.create(Path(temp_name) / "safe", author_id="alice")
            manifest_path = workspace.root / "package/strategy_package.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["package_id"] = "../escape"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(WorkspaceError) as raised:
                StrategyWorkspace.open(workspace.root)
            self.assertEqual("workspace_manifest_invalid", raised.exception.code)

    def test_workspace_cli_is_the_short_primary_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "cli-workspace"
            create = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "forge.py"),
                    "workspace",
                    "create",
                    str(path),
                    "--author-id",
                    "cli.dev",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, create.returncode, create.stderr or create.stdout)
            created = json.loads(create.stdout)
            self.assertEqual("created", created["status"])
            self.assertEqual("dev.cli.dev.cli-workspace", created["workspace"]["package_id"])

            status_run = subprocess.run(
                [sys.executable, str(ROOT / "forge.py"), "workspace", "status", str(path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, status_run.returncode, status_run.stderr or status_run.stdout)
            status = json.loads(status_run.stdout)
            self.assertEqual("ready", status["status"])

    def test_empty_directory_to_default_artifact_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            workspace = StrategyWorkspace.create(
                Path(temp_name) / "first-success",
                author_id="acceptance.dev",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "forge.py"),
                    "workspace",
                    "build",
                    str(workspace.root),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            report = json.loads(completed.stdout)
            self.assertEqual("passed", report["status"])
            self.assertTrue(report["build"]["deterministic"])
            self.assertEqual((10, 10), (report["scenarios"]["passed_count"], report["scenarios"]["case_count"]))
            self.assertTrue(workspace.default_artifact.is_file())
            self.assertTrue(workspace.default_report.is_file())


if __name__ == "__main__":
    unittest.main()
