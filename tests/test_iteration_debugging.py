import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class DebuggingTests(unittest.TestCase):
    def test_competitive_predicates_observe_without_changing_base_authority(self):
        from ptcg_strategy_forge.diagnostics import capture_predicates
        from tests.test_competitive_forge_v2 import _adapter, _frame, GRIMMSNARL, MORGREM, DARK_ENERGY
        from scripts.ai.ptcgdap.competitive_policy_v2 import CompetitivePolicyV2Compiler, CompetitivePolicyV2Runtime
        document = _adapter()
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(document, allowed_card_uids={GRIMMSNARL, MORGREM, DARK_ENERGY})
        plain = CompetitivePolicyV2Runtime.decide(compiled.policy, _frame())
        with capture_predicates(document) as rows:
            monitored = CompetitivePolicyV2Runtime.decide(compiled.policy, _frame())
        self.assertEqual(plain.selected_indexes, monitored.selected_indexes)
        self.assertTrue(any(r["rule_id"] == "select-dark-energy" and r["matched"] for r in rows))
        with capture_predicates(document):
            protected = CompetitivePolicyV2Runtime.decide(compiled.policy, _frame(), mandatory_indexes=[4])
        self.assertEqual([4], protected.selected_indexes)

    def test_quick_changed_cache_is_bound_to_case_and_policy(self):
        from ptcg_strategy_forge.debugging import DebuggingService
        from unittest.mock import patch
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            shutil.copytree(ROOT / "demo/marnie-forge", root)
            service = DebuggingService(root)
            observed = {"status": "passed", "cases": [{"id": "positive", "accepted": True}], "case_count": 1, "passed_count": 1}
            with patch("ptcg_strategy_forge.application.run_suite", return_value=observed) as owner:
                self.assertEqual(1, service.test(cases=["positive"], changed=True)["executed_count"])
                self.assertEqual(0, service.test(cases=["positive"], changed=True)["executed_count"])
                path = root / "scenarios/01-positive.json"
                path.write_text(path.read_text(encoding="utf-8")+"\n", encoding="utf-8")
                self.assertEqual(1, service.test(cases=["positive"], changed=True)["executed_count"])
                self.assertEqual(2, owner.call_count)
            with self.assertRaisesRegex(ValueError, "scenario_case_unknown"):
                service.test(cases=["missing"])

    def test_competitive_inspection_and_reorder_reject_hidden_fields(self):
        from ptcg_strategy_forge.application import inspect_ucis_scenario
        from ptcg_strategy_forge.debugging import reorder_scenario
        from tests.test_competitive_forge_v2 import _frame
        frame = _frame()
        scenario = {"document_type": "ptcg_strategy_forge_competitive_scenario_v2", "schema_version": 2,
                    "scenario_id": "competitive-example", "frame": frame, "expected_selected_indexes": [0],
                    "base_authority": {"mandatory_indexes": [], "terminal_indexes": [],
                                       "base_vetoed_indexes": [], "base_hard_tiers": None}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "scenario.json"
            path.write_text(json.dumps(scenario), encoding="utf-8")
            self.assertEqual("passed", inspect_ucis_scenario(path)["status"])
            result = reorder_scenario(scenario, list(reversed(range(len(frame["options"])))))
            self.assertEqual([len(frame["options"])-1], result["expected_selected_indexes"])
            scenario["frame"]["public_state"]["opponent"]["hand"] = []
            path.write_text(json.dumps(scenario), encoding="utf-8")
            with self.assertRaises(ValueError):
                inspect_ucis_scenario(path)

    def test_reorder_rebinds_frontier_not_card_location(self):
        from ptcg_strategy_forge.debugging import reorder_scenario
        source = json.loads((ROOT / "demo/marnie-forge/scenarios/01-positive.json").read_bytes())
        result = reorder_scenario(source, [1, 0])
        self.assertEqual([0], result["expected_selected_indexes"])
        self.assertEqual(1, result["raw_observation"]["select"]["option"][0]["index"])
        self.assertEqual("CSV10C_146", next(b["local_card_uid"] for b in result["local_uid_bindings"]["options"] if b["index"] == 0))
        self.assertEqual([1], source["expected_selected_indexes"])
        with self.assertRaisesRegex(ValueError, "scenario_permutation_invalid"):
            reorder_scenario(source, [0, 0])

    def test_single_fact_pair_preserves_teacher_and_requires_explicit_expectation(self):
        from ptcg_strategy_forge.debugging import counterfactual_scenario
        source = json.loads((ROOT / "demo/marnie-forge/scenarios/01-positive.json").read_bytes())
        changed = counterfactual_scenario(source, "/local_uid_bindings/acting_hand/0/local_card_uid", "CSV10C_216", [0])
        self.assertEqual([1], source["expected_selected_indexes"])
        self.assertEqual([0], changed["expected_selected_indexes"])
        self.assertEqual(source["raw_observation"], changed["raw_observation"])
        with self.assertRaisesRegex(ValueError, "scenario_counterfactual_field_invalid"):
            counterfactual_scenario(source, "/expected_selected_indexes/0", 0, [0])

    def test_generated_reorder_replays_through_host(self):
        from ptcg_strategy_forge.debugging import DebuggingService
        from tools.ptcgdap.author_strategy_developer import build_development_package
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "workspace"
            shutil.copytree(ROOT / "demo/marnie-forge", root)
            package = Path(temp) / "test.ptcgai"
            build_development_package(root / "package", package)
            service = DebuggingService(root)
            source = "scenarios/01-positive.json"
            generated = service.generate(source, permutation=[1, 0])
            report = service.explain(generated["path"], artifact=package)
            self.assertEqual("passed", report["simulation"]["status"])
            self.assertEqual([0], report["simulation"]["decision"]["selected_indexes"])
            self.assertFalse(report["claims"]["engine_execution"])
            failed = service.explain("scenarios/02-no-key-card.json", artifact=package)
            condition = next(c for row in failed["predicate_evaluations"] if row["rule_id"] == "forge.morgrem.evolve"
                             for c in row["conditions"] if c["field"] == "acting_hand_card_id")
            self.assertFalse(condition["matched"])
            self.assertEqual("CSV10C_147", condition["expected"])
