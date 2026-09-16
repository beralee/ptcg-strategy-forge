from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ptcg_strategy_forge import StrategyWorkspace, WorkspaceError


class FoundationTests(unittest.TestCase):
    def test_identical_build_reuses_verified_archive_and_retains_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = StrategyWorkspace.create(Path(temp) / "deck", author_id="local.dev")
            def accepted(root, *, output):
                output.write_bytes(b"test-only-accepted-archive")
                return {"status": "passed", "artifact": {"written": True, "path": str(output)}}
            with patch("ptcg_strategy_forge.application.check_workspace", side_effect=accepted) as check:
                first = workspace.build()
                second = workspace.build()
                self.assertEqual(1, check.call_count)
            self.assertEqual(first["record"], second["record"])
            receipt = json.loads(Path(first["record"]["path"]).read_bytes())
            archived = workspace.root / receipt["archive_relative_path"]
            self.assertEqual(workspace.default_artifact.read_bytes(), archived.read_bytes())
            archived.write_bytes(b"tampered")
            self.assertEqual("stale", workspace.status()["acceptance"]["status"])

    def test_model_status_uses_hash_bound_evidence_without_inference(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = StrategyWorkspace.create(Path(temp) / "deck", author_id="local.dev", mode="model")
            with patch("ptcg_strategy_forge.sdk.model_conformance", side_effect=AssertionError("status must not infer")):
                self.assertEqual("ready", workspace.status()["model"]["status"])

    def test_rules_sdk_does_not_import_model_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            code = "import sys; sys.modules.update({name: None for name in ('numpy', 'onnx', 'onnxruntime')}); from ptcg_strategy_forge import StrategyWorkspace; StrategyWorkspace.create('deck', author_id='local.dev')"
            process = subprocess.run([sys.executable, "-B", "-c", code], cwd=temp, env=env, capture_output=True, text=True)
            self.assertEqual(0, process.returncode, process.stderr)

    def test_nested_first_workspace_and_no_cli_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(sys.modules, {"ptcg_strategy_forge.cli": None}):
                workspace = StrategyWorkspace.create(Path(temp) / "new" / "nested" / "deck", author_id="local.dev")
            self.assertEqual("ready", workspace.status()["status"])

    def test_install_rejects_changed_source_before_touching_game(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = StrategyWorkspace.create(Path(temp) / "deck", author_id="local.dev")
            workspace.build()
            adapter = workspace.root / "package/policy/adapter.json"
            adapter.write_text(adapter.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with patch("ptcg_strategy_forge.sdk.install_development_package") as install:
                with self.assertRaisesRegex(WorkspaceError, "workspace_artifact_stale"):
                    workspace.install()
                install.assert_not_called()

    def test_suite_change_invalidates_evidence_and_old_receipt_survives(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = StrategyWorkspace.create(Path(temp) / "deck", author_id="local.dev")
            report = workspace.build()
            receipt = Path(report["record"]["path"])
            original = receipt.read_bytes()
            suite = workspace.root / "scenario-suite.json"
            suite.write_text(suite.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            self.assertEqual("stale", workspace.status()["acceptance"]["status"])
            self.assertEqual(original, receipt.read_bytes())

    def test_artifact_tamper_invalidates_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = StrategyWorkspace.create(Path(temp) / "deck", author_id="local.dev")
            workspace.build()
            workspace.default_artifact.write_bytes(b"broken")
            self.assertEqual("stale", workspace.status()["acceptance"]["status"])

    def test_direct_sdk_import_outside_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT / "src")
            process = subprocess.run([sys.executable, "-B", "-c",
                "from ptcg_strategy_forge import StrategyWorkspace; print(StrategyWorkspace.__name__)"],
                cwd=temp, env=env, capture_output=True, text=True)
            self.assertEqual(0, process.returncode, process.stderr)

    def test_report_path_cannot_destroy_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = StrategyWorkspace.create(Path(temp) / "deck", author_id="local.dev")
            with self.assertRaisesRegex(WorkspaceError, "workspace_check_paths_conflict"):
                workspace.build(report=workspace.default_artifact)
            self.assertFalse(workspace.default_artifact.exists())

    def test_source_mutation_during_acceptance_never_publishes(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = StrategyWorkspace.create(Path(temp) / "deck", author_id="local.dev")
            def changed(root, *, output):
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"validated-before-edit")
                with (root / "scenario-suite.json").open("a") as stream:
                    stream.write("\n")
                return {"status": "passed", "artifact": {"written": True, "path": str(output)}}
            with patch("ptcg_strategy_forge.application.check_workspace", side_effect=changed):
                with self.assertRaisesRegex(WorkspaceError, "workspace_source_changed_during_build"):
                    workspace.build()
            self.assertFalse(workspace.default_artifact.exists())

    def test_report_cannot_overwrite_workspace_source(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = StrategyWorkspace.create(Path(temp) / "deck", author_id="local.dev")
            with self.assertRaisesRegex(WorkspaceError, "workspace_check_paths_conflict"):
                workspace.build(report=workspace.manifest_path)

    def test_custom_report_preserves_default_latest_pointer(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = StrategyWorkspace.create(Path(temp) / "deck", author_id="local.dev")
            def accepted(root, *, output):
                output.write_bytes(b"test-only-accepted-archive")
                return {"status": "passed", "artifact": {"written": True, "path": str(output)}}
            with patch("ptcg_strategy_forge.application.check_workspace", side_effect=accepted):
                workspace.build(report=Path(temp) / "custom.json")
            self.assertEqual("current", workspace.status()["acceptance"]["status"])
