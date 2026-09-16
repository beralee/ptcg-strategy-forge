from pathlib import Path
import sys
import json
import tempfile
from contextlib import nullcontext
from unittest.mock import patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class BcTrainingTests(unittest.TestCase):
    def row(self):
        return {"option_i32": [[0]*16, [0, 0, 0, 1]+[0]*12],
                "option_presence_i32": [[1]*16, [1]*16], "model_eligible_mask": [1, 1],
                "selected_rows": [1], "desired_count": 1,
                "frame_i32": [0]*17+[1]+[0]*6, "semantic_keys": ["a", "b"]}

    def test_supervised_update_improves_held_out_semantic_choice(self):
        from ptcg_strategy_forge.training import fit_epoch, evaluate_rows
        row = self.row()
        before = evaluate_rows([row], [0]*16)
        weights = fit_epoch([row], [0]*16)
        after = evaluate_rows([row], weights)
        self.assertEqual(0, before["exact_set_accuracy"])
        self.assertEqual(1, after["exact_set_accuracy"])

    def test_veto_and_count_scope_are_not_silently_relabelled(self):
        from ptcg_strategy_forge.training import fit_epoch
        row = self.row()
        row["model_eligible_mask"] = [1, 0]
        with self.assertRaisesRegex(ValueError, "training_label_outside_domain"):
            fit_epoch([row], [0]*16)
        row = self.row()
        row["desired_count"] = 2
        row["selected_rows"] = [0, 1]
        with self.assertRaisesRegex(ValueError, "training_count_head_unsupported"):
            fit_epoch([row], [0]*16)

    def test_integer_score_matches_int32_runtime_wrap(self):
        from ptcg_strategy_forge.training import predict
        row = self.row()
        row["option_i32"][1][3] = 2**30
        weights = [0, 0, 0, 2]+[0]*12
        self.assertEqual([0], predict(row, weights))

    def test_run_exports_actor_and_rejects_tampered_checkpoint(self):
        from tests.test_bc_dataset import BcDatasetTests
        from ptcg_strategy_forge.datasets import DatasetStore
        from ptcg_strategy_forge.replays import identity
        from ptcg_strategy_forge.training import TrainingService
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = []
            found = set()
            for i in range(1000):
                group = f"series-{i}"
                bucket = int(identity([17, group])[:16], 16) % 100
                part = "train" if bucket < 80 else "validation" if bucket < 90 else "test"
                if part in found:
                    continue
                found.add(part)
                trace = BcDatasetTests().trace()
                trace.update(game_id=f"game-{i}", related_match_id=group)
                source = root / f"{i}.json"
                source.write_text(json.dumps(trace), encoding="utf-8")
                sources.append(source)
                if len(found) == 3:
                    break
            store = DatasetStore(root)
            dataset = store.build(sources, allow_fixture=True)["dataset_id"]
            split = store.split(dataset, seed=17)["split_id"]
            with patch("ptcg_strategy_forge.training.heavy_job", return_value=nullcontext()), patch("ptcg_strategy_forge.training.check_pressure"):
                service = TrainingService(root)
                result = service.bc(dataset, split, epochs=2, allow_fixture=True)
                self.assertEqual("passed", result["conformance"]["status"])
                self.assertTrue(Path(result["actor_ort"]).is_file())
                self.assertEqual("passed", result["export_equivalence"]["status"])
                from ptcg_strategy_forge.jobs import JobStore
                self.assertEqual("completed", JobStore().status(result["job_id"])["status"])
                from ptcg_strategy_forge.ptcgai_ort import write_linear_actor_onnx
                altered = root / "altered.onnx"
                write_linear_actor_onnx(altered, [16]*16)
                Path(result["actor_onnx"]).write_bytes(altered.read_bytes())
                with self.assertRaisesRegex(ValueError, "training_export_integrity_failed"):
                    service.bc(dataset, split, epochs=2, resume=True, allow_fixture=True)
                checkpoint = root / "runs" / result["run_id"] / "checkpoint.json"
                saved = json.loads(checkpoint.read_bytes())
                saved["weights"][0] += 1
                checkpoint.write_text(json.dumps(saved), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "training_checkpoint_incompatible"):
                    service.bc(dataset, split, epochs=2, resume=True, allow_fixture=True)


if __name__ == "__main__":
    unittest.main()
