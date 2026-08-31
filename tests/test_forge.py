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
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ptcg_strategy_forge.cli import _emit, check_workspace, doctor, run_suite  # noqa: E402
from ptcg_strategy_forge.provenance import load_manifest, verify_snapshot  # noqa: E402
from ptcg_strategy_forge import reviewed_decks  # noqa: E402
from ptcg_strategy_forge.ethans_typhlosion import build_adapter as build_ethans_adapter  # noqa: E402
from ptcg_strategy_forge.scenarios import (  # noqa: E402
    assert_public_report,
    generate_demo_scenarios,
    write_json,
)
from ptcg_strategy_forge.release_signing import (  # noqa: E402
    build_registered_release,
    generate_release_key,
    resign_registered_release,
)
from tools.ptcgdap.author_strategy_developer import (  # noqa: E402
    DeveloperToolError,
    validate_development_package,
)
from scripts.ai.ptcgdap.strategic_trace_v2 import RestrictedBaseGraphIRCompiler  # noqa: E402


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
    def test_release_key_and_registered_release_build_are_non_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            private_key = root / "author.ed25519"
            public_key = root / "author.public.json"
            key_report = generate_release_key(private_key, public_key)
            self.assertEqual("generated", key_report["status"])
            self.assertEqual(32, len(private_key.read_bytes()))
            public_document = json.loads(public_key.read_text(encoding="utf-8"))
            self.assertEqual(key_report["key_id"], public_document["key_id"])
            self.assertNotIn("private_key", public_document)
            with self.assertRaisesRegex(ValueError, "release_key_path_exists"):
                generate_release_key(private_key, root / "other.public.json")

            archive = root / "registered.ptcgai"
            build = build_registered_release(
                ROOT / "demo/marnie-forge/package", archive, private_key
            )
            self.assertEqual("developer_registered_release", build["signature_scope"])
            self.assertTrue(build["deterministic"])
            self.assertEqual(sha(archive), build["archive_sha256"])
            with zipfile.ZipFile(archive, "r") as package:
                signature = json.loads(package.read("signature.json"))
            self.assertEqual(key_report["key_id"], signature["key_id"])
            with self.assertRaisesRegex(ValueError, "release_output_exists"):
                build_registered_release(
                    ROOT / "demo/marnie-forge/package", archive, private_key
                )

            resigned = root / "resigned.ptcgai"
            resign = resign_registered_release(RELEASE, resigned, private_key)
            self.assertEqual("developer_registered_release", resign["signature_scope"])
            with zipfile.ZipFile(RELEASE, "r") as original, zipfile.ZipFile(resigned, "r") as final:
                payload_names = set(original.namelist()) - {"files.sha256.json", "signature.json"}
                self.assertEqual(
                    {name: original.read(name) for name in payload_names},
                    {name: final.read(name) for name in payload_names},
                )

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
        self.assertEqual(797, checks["supported-cards"]["total_cards"])
        self.assertTrue(checks["supported-cards"]["accepted"])
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
            self.assertEqual("strategy_package_v2", manifest["document_type"])
            self.assertEqual(2, manifest["schema_version"])
            self.assertEqual("rules_only", manifest["policy"]["policy_mode"])
            self.assertIsNone(manifest["policy"]["model_manifest_path"])
            self.assertIsNone(manifest["policy"]["model_artifact_path"])
            self.assertFalse((workspace / "package/policy/weights.bin").exists())
            blueprint = (workspace / "STRATEGY-BLUEPRINT.md").read_text(encoding="utf-8")
            self.assertIn("Integration Strategy", blueprint)
            self.assertIn("攻击窗口", blueprint)
            self.assertIn("信息动作", blueprint)
            self.assertIn("重观察", blueprint)
            self.assertIn("Base Graph", blueprint)
            sdk_guide = (workspace / "UCIS-SDK.md").read_text(encoding="utf-8")
            self.assertIn("workspace inspect", sdk_guide)
            self.assertIn("不会装进游戏", sdk_guide)
            self.assertEqual(
                (ROOT / "data/developer/supported-cards-v1.json").read_bytes(),
                (workspace / "SUPPORTED-CARDS.json").read_bytes(),
            )
            package = root / "integration.ptcgai"
            report = check_workspace(workspace, output=package)
            self.assertEqual("passed", report["status"])
            self.assertTrue(report["build"]["deterministic"])
            self.assertEqual("valid", report["validation"]["status"])
            self.assertEqual((10, 10), (report["scenarios"]["passed_count"], report["scenarios"]["case_count"]))
            self.assertFalse(report["model"]["required"])
            self.assertEqual("not_applicable", report["model"]["status"])
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

    def test_marnie_gift_box_r1_funds_one_munkidori_and_active_tm_evolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            workspace = root / "marnies-gift-box"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "forge.py"),
                    "new",
                    "--output",
                    str(workspace),
                    "--deck-id",
                    "646600",
                    "--package-id",
                    "dev.bodao-yongzhe.marnies-gift-box",
                    "--package-version",
                    "0.2.0",
                    "--author-id",
                    "bodao.yongzhe",
                    "--author-name",
                    "波导的勇者",
                    "--strategy-name",
                    "玛丽的礼盒",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            adapter = json.loads((workspace / "package/policy/adapter.json").read_text(encoding="utf-8"))
            rules = {row["rule_id"]: row for row in adapter["rules"]}
            self.assertGreaterEqual(adapter["adapter_version"], 3)
            self.assertIn(
                {
                    "fact": "option.target_attached_energy_count",
                    "op": "eq",
                    "value": 0,
                    "card_uid": None,
                },
                rules["attach.munkidori-first"]["when"],
            )
            for rule_id in (
                "attach.impidimp-line-debt",
                "attach.morgrem-line-debt",
                "attach.tm-evolution-active-snorunt",
                "attach.tm-evolution-active-impidimp",
            ):
                self.assertIn(rule_id, rules)
            self.assertIn(
                {"fact": "option.target_is_active", "op": "eq", "value": True, "card_uid": None},
                rules["main.tm-evolution"]["when"],
            )
            self.assertIn(
                {"fact": "option.target_attached_energy_count", "op": "gte", "value": 1, "card_uid": None},
                rules["main.tm-evolution"]["when"],
            )
            suite = json.loads((workspace / "scenario-suite.json").read_text(encoding="utf-8"))
            scenario_ids = {row["id"] for row in suite["cases"]}
            self.assertGreaterEqual(len(scenario_ids), 40)
            for scenario_id in (
                "manual-attach-munkidori-zero-energy",
                "manual-attach-munkidori-one-energy-flips-to-line",
                "manual-attach-munkidori-one-energy-semantic-reorder",
                "tm-evolution-active-energy-first",
                "tm-evolution-active-after-energy",
                "tm-evolution-active-after-energy-semantic-reorder",
            ):
                self.assertIn(scenario_id, scenario_ids)
            report = check_workspace(workspace, output=root / "marnies-gift-box-r1.ptcgai")
            self.assertEqual("passed", report["status"])
            self.assertEqual(len(scenario_ids), report["scenarios"]["passed_count"])

    def test_marnie_gift_box_r2_poffin_selects_two_semantic_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            workspace = root / "marnies-gift-box"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "forge.py"),
                    "new",
                    "--output",
                    str(workspace),
                    "--deck-id",
                    "646600",
                    "--package-id",
                    "dev.bodao-yongzhe.marnies-gift-box",
                    "--package-version",
                    "0.3.0",
                    "--author-id",
                    "bodao.yongzhe",
                    "--author-name",
                    "波导的勇者",
                    "--strategy-name",
                    "玛丽的礼盒",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            adapter = json.loads((workspace / "package/policy/adapter.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(adapter["adapter_version"], 4)
            count_rules = {row["rule_id"]: row for row in adapter["count_rules"]}
            self.assertEqual(2, count_rules["poffin.exact-two"]["fixed_count"])
            self.assertEqual(10, count_rules["poffin.exact-two"]["priority"])
            rules = {row["rule_id"] for row in adapter["rules"]}
            self.assertIn("search.poffin-impidimp-first", rules)
            self.assertIn("search.poffin-snorunt-after-line", rules)
            suite = json.loads((workspace / "scenario-suite.json").read_text(encoding="utf-8"))
            scenario_ids = {row["id"] for row in suite["cases"]}
            for scenario_id in (
                "poffin-exact-two-impidimp-line",
                "poffin-exact-two-impidimp-line-reordered",
                "poffin-second-line-flips-to-snorunt",
                "poffin-second-line-flips-to-snorunt-reordered",
            ):
                self.assertIn(scenario_id, scenario_ids)
            report = check_workspace(workspace, output=root / "marnies-gift-box-0.3.0.ptcgai")
            self.assertEqual("passed", report["status"])
            self.assertGreaterEqual(report["scenarios"]["case_count"], 44)
            self.assertEqual(report["scenarios"]["case_count"], report["scenarios"]["passed_count"])

    def test_marnie_gift_box_r3_searches_missing_evolution_stages_and_artazon_basic(self) -> None:
        adapter = reviewed_decks._marnie_gift_box_competitive_adapter(
            "dev.bodao-yongzhe.marnies-gift-box"
        )
        self.assertGreaterEqual(adapter["adapter_version"], 5)
        rules = {row["rule_id"] for row in adapter["rules"]}
        for rule_id in (
            "search.spikemuth-grimmsnarl-from-morgrem",
            "search.spikemuth-morgrem-from-impidimp",
            "search.ultra-ball-grimmsnarl-from-morgrem",
            "search.artazon-impidimp-first",
        ):
            self.assertIn(rule_id, rules)

    def test_marnie_gift_box_r4_binds_damage_tool_and_gust_target(self) -> None:
        adapter = reviewed_decks._marnie_gift_box_competitive_adapter(
            "dev.bodao-yongzhe.marnies-gift-box"
        )
        self.assertGreaterEqual(adapter["adapter_version"], 6)
        rules = {row["rule_id"] for row in adapter["rules"]}
        for rule_id in (
            "main.defiance-band-grimmsnarl",
            "main.reject-defiance-band-non-attacker",
            "gust.target-two-prize",
            "gust.avoid-single-prize-wall",
        ):
            self.assertIn(rule_id, rules)

    def test_marnie_gift_box_r5_controls_all_munkidori_windows(self) -> None:
        adapter = reviewed_decks._marnie_gift_box_competitive_adapter(
            "dev.bodao-yongzhe.marnies-gift-box"
        )
        self.assertGreaterEqual(adapter["adapter_version"], 7)
        rules = {row["rule_id"] for row in adapter["rules"]}
        for rule_id in (
            "munkidori.source-protect-two-prize",
            "munkidori.count-full-public-transfer",
            "munkidori.target-concentrated-public-ko",
            "munkidori.avoid-healed-bench-debt",
        ):
            self.assertIn(rule_id, rules)
        self.assertNotIn("munkidori.target-two-prize-conversion", rules)

    def test_marnie_gift_box_r6_rejects_zero_effective_damage(self) -> None:
        adapter = reviewed_decks._marnie_gift_box_competitive_adapter(
            "dev.bodao-yongzhe.marnies-gift-box"
        )
        self.assertGreaterEqual(adapter["adapter_version"], 8)
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        self.assertIn("attack.reject-zero-active-damage", rules)
        shadow_conditions = rules["attack.shadow-bullet"]["when"]
        self.assertTrue(
            any(
                row["fact"] == "damage.option.projected_damage"
                and row["op"] == "gt"
                and row["value"] == 0
                for row in shadow_conditions
            )
        )

    def test_marnie_gift_box_r7_executes_tm_evolution_granted_attack(self) -> None:
        adapter = reviewed_decks._marnie_gift_box_competitive_adapter(
            "dev.bodao-yongzhe.marnies-gift-box"
        )
        self.assertGreaterEqual(adapter["adapter_version"], 9)
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        self.assertIn("attack.tm-evolution-develop", rules)
        conditions = rules["attack.tm-evolution-develop"]["when"]
        self.assertTrue(any(row["fact"] == "option.kind" and row["value"] == "granted_attack" for row in conditions))
        self.assertTrue(any(row["fact"] == "option.source_uid" and row["value"] == "CSV5C_119" for row in conditions))

    def test_marnie_gift_box_r8_requires_a_benched_tm_evolution_target(self) -> None:
        adapter = reviewed_decks._marnie_gift_box_competitive_adapter(
            "dev.bodao-yongzhe.marnies-gift-box"
        )
        self.assertGreaterEqual(adapter["adapter_version"], 10)
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        expected = {
            "attack.tm-evolution-develop": "CSV10C_146",
            "attack.tm-evolution-develop-snorunt": "CSV9.5C_043",
        }
        for rule_id, card_uid in expected.items():
            self.assertIn(rule_id, rules)
            self.assertTrue(
                any(
                    row["fact"] == "self.bench.count_uid"
                    and row["op"] == "gt"
                    and row["value"] == 0
                    and row["card_uid"] == card_uid
                    for row in rules[rule_id]["when"]
                )
            )

    def test_marnie_gift_box_r9_prefers_grimmsnarl_when_rare_candy_is_public(self) -> None:
        adapter = reviewed_decks._marnie_gift_box_competitive_adapter(
            "dev.bodao-yongzhe.marnies-gift-box"
        )
        self.assertGreaterEqual(adapter["adapter_version"], 11)
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        for rule_id in (
            "search.ultra-ball-grimmsnarl-with-rare-candy",
            "search.spikemuth-grimmsnarl-with-rare-candy",
        ):
            self.assertIn(rule_id, rules)
            conditions = rules[rule_id]["when"]
            self.assertTrue(
                any(
                    row["fact"] == "self.hand.count_uid"
                    and row["op"] == "gt"
                    and row["value"] == 0
                    and row["card_uid"] == "CSVH1C_045"
                    for row in conditions
                )
            )

    def test_marnie_gift_box_r10_repays_active_grimmsnarl_after_energy_denial(self) -> None:
        adapter = reviewed_decks._marnie_gift_box_competitive_adapter(
            "dev.bodao-yongzhe.marnies-gift-box"
        )
        self.assertGreaterEqual(adapter["adapter_version"], 12)
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        rule = rules["attach.active-grimmsnarl-after-denial"]
        self.assertGreater(rule["base_score"], rules["attach.munkidori-first"]["base_score"])
        self.assertTrue(
            any(
                row["fact"] == "option.target_is_active"
                and row["op"] == "eq"
                and row["value"] is True
                for row in rule["when"]
            )
        )

    def test_marnie_gift_box_1_8_restores_source_arven_artazon_and_targets_them(self) -> None:
        source = json.loads(
            (ROOT / "data/bundled_user/decks/646600.json").read_text(encoding="utf-8")
        )
        counts = {
            f"{row['set_code']}_{row['card_index']}": int(row["count"])
            for row in source["cards"]
        }
        self.assertEqual(4, counts.get("CSV1C_123"), "source deck 646600 must contain four Arven")
        self.assertEqual(2, counts.get("CSV2C_127"), "source deck 646600 must contain two Artazon")
        self.assertNotIn("CSV10C_208", counts, "Ethan's Adventure has no target in this deck")
        self.assertNotIn("CSV1C_126", counts, "Mesagoza is not present in the source deck")

        adapter = reviewed_decks._marnie_gift_box_competitive_adapter(
            "dev.bodao-yongzhe.marnies-gift-box"
        )
        self.assertGreaterEqual(adapter["adapter_version"], 14)
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        rule_ids = set(rules)
        for rule_id in (
            "main.arven-development",
            "search.arven-poffin-core",
            "search.arven-tm-evolution-core",
            "main.artazon-development",
            "main.artazon-use",
            "search.artazon-impidimp-first",
            "search.artazon-snorunt-engine",
            "main.defer-boss-without-active-attacker",
            "main.defer-counter-catcher-without-active-attacker",
        ):
            self.assertIn(rule_id, rule_ids)
        for rule_id in ("main.boss-only-with-attacker", "main.counter-catcher-window"):
            self.assertTrue(any(
                row["fact"] == "goal.active_ready_count"
                and row["op"] == "gte"
                and row["value"] == 1
                for row in rules[rule_id]["when"]
            ))
            self.assertFalse(any(
                row["fact"] == "goal.ready_count"
                for row in rules[rule_id]["when"]
            ))
        self.assertNotIn("main.ethans-adventure", rule_ids)
        self.assertNotIn("main.mesagoza-before-supporter", rule_ids)
        self.assertNotIn("search.mesagoza-froslass-from-snorunt", rule_ids)

        with tempfile.TemporaryDirectory() as temp_name:
            workspace = Path(temp_name) / "marnie-1.8.0"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "forge.py"),
                    "new",
                    "--output",
                    str(workspace),
                    "--deck-id",
                    "646600",
                    "--package-id",
                    "dev.bodao-yongzhe.marnies-gift-box",
                    "--package-version",
                    "1.8.0",
                    "--author-id",
                    "bodao.yongzhe",
                    "--author-name",
                    "波导的勇者",
                    "--strategy-name",
                    "玛丽的礼盒",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            suite = json.loads((workspace / "scenario-suite.json").read_text(encoding="utf-8"))
            scenario_ids = {row["id"] for row in suite["cases"]}
            for scenario_id in (
                "arven-finds-poffin-core",
                "arven-finds-poffin-core-reordered",
                "arven-finds-tm-evolution-core",
                "arven-finds-tm-evolution-core-reordered",
                "arven-without-evolution-target-finds-rescue-board",
                "arven-without-evolution-target-finds-rescue-board-reordered",
                "artazon-use-before-supporter",
                "artazon-deploys-impidimp",
                "artazon-deploys-impidimp-reordered",
                "artazon-after-impidimp-deploys-snorunt",
                "artazon-after-core-deploys-munkidori",
                "artazon-yields-to-mandatory-option",
                "artazon-bench-full-deferred",
                "boss-with-ready-bench-only-is-deferred",
                "boss-with-ready-bench-only-is-deferred-reordered",
            ):
                self.assertIn(scenario_id, scenario_ids)

    def test_marnie_gift_box_1_9_repairs_replay_shaped_damage_and_assignment_windows(self) -> None:
        adapter = reviewed_decks._marnie_gift_box_competitive_adapter(
            "dev.bodao-yongzhe.marnies-gift-box"
        )
        self.assertEqual(15, adapter["adapter_version"])
        count_rules = {row["rule_id"]: row for row in adapter["count_rules"]}
        self.assertNotIn("punk-up.exact-five-with-munkidori-reserve", count_rules)
        self.assertTrue(any(
            row["fact"] == "prompt_kind" and row["value"] == "assignment_source"
            for row in count_rules["punk-up.exact-public-debt"]["when"]
        ))
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        self.assertTrue(any(
            row["fact"] == "damage.option.attack_windows_to_ko"
            and row["op"] == "eq"
            and row["value"] == 1
            for row in rules["attack.defiance-210-two-prize"]["when"]
        ))
        self.assertTrue(any(
            row["fact"] == "prompt_kind" and row["value"] == "attack_target"
            for row in rules["damage.shadow-bullet-bench-target"]["when"]
        ))
        self.assertIn("transaction.option.matches_target", {
            row["fact"] for row in rules["munkidori.target-concentrated-public-ko"]["when"]
        })
        transaction_ids = {
            row["transaction_id"] for row in adapter["semantic_transactions"]
        }
        self.assertIn("munkidori-concentrated-ko", transaction_ids)
        self.assertIn("gust-exact-two-prize-ko", transaction_ids)

    def test_new_workspace_supports_ethans_typhlosion_competitive_v2(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            workspace = root / "ethans-typhlosion"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "forge.py"),
                    "new",
                    "--output",
                    str(workspace),
                    "--deck-id",
                    "800018880",
                    "--package-id",
                    "dev.bodao-yongzhe.v18.ethans-typhlosion",
                    "--package-version",
                    "0.1.0",
                    "--author-id",
                    "bodao.yongzhe",
                    "--author-name",
                    "波导的勇者",
                    "--strategy-name",
                    "18.0 阿响的火暴兽",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)

            deck = json.loads((workspace / "package/deck/deck_manifest.json").read_text(encoding="utf-8"))
            adapter = json.loads((workspace / "package/policy/adapter.json").read_text(encoding="utf-8"))
            policy_ir = json.loads((workspace / "package/policy/policy_ir.json").read_text(encoding="utf-8"))
            blueprint = (workspace / "STRATEGY-BLUEPRINT.md").read_text(encoding="utf-8")
            suite = json.loads((workspace / "scenario-suite.json").read_text(encoding="utf-8"))

            self.assertEqual(800018880, deck["source_deck_id"])
            self.assertEqual((60, 26), (deck["card_count"], deck["unique_card_count"]))
            counts = {row["local_card_uid"]: row["count"] for row in deck["cards"]}
            self.assertEqual(4, counts["CSV10C_028"])
            self.assertEqual(4, counts["CSV10C_029"])
            self.assertEqual(3, counts["CSV10C_030"])
            self.assertEqual(4, counts["CSV10C_208"])
            self.assertEqual(5, counts["CSVE1C_FIR"])

            self.assertEqual(2, adapter["schema_version"])
            self.assertGreaterEqual(adapter["adapter_version"], 2)
            self.assertEqual(["competitive.score-rules"], policy_ir["nodes"][2]["config"]["macro_ids"])
            self.assertTrue(RestrictedBaseGraphIRCompiler.compile(policy_ir).accepted)
            goal_ids = {row["goal_id"] for row in adapter["goals"]}
            self.assertTrue({"typhlosion-prize-route", "backup-typhlosion", "pidgeot-engine"} <= goal_ids)
            count_rules = {row["rule_id"]: row for row in adapter["count_rules"]}
            self.assertEqual(2, count_rules["poffin.exact-two"]["fixed_count"])
            self.assertEqual(3, count_rules["ethans-adventure.up-to-three"]["fixed_count"])
            rule_ids = {row["rule_id"] for row in adapter["rules"]}
            for rule_id in (
                "main.arven-development",
                "search.arven-poffin-core",
                "search.arven-tm-evolution-core",
                "main.evolve-quilava",
                "main.evolve-typhlosion",
                "main.evolve-pidgeot",
                "quilava.journey-bond",
                "search.adventure.typhlosion-first",
                "search.adventure.fire-energy",
                "attack.partner-blast-ko",
                "main.stop-low-deck-information",
            ):
                self.assertIn(rule_id, rule_ids)
            self.assertIn("40/100/160/220/280", blueprint)
            self.assertIn("每次检索、抽牌、能力", blueprint)

            scenario_ids = {row["id"] for row in suite["cases"]}
            for scenario_id in (
                "poffin-cyndaquil-pidgey",
                "poffin-cyndaquil-pidgey-reordered",
                "tm-evolution-two-roots",
                "journey-bond-searches-adventure",
                "journey-bond-searches-adventure-reordered",
                "adventure-gets-typhlosion-and-fire",
                "partner-blast-public-ko",
                "partner-blast-public-ko-reordered",
                "partner-blast-non-ko-develops",
                "terminal-protects-base",
                "mandatory-protects-base",
                "hard-tier-protects-base",
                "veto-protects-base",
                "unknown-uid-fails-closed",
                "hidden-field-rejected",
            ):
                self.assertIn(scenario_id, scenario_ids)

            report = check_workspace(workspace, output=root / "ethans-typhlosion-r0.ptcgai")
            self.assertEqual("passed", report["status"])
            self.assertEqual(
                (len(scenario_ids), len(scenario_ids)),
                (report["scenarios"]["passed_count"], report["scenarios"]["case_count"]),
            )

    def test_ethans_typhlosion_r1_retreats_victini_into_ready_typhlosion(self) -> None:
        adapter = build_ethans_adapter(
            "dev.bodao-yongzhe.ethans-typhlosion", package_version="0.2.0"
        )
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        rule = rules["pivot.ready-typhlosion-from-victini"]
        self.assertEqual(65000, rule["base_score"])
        self.assertTrue(any(
            condition["fact"] == "option.target_uid"
            and condition["value"] == "CSV10C_030"
            for condition in rule["when"]
        ))
        self.assertTrue(any(
            condition["fact"] == "option.target_attack_ready"
            and condition["value"] is True
            for condition in rule["when"]
        ))

    def test_ethans_typhlosion_r2_funds_the_active_evolution_line_before_victini(self) -> None:
        adapter = build_ethans_adapter(
            "dev.bodao-yongzhe.ethans-typhlosion", package_version="0.3.0"
        )
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        self.assertEqual(43000, rules["attach.active-quilava-debt"]["base_score"])
        self.assertEqual(42000, rules["attach.active-cyndaquil-debt"]["base_score"])
        self.assertGreater(
            rules["attach.active-cyndaquil-debt"]["base_score"],
            rules["attach.victini-emergency"]["base_score"],
        )

    def test_ethans_typhlosion_r3_adventure_repairs_a_missing_cyndaquil_root(self) -> None:
        adapter = build_ethans_adapter(
            "dev.bodao-yongzhe.ethans-typhlosion", package_version="0.4.0"
        )
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        rule = rules["search.adventure.cyndaquil-missing-root"]
        self.assertEqual(55000, rule["base_score"])
        self.assertTrue(any(
            condition["fact"] == "self.board.count_uid"
            and condition["op"] == "lt"
            and condition["value"] == 1
            and condition["card_uid"] == "CSV10C_028"
            for condition in rule["when"]
        ))

    def test_ethans_typhlosion_r4_pidgeot_gets_the_fourth_adventure(self) -> None:
        adapter = build_ethans_adapter(
            "dev.bodao-yongzhe.ethans-typhlosion", package_version="0.5.0"
        )
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        rule = rules["search.pidgeot-fourth-adventure"]
        self.assertEqual(50000, rule["base_score"])
        self.assertTrue(any(
            condition["fact"] == "self.discard.count_uid"
            and condition["op"] == "eq"
            and condition["value"] == 3
            and condition["card_uid"] == "CSV10C_208"
            for condition in rule["when"]
        ))

    def test_ethans_typhlosion_r5_artazon_repairs_a_missing_cyndaquil_root(self) -> None:
        adapter = build_ethans_adapter(
            "dev.bodao-yongzhe.ethans-typhlosion", package_version="0.6.0"
        )
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        rule = rules["search.artazon-cyndaquil-missing-root"]
        self.assertEqual(52000, rule["base_score"])
        self.assertTrue(any(
            condition["fact"] == "window.source_uid"
            and condition["value"] == "CSV2C_127"
            for condition in rule["when"]
        ))

    def test_ethans_typhlosion_r6_funds_the_benched_evolution_line_before_victini(self) -> None:
        adapter = build_ethans_adapter(
            "dev.bodao-yongzhe.ethans-typhlosion", package_version="0.7.0"
        )
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        self.assertEqual(37000, rules["attach.benched-quilava-debt"]["base_score"])
        self.assertEqual(35000, rules["attach.benched-cyndaquil-debt"]["base_score"])

    def test_ethans_typhlosion_r7_pivots_into_a_ready_quilava(self) -> None:
        adapter = build_ethans_adapter(
            "dev.bodao-yongzhe.ethans-typhlosion", package_version="0.8.0"
        )
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        rule = rules["pivot.ready-quilava-from-nonline-active"]
        self.assertEqual(48000, rule["base_score"])
        self.assertTrue(any(
            condition["fact"] == "self.active.count_uid"
            and condition["value"] == 0
            and condition["card_uid"] == "CSV10C_029"
            for condition in rule["when"]
        ))

    def test_ethans_typhlosion_r8_ultra_ball_repairs_a_missing_quilava_bridge(self) -> None:
        adapter = build_ethans_adapter(
            "dev.bodao-yongzhe.ethans-typhlosion", package_version="0.9.0"
        )
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        self.assertNotIn("pivot.ready-quilava-from-nonline-active", rules)
        rule = rules["search.ultra-ball-quilava-missing-bridge"]
        self.assertEqual(56000, rule["base_score"])

    def test_ethans_typhlosion_r9_does_not_duplicate_a_quilava_already_in_hand(self) -> None:
        adapter = build_ethans_adapter(
            "dev.bodao-yongzhe.ethans-typhlosion", package_version="0.10.0"
        )
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        self.assertNotIn("search.ultra-ball-quilava-missing-bridge", rules)
        rule = rules["search.ultra-ball-quilava-missing-hand-bridge"]
        self.assertTrue(any(
            condition["fact"] == "self.hand.count_uid"
            and condition["op"] == "eq"
            and condition["value"] == 0
            and condition["card_uid"] == "CSV10C_029"
            for condition in rule["when"]
        ))

    def test_ethans_typhlosion_r10_rare_candy_prefers_typhlosion_over_pidgeot(self) -> None:
        adapter = build_ethans_adapter(
            "dev.bodao-yongzhe.ethans-typhlosion", package_version="0.11.0"
        )
        rules = {row["rule_id"]: row for row in adapter["rules"]}
        self.assertNotIn("search.ultra-ball-quilava-missing-hand-bridge", rules)
        rule = rules["evolve.rare-candy-typhlosion-first"]
        self.assertEqual(65000, rule["base_score"])
        self.assertTrue(any(
            condition["fact"] == "window.source_uid"
            and condition["value"] == "CSVH1C_045"
            for condition in rule["when"]
        ))

    def test_new_workspace_supports_ogerpon_champion_migration_v2(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            workspace = root / "ogerpon"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "forge.py"),
                    "new",
                    "--output",
                    str(workspace),
                    "--deck-id",
                    "800052301",
                    "--package-id",
                    "dev.beralee.v18.ogerpon-crustle-v523a",
                    "--package-version",
                    "0.1.0",
                    "--author-id",
                    "beralee.ogerpon",
                    "--author-name",
                    "Beralee",
                    "--strategy-name",
                    "18.0 厄诡椪岩殿居蟹 v5.23a 迁移策略",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
            deck = json.loads((workspace / "package/deck/deck_manifest.json").read_text(encoding="utf-8"))
            adapter = json.loads((workspace / "package/policy/adapter.json").read_text(encoding="utf-8"))
            policy_ir = json.loads((workspace / "package/policy/policy_ir.json").read_text(encoding="utf-8"))
            blueprint = (workspace / "STRATEGY-BLUEPRINT.md").read_text(encoding="utf-8")
            self.assertEqual(800052301, deck["source_deck_id"])
            self.assertEqual((60, 19), (deck["card_count"], deck["unique_card_count"]))
            self.assertEqual(2, adapter["schema_version"])
            self.assertEqual(67, len(adapter["rules"]))
            self.assertEqual(["competitive.score-rules"], policy_ir["nodes"][2]["config"]["macro_ids"])
            self.assertTrue(RestrictedBaseGraphIRCompiler.compile(policy_ir).accepted)
            self.assertIn("ogerpon.teal-dance", {row["rule_id"] for row in adapter["rules"]})
            self.assertIn("main.iono-self-brick-reset", {row["rule_id"] for row in adapter["rules"]})
            self.assertIn("main.iono-late-prize-lock", {row["rule_id"] for row in adapter["rules"]})
            self.assertIn("main.judge-early-prize-disruption", {row["rule_id"] for row in adapter["rules"]})
            self.assertIn("main.avoid-judge-late-game", {row["rule_id"] for row in adapter["rules"]})
            self.assertNotIn("main.iono-after-items", {row["rule_id"] for row in adapter["rules"]})
            self.assertNotIn("main.judge-after-items", {row["rule_id"] for row in adapter["rules"]})
            self.assertEqual(
                [],
                [
                    row["rule_id"]
                    for row in adapter["rules"]
                    if row["base_score"] > 0
                    and any(
                        condition["fact"] == "option.kind" and condition["value"] == "end_turn"
                        for condition in row["when"]
                    )
                ],
            )
            self.assertIn("crustle evolve-before-funding", blueprint)
            self.assertIn("Articuno", blueprint)
            self.assertIn("SCENARIO COMPLETE / GODOT ENGINE PENDING", blueprint)
            report = check_workspace(workspace, output=root / "ogerpon-r0.ptcgai")
            self.assertEqual("passed", report["status"])
            self.assertTrue(report["build"]["deterministic"])
            self.assertEqual((31, 31), (report["scenarios"]["passed_count"], report["scenarios"]["case_count"]))

            policy_ir["nodes"][2]["config"]["macro_ids"] = [
                f"invalid.overwide.{index}" for index in range(65)
            ]
            (workspace / "package/policy/policy_ir.json").write_text(
                json.dumps(policy_ir, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(DeveloperToolError) as captured:
                check_workspace(workspace)
            self.assertEqual("package_policy_unsupported", captured.exception.code)

    def test_ogerpon_supporter_curve_uses_phase_and_board_state(self) -> None:
        adapter = reviewed_decks._ogerpon_competitive_adapter(
            "dev.beralee.v18.ogerpon-crustle-v523a"
        )
        self.assertEqual(6, adapter["adapter_version"])
        rules = {row["rule_id"]: row for row in adapter["rules"]}

        self_brick = rules["main.iono-self-brick-reset"]
        self.assertGreater(self_brick["base_score"], 21000)
        self.assertTrue(any(
            row["fact"] == "goal.ready_count" and row["op"] == "eq" and row["value"] == 0
            for row in self_brick["when"]
        ))
        self.assertFalse(any(
            row["fact"] == "window.option_count_card_uid"
            for row in self_brick["when"]
        ))

        late_iono = rules["main.iono-late-prize-lock"]
        self.assertTrue(any(
            row["fact"] == "opponent.prizes_remaining" and row["op"] == "lte" and row["value"] == 3
            for row in late_iono["when"]
        ))
        self.assertTrue(any(
            row["fact"] == "self.prizes_remaining" and row["op"] == "gte" and row["value"] == 3
            for row in late_iono["when"]
        ))

        early_judge = rules["main.judge-early-prize-disruption"]
        self.assertTrue(any(
            row["fact"] == "turn_number" and row["op"] == "lte" and row["value"] == 6
            for row in early_judge["when"]
        ))
        self.assertTrue(any(
            row["fact"] == "opponent.prizes_remaining" and row["op"] == "gte" and row["value"] == 4
            for row in early_judge["when"]
        ))

        late_judge = rules["main.avoid-judge-late-game"]
        self.assertLess(late_judge["base_score"], 0)
        self.assertTrue(any(
            row["fact"] == "opponent.prizes_remaining" and row["op"] == "lte" and row["value"] == 3
            for row in late_judge["when"]
        ))

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

    def test_supported_cards_delivery_matches_qualified_ucis_catalog(self) -> None:
        delivered_path = ROOT / "data/developer/supported-cards-v1.json"
        delivered = json.loads(delivered_path.read_text(encoding="utf-8"))
        catalog_path = ROOT / "contracts/ptcgdap/ucis_card_catalog_v1.json"
        qualification_path = ROOT / "contracts/ptcgdap/ucis_catalog_qualification_v1.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        qualification = json.loads(qualification_path.read_text(encoding="utf-8"))

        self.assertEqual("ptcg_strategy_forge_supported_cards_v1", delivered["document_type"])
        self.assertEqual("godot_local_card_uid_v1", delivered["identity_domain"])
        self.assertEqual("passed", delivered["qualification_status"])
        self.assertEqual(qualification["scope"]["total_cards"], delivered["counts"]["total_cards"])
        self.assertEqual(
            hashlib.sha256(catalog_path.read_bytes()).hexdigest().upper(),
            delivered["sources"]["catalog_raw_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(qualification_path.read_bytes()).hexdigest().upper(),
            delivered["sources"]["qualification_raw_sha256"],
        )
        expected = [
            (row["card_uid"], row["status"], row["effect_id"])
            for row in sorted(catalog["cards"], key=lambda item: item["card_uid"])
        ]
        actual = [
            (row["card_uid"], row["interaction_status"], row["effect_id"])
            for row in delivered["cards"]
        ]
        self.assertEqual(expected, actual)
        self.assertEqual(len(actual), len({row[0] for row in actual}))
        self.assertTrue(all("display_name" not in row for row in delivered["cards"]))

    def test_first_upload_docs_preserve_account_identity_and_key_boundaries(self) -> None:
        quickstart = (ROOT / "docs" / "01-QUICKSTART.md").read_text(encoding="utf-8")
        publishing = (ROOT / "docs" / "05-PUBLISHING.md").read_text(encoding="utf-8")
        troubleshooting = (ROOT / "docs" / "07-TROUBLESHOOTING.md").read_text(encoding="utf-8")

        for text in (quickstart, publishing):
            self.assertIn("包括 `developer-` 前缀", text)
            self.assertIn("--package-id", text)
        self.assertIn("package_signature_untrusted", publishing)
        self.assertIn("同一个 `author_id`", publishing)
        self.assertIn("已接收", publishing)
        self.assertIn("等待资格验证", publishing)
        self.assertIn("仍可能是 `author_id`", troubleshooting)
        self.assertIn("私钥", publishing)
        self.assertIn("不能", publishing)

    def test_todo_statuses_are_machine_auditable(self) -> None:
        text = (ROOT / "TODO.md").read_text(encoding="utf-8")
        rows = re.findall(
            r"^\| (T\d{2}) \|.*\| (DONE|PARTIAL|PENDING|BLOCKED|OUT OF SCOPE) \|",
            text,
            flags=re.MULTILINE,
        )
        todo_ids = {int(row[0][1:]) for row in rows}
        self.assertGreaterEqual(max(todo_ids), 32)
        self.assertEqual(set(range(1, max(todo_ids) + 1)), todo_ids)
        statuses = dict(rows)
        self.assertEqual("PENDING", statuses["T19"])
        self.assertEqual("DONE", statuses["T20"])
        self.assertEqual("DONE", statuses["T21"])
        self.assertEqual("DONE", statuses["T22"])
        self.assertEqual("OUT OF SCOPE", statuses["T23"])
        self.assertEqual("DONE", statuses["T24"])
        self.assertEqual("DONE", statuses["T25"])
        self.assertEqual("DONE", statuses["T26"])
        self.assertEqual("DONE", statuses["T27"])
        self.assertEqual("DONE", statuses["T29"])
        self.assertEqual("DONE", statuses["T30"])
        self.assertEqual("DONE", statuses["T31"])
        self.assertEqual("DONE", statuses["T32"])
        self.assertEqual("PARTIAL", statuses["T36"])
        self.assertEqual("DONE", statuses["T37"])
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
