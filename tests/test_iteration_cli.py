import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class IterationCliTests(unittest.TestCase):
    def test_recent_games_deduplicate_paired_series_before_download_budget(self):
        from ptcg_strategy_forge.services import matches
        from unittest.mock import patch
        from contextlib import nullcontext
        from io import BytesIO
        games = [{"series_id": series, "replay_available": True} for series in ("series-a", "series-a", "series-b")]
        with patch("ptcg_strategy_forge.replays.NetworkBudget") as budget, patch("urllib.request.build_opener") as opener:
            budget.return_value.acquire.return_value = nullcontext()
            opener.return_value.open.return_value = BytesIO(json.dumps({"recent_games": games}).encode())
            result = matches("https://api.example.test", "release-1")
        self.assertEqual(3, result["scanned"])
        self.assertEqual(["series-a", "series-b"], [entry["id"] for entry in result["entries"]])

    def test_sdk_recent_matches_uses_shared_network_budget(self):
        from ptcg_strategy_forge import StrategyWorkspace
        from unittest.mock import patch, Mock
        from contextlib import nullcontext
        from io import BytesIO
        with tempfile.TemporaryDirectory() as temp:
            workspace = StrategyWorkspace.create(Path(temp) / "deck", author_id="local.dev")
            with patch("ptcg_strategy_forge.replays.NetworkBudget") as budget, patch("urllib.request.build_opener") as opener:
                budget.return_value.acquire.return_value = nullcontext()
                opener.return_value.open.return_value = BytesIO(b'{"recent_games": []}')
                result = workspace.matches("http://127.0.0.1:8765", "release-1")
                self.assertEqual(0, result["scanned"])
                budget.return_value.acquire.assert_called_once()

    def run_cli(self, *args):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "forge.py"), *map(str, args)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        return json.loads(result.stdout)

    def test_sdk_facades_and_cli_dataset_roundtrip(self):
        from ptcg_strategy_forge import StrategyWorkspace
        from tests.test_bc_dataset import BcDatasetTests
        with tempfile.TemporaryDirectory() as temp:
            workspace = StrategyWorkspace.create(Path(temp) / "deck", author_id="local.dev")
            self.assertIsNotNone(workspace.replays)
            self.assertIsNotNone(workspace.dataset)
            trace = Path(temp) / "trace.json"
            trace.write_text(json.dumps(BcDatasetTests().trace()), encoding="utf-8")
            built = self.run_cli("workspace", "dataset", "build", workspace.root, "--source", trace, "--allow-fixture")
            audited = self.run_cli("workspace", "dataset", "audit", workspace.root, "--dataset", built["dataset_id"])
            self.assertEqual("passed", audited["status"])
            stats = self.run_cli("workspace", "dataset", "stats", workspace.root, "--dataset", built["dataset_id"])
            self.assertEqual(1, stats["row_count"])

    def test_cards_and_service_capabilities_are_explicit(self):
        cards = self.run_cli("cards", "search", "CSV10C_146")
        self.assertEqual("CSV10C_146", cards["cards"][0]["card_uid"])
        capabilities = self.run_cli("service", "capabilities", "--profile", "dojo")
        self.assertFalse(capabilities["capabilities"]["decision_trace"])

    def test_version_and_upgrade_are_explicit_and_preserve_backup(self):
        from ptcg_strategy_forge import StrategyWorkspace
        with tempfile.TemporaryDirectory() as temp:
            workspace = StrategyWorkspace.create(Path(temp) / "deck", author_id="local.dev")
            original = workspace.manifest_path.read_bytes()
            preview = self.run_cli("workspace", "upgrade", workspace.root, "--dry-run")
            self.assertEqual("preview", preview["status"])
            self.assertFalse((workspace.root / ".forge/workspace.json").exists())
            self.run_cli("workspace", "upgrade", workspace.root)
            changed = self.run_cli("workspace", "version", "bump", workspace.root, "--part", "patch")
            self.assertEqual("0.1.1", workspace.package_version)
            self.assertEqual(original, Path(changed["backup"]).read_bytes())


if __name__ == "__main__":
    unittest.main()
