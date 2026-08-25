from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ptcg_strategy_forge import competition
from tools.ptcgdap.competition_bundle import CompetitionBundleOwner


class CompetitionForgeV2Tests(unittest.TestCase):
    def _workspace(self, root: Path) -> Path:
        workspace = root / "workspace"
        report = competition.scaffold(
            workspace,
            strategy_id="community.agent",
            author_id="community.author",
            display_name="Community agent",
        )
        self.assertEqual("created", report["status"])
        return workspace

    def test_clean_workspace_runs_init_check_build_trace_and_prequalify(self) -> None:
        with tempfile.TemporaryDirectory(prefix="forge-competition-v2-") as temporary:
            root = Path(temporary)
            workspace = self._workspace(root)
            self.assertTrue((workspace / "src/submission/main.py").is_file())
            self.assertTrue((workspace / "src/submission/ucis.py").is_file())
            self.assertTrue((workspace / "runtime-lock.json").is_file())
            self.assertTrue((workspace / "STRATEGY-BLUEPRINT.md").is_file())

            suite = json.loads((workspace / "scenarios/smoke.json").read_text(encoding="utf-8"))
            selection = suite["cases"][1]["observation"]["select"]
            self.assertEqual(7, selection["context"])
            self.assertEqual(
                {
                    "type",
                    "context",
                    "minCount",
                    "maxCount",
                    "remainDamageCounter",
                    "remainEnergyCost",
                    "option",
                    "deck",
                    "contextCard",
                    "effect",
                },
                set(selection),
            )
            self.assertEqual(
                {"type", "area", "index", "playerIndex"},
                set(selection["option"][0]),
            )

            doctor = competition.doctor(workspace)
            self.assertEqual("passed", doctor["status"])
            self.assertTrue(doctor["gates"]["a1_scope_pinned"])
            self.assertFalse(doctor["a1"]["full_official_api_aligned"])
            checked = competition.check(workspace)
            self.assertEqual("passed", checked["status"])

            first = root / "first.ptcgbot"
            second = root / "second.ptcgbot"
            competition.build(workspace, first)
            competition.build(workspace, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            handle = CompetitionBundleOwner.load_default(ROOT).validate(first.read_bytes())
            self.assertEqual(2, handle.schema_generation)

            traced = competition.trace(
                first, workspace / "scenarios/smoke.json", public=True
            )
            self.assertEqual("passed", traced["status"])
            self.assertFalse(traced["hidden_fields_included"])
            self.assertEqual("official_card_ids", traced["trace"][0]["response_domain"])
            self.assertEqual(
                "current_option_indexes", traced["trace"][1]["response_domain"]
            )

            qualified = competition.prequalify(workspace)
            self.assertEqual("developer_local_qualified", qualified["status"])
            self.assertFalse(qualified["official_engine_parity"])
            self.assertEqual(
                doctor["a1"]["scope_sha256"],
                qualified["evidence"]["a1_scope_sha256"],
            )
            self.assertTrue(all(qualified["evidence"]["gates"].values()))
            self.assertEqual([], qualified["evidence"]["missing_profile_gates"])
            self.assertEqual(
                "agent_timeout",
                qualified["evidence"]["fault_probes"]["timeout"]["observed_code"],
            )

    def test_unknown_project_key_and_executable_resource_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="forge-competition-v2-bad-") as temporary:
            root = Path(temporary)
            workspace = self._workspace(root)
            config_path = workspace / "ptcgbot.toml"
            config_path.write_text(
                config_path.read_text(encoding="utf-8") + "\n[unknown]\nvalue=1\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                competition.CompetitionToolError, "competition_project_config_invalid"
            ):
                competition.check(workspace)

            clean = root / "clean"
            competition.scaffold(
                clean,
                strategy_id="community.agent2",
                author_id="community.author",
                display_name="Community agent two",
            )
            (clean / "resources/payload.pkl").write_bytes(b"not executable")
            with self.assertRaisesRegex(Exception, "competition_resource_type_forbidden"):
                competition.check(clean)

    def test_generated_ucis_runtime_sdk_is_pinned_and_tamper_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="forge-competition-v2-sdk-") as temporary:
            workspace = self._workspace(Path(temporary))
            sdk = workspace / "src/submission/ucis.py"
            sdk.write_text(sdk.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
            with self.assertRaisesRegex(
                competition.CompetitionToolError,
                "competition_ucis_runtime_sdk_mismatch",
            ):
                competition.check(workspace)

    def test_public_trace_never_echoes_observation_private_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="forge-competition-v2-trace-") as temporary:
            root = Path(temporary)
            workspace = self._workspace(root)
            suite_path = workspace / "scenarios/smoke.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["cases"][1]["observation"]["opponent_private_hand"] = [999]
            suite_path.write_text(
                json.dumps(suite, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            package = root / "agent.ptcgbot"
            competition.build(workspace, package)
            report = competition.trace(package, suite_path, public=True)
            rendered = json.dumps(report, ensure_ascii=False)
            self.assertNotIn("opponent_private_hand", rendered)
            self.assertNotIn("999", rendered)

    def test_scaffold_identity_is_validated_before_toml_generation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="forge-competition-v2-identity-") as temporary:
            with self.assertRaisesRegex(
                competition.CompetitionToolError, "competition_identity_invalid"
            ):
                competition.scaffold(
                    Path(temporary) / "workspace",
                    strategy_id='agent"\n[rights]\nmode="explicit_authorized',
                    author_id="author",
                    display_name="Agent",
                )


if __name__ == "__main__":
    unittest.main()
