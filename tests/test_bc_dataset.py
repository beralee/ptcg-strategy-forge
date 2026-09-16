import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class BcDatasetTests(unittest.TestCase):
    def test_deterministic_shards_stream_and_audit(self):
        from ptcg_strategy_forge.datasets import DatasetStore
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = []
            for i in range(3):
                trace = self.trace()
                trace["game_id"] = f"game-{i}"
                path = root / f"{i}.json"
                path.write_text(json.dumps(trace), encoding="utf-8")
                sources.append(path)
            store = DatasetStore(root)
            first = store.build(sources, allow_fixture=True, shard_rows=2)
            second = store.build(list(reversed(sources)), allow_fixture=True, shard_rows=2)
            self.assertEqual(first["dataset_id"], second["dataset_id"])
            self.assertEqual([2, 1], [s["row_count"] for s in first["shards"]])
            self.assertEqual(3, len(list(store.rows(first["dataset_id"]))))
            self.assertEqual(1, store.stats(first["dataset_id"])["duplicate_tensor_groups"])
            shard = store.path(first["dataset_id"]) / first["shards"][1]["path"]
            shard.write_bytes(b"corrupt")
            self.assertEqual("failed", store.audit(first["dataset_id"])["status"])

    def trace(self):
        scenario = json.loads((ROOT / "demo/marnie-forge/scenarios/01-positive.json").read_text(encoding="utf-8"))
        return {"document_type": "forge_decision_trace_v1", "schema_version": 1,
                "evidence_kind": "test_fixture", "game_id": "game-a", "related_match_id": "series-a",
                "engine_version": "fixture", "contract_sha256": "0" * 64,
                "decisions": [{"window_id": "w1", "seat": 0, "predecision": scenario,
                               "accepted": True, "selected_indexes": [1], "rule_selected_indexes": [0],
                               "mandatory_indexes": [], "terminal_indexes": [],
                               "base_hard_tiers": [{"index": 0, "tier": [1]}, {"index": 1, "tier": [1]}],
                               "base_vetoed_indexes": []}]}

    def test_semantic_reorder_preserves_canonical_bc_label(self):
        from ptcg_strategy_forge.datasets import decision_rows
        trace = self.trace()
        first = decision_rows(trace, allow_fixture=True)
        second_trace = copy.deepcopy(trace)
        decision = second_trace["decisions"][0]
        decision["predecision"]["raw_observation"]["select"]["option"].reverse()
        for binding in decision["predecision"]["local_uid_bindings"]["options"]:
            binding["index"] = 1 - binding["index"]
        decision["selected_indexes"] = [0]
        decision["rule_selected_indexes"] = [1]
        second = decision_rows(second_trace, allow_fixture=True)
        self.assertEqual(first[0]["selected_rows"], second[0]["selected_rows"])
        self.assertEqual(first[0]["option_i32"], second[0]["option_i32"])

    def test_invalid_or_ineligible_labels_fail_closed(self):
        from ptcg_strategy_forge.datasets import decision_rows
        for updates in ({"accepted": False}, {"selected_indexes": [2]},
                        {"selected_indexes": [True]}, {"selected_indexes": [1, 1]},
                        {"base_vetoed_indexes": [1]}, {"mandatory_indexes": [0]}):
            with self.subTest(updates=updates):
                trace = self.trace()
                trace["decisions"][0].update(updates)
                with self.assertRaises(ValueError):
                    decision_rows(trace, allow_fixture=True)

    def test_hidden_field_and_fixture_authority_are_rejected(self):
        from ptcg_strategy_forge.datasets import decision_rows
        trace = self.trace()
        with self.assertRaisesRegex(ValueError, "dataset_fixture_requires_opt_in"):
            decision_rows(trace)
        trace["decisions"][0]["predecision"]["raw_observation"]["private_rng"] = 1
        with self.assertRaises(ValueError):
            decision_rows(trace, allow_fixture=True)

    def test_multiselect_count_and_mask_have_distinct_semantics(self):
        from ptcg_strategy_forge.datasets import decision_rows
        trace = self.trace()
        decision = trace["decisions"][0]
        decision["predecision"]["raw_observation"]["select"]["maxCount"] = 2
        decision["selected_indexes"] = [0, 1]
        rows = decision_rows(trace, allow_fixture=True)
        self.assertEqual(2, rows[0]["desired_count"])
        self.assertEqual(2, sum(rows[0]["model_eligible_mask"]))

    def test_dataset_identity_audit_and_group_split(self):
        from ptcg_strategy_forge.datasets import DatasetStore
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace = self.trace()
            source = root / "trace.json"
            source.write_text(json.dumps(trace), encoding="utf-8")
            store = DatasetStore(root)
            result = store.build([source], allow_fixture=True)
            repeated = store.build([source], allow_fixture=True)
            self.assertEqual(result["dataset_id"], repeated["dataset_id"])
            split = store.split(result["dataset_id"], seed=17)
            self.assertEqual(1, len(split["groups"]))
            self.assertEqual("passed", store.audit(result["dataset_id"])["status"])
            shard = root / "data/datasets" / result["dataset_id"] / "rows.jsonl"
            shard.write_text("tampered", encoding="utf-8")
            self.assertEqual("failed", store.audit(result["dataset_id"])["status"])


if __name__ == "__main__":
    unittest.main()
