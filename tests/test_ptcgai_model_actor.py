from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

import onnx
from onnx import TensorProto, helper
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.ai.ptcgdap.author_strategy_package import (
    AuthorStrategyPackageError,
    AuthorStrategyPackageLoader,
    CABT_CONTRACT_SHA256,
    CARD_CATALOG_SHA256,
)

from scripts.ai.ptcgdap.ptcgai_model_actor import (
    MAX_OPTIONS,
    ModelAdjudicator,
    ModelActorError,
    PublicActorTensorizer,
)
from scripts.ai.ptcgdap.ptcgai_model_package import build_model_manifest, canonical_bytes
from tools.ptcgdap.build_author_strategy_package import (
    build_package_bytes,
    build_synthetic_fixture_payloads,
)
from src.ptcg_strategy_forge.ptcgai_ort import (
    OrtActor,
    OrtActorError,
    import_onnx_to_ort,
    inspect_onnx,
)


def _context(options: list[dict[str, int | None]]) -> dict[str, object]:
    return {
        "clocks": {
            "turn": 3,
            "turn_action_count": 2,
            "remaining_overage_time": 0,
            "acting_prizes_remaining": 4,
            "opponent_prizes_remaining": 5,
            "acting_deck_count": 31,
            "opponent_deck_count": 33,
            "acting_hand_count": 6,
            "opponent_hand_count": 5,
        },
        "public_state": {
            "turn_flags": {
                "first_player": 0,
                "result": 0,
                "supporter_played": False,
                "stadium_played": False,
                "energy_attached": True,
                "retreated": False,
            }
        },
        "select_semantics": {
            "select_type_raw": 1,
            "select_context_raw": 0,
            "min_count": 1,
            "max_count": 1,
            "remain_damage_counter": 0,
            "remain_energy_cost": 0,
            "options": [
                {"index": index, "fingerprint": "A" * 64, "raw": option}
                for index, option in enumerate(options)
            ],
        },
    }


class PublicActorTensorizerTests(unittest.TestCase):
    def test_option_rows_are_semantically_stable_across_reorder(self) -> None:
        card = {"type": 15, "cardId": 101, "serial": 7}
        attack = {"type": 13, "attackId": 22}
        first = PublicActorTensorizer.tensorize(_context([card, attack]))
        second = PublicActorTensorizer.tensorize(_context([attack, card]))

        self.assertEqual(first.option_i32, second.option_i32)
        self.assertEqual(first.option_presence_i32, second.option_presence_i32)
        self.assertEqual(first.semantic_keys, second.semantic_keys)
        self.assertEqual(first.row_to_current_index, (1, 0))
        self.assertEqual(second.row_to_current_index, (0, 1))
        self.assertEqual(len(first.option_mask_i32), MAX_OPTIONS)

    def test_hidden_field_and_unknown_shape_fail_closed(self) -> None:
        hidden = _context([{"type": 1}])
        hidden["private_state"] = {"opponent_hand": [1]}
        with self.assertRaisesRegex(ModelActorError, "model_hidden_field"):
            PublicActorTensorizer.tensorize(hidden)

        with self.assertRaisesRegex(ModelActorError, "model_unknown_option_shape"):
            PublicActorTensorizer.tensorize(_context([{"type": 1, "number": 1}]))

    def test_unknown_local_uid_fails_closed(self) -> None:
        context = _context([{"type": 15, "cardId": 101, "serial": 7}])
        with self.assertRaisesRegex(ModelActorError, "model_unknown_uid"):
            PublicActorTensorizer.tensorize(
                context,
                local_option_uids={0: "CSV8C_999"},
                allowed_card_uids={"CSV8C_094"},
            )


class ModelAdjudicatorTests(unittest.TestCase):
    def test_model_can_reorder_only_rule_tier_and_rebinds_current_index(self) -> None:
        context = _context(
            [
                {"type": 13, "attackId": 11},
                {"type": 13, "attackId": 22},
                {"type": 14},
            ]
        )
        tensors = PublicActorTensorizer.tensorize(context)
        score_by_attack = {11: 10, 22: 90}
        scores = [0] * MAX_OPTIONS
        for row, features in enumerate(tensors.option_i32[:3]):
            scores[row] = score_by_attack.get(features[10], -100)

        result = ModelAdjudicator.adjudicate(
            tensors=tensors,
            rule_selected_indexes=[0],
            mandatory_indexes=[],
            terminal_indexes=[],
            base_hard_tiers=[
                {"index": 0, "tier": [1]},
                {"index": 1, "tier": [1]},
                {"index": 2, "tier": [2]},
            ],
            base_vetoed_indexes=[],
            option_scores=scores,
            desired_count=[1],
        )
        self.assertTrue(result.model_used)
        self.assertEqual(result.selected_indexes, (1,))
        self.assertEqual(result.diagnostic_code, "")

    def test_mandatory_terminal_veto_and_higher_tier_cannot_be_overridden(self) -> None:
        tensors = PublicActorTensorizer.tensorize(
            _context([{"type": 1}, {"type": 2}, {"type": 14}])
        )
        scores = [0] * MAX_OPTIONS
        scores[tensors.current_index_to_row[1]] = 100
        scores[tensors.current_index_to_row[2]] = 200
        tiers = [
            {"index": 0, "tier": [1]},
            {"index": 1, "tier": [1]},
            {"index": 2, "tier": [2]},
        ]

        mandatory = ModelAdjudicator.adjudicate(
            tensors=tensors,
            rule_selected_indexes=[0],
            mandatory_indexes=[0],
            terminal_indexes=[],
            base_hard_tiers=tiers,
            base_vetoed_indexes=[],
            option_scores=scores,
            desired_count=[1],
        )
        self.assertFalse(mandatory.model_used)
        self.assertEqual(mandatory.selected_indexes, (0,))
        self.assertEqual(mandatory.diagnostic_code, "model_bypassed_mandatory")

        terminal = ModelAdjudicator.adjudicate(
            tensors=tensors,
            rule_selected_indexes=[0],
            mandatory_indexes=[],
            terminal_indexes=[0],
            base_hard_tiers=tiers,
            base_vetoed_indexes=[],
            option_scores=scores,
            desired_count=[1],
        )
        self.assertEqual(terminal.selected_indexes, (0,))
        self.assertEqual(terminal.diagnostic_code, "model_bypassed_terminal")

        constrained = ModelAdjudicator.adjudicate(
            tensors=tensors,
            rule_selected_indexes=[0],
            mandatory_indexes=[],
            terminal_indexes=[],
            base_hard_tiers=tiers,
            base_vetoed_indexes=[1],
            option_scores=scores,
            desired_count=[1],
        )
        self.assertTrue(constrained.model_used)
        self.assertEqual(constrained.selected_indexes, (0,))

    def test_invalid_output_falls_back_to_rules_in_same_window(self) -> None:
        tensors = PublicActorTensorizer.tensorize(_context([{"type": 1}, {"type": 2}]))
        result = ModelAdjudicator.adjudicate(
            tensors=tensors,
            rule_selected_indexes=[1],
            mandatory_indexes=[],
            terminal_indexes=[],
            base_hard_tiers=[{"index": 0, "tier": [1]}, {"index": 1, "tier": [1]}],
            base_vetoed_indexes=[],
            option_scores=[1],
            desired_count=[1],
        )
        self.assertFalse(result.model_used)
        self.assertEqual(result.selected_indexes, (1,))
        self.assertEqual(result.diagnostic_code, "model_output_shape_invalid")


class PtcgaiV2PackageTests(unittest.TestCase):
    def _archive(self, *, mode: str = "rules_with_model", corrupt_hash: bool = False) -> tuple[bytes, AuthorStrategyPackageLoader]:
        actor = b"ORT-FIXTURE-V1"
        payloads = build_synthetic_fixture_payloads()
        manifest = __import__("json").loads(payloads["strategy_package.json"])
        manifest["document_type"] = "strategy_package_v2"
        manifest["schema_version"] = 2
        manifest["compatibility"]["minimum_game_api"] = "ptcgdap-author-host-v2"
        manifest["compatibility"]["required_capabilities"] = (
            ["learned_policy_head_v1"] if mode == "rules_with_model" else []
        )
        manifest["policy"] = {
            **manifest["policy"],
            "policy_mode": mode,
            "model_manifest_path": "model/model_manifest.json" if mode == "rules_with_model" else None,
            "model_artifact_path": "model/actor.ort" if mode == "rules_with_model" else None,
        }
        payloads["strategy_package.json"] = canonical_bytes(manifest)
        if mode == "rules_with_model":
            model_manifest = build_model_manifest(
                actor,
                model_id="test.fixture.bc-rl",
                cabt_contract_sha256=CABT_CONTRACT_SHA256,
                card_catalog_sha256=CARD_CATALOG_SHA256,
            )
            if corrupt_hash:
                model_manifest["artifact"]["sha256"] = "0" * 64
            payloads["model/model_manifest.json"] = canonical_bytes(model_manifest)
            payloads["model/actor.ort"] = actor
        key = Ed25519PrivateKey.generate()
        private = key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        key_id = "test-v2-key"
        archive = build_package_bytes(payloads, private, key_id=key_id)
        loader = AuthorStrategyPackageLoader()
        loader._trust_store[key_id] = {
            "key_id": key_id,
            "algorithm": "ed25519",
            "public_key_base64": __import__("base64").b64encode(public).decode("ascii"),
            "scope": "test_fixture_only",
            "execution_trusted": False,
        }
        return archive, loader

    def test_rules_with_model_package_is_strict_and_keeps_fallback(self) -> None:
        archive, loader = self._archive()
        handle = loader.load_bytes(archive)
        metadata = handle.to_dict()
        self.assertEqual(metadata["package_document_type"], "strategy_package_v2")
        self.assertEqual(metadata["policy_mode"], "rules_with_model")
        self.assertEqual(len(metadata["model_artifact_sha256"]), 64)
        self.assertTrue(handle.payload_bytes("policy/policy_ir.json"))

    def test_rules_only_v2_has_no_model_artifact(self) -> None:
        archive, loader = self._archive(mode="rules_only")
        metadata = loader.load_bytes(archive).to_dict()
        self.assertEqual(metadata["policy_mode"], "rules_only")
        self.assertIsNone(metadata["model_artifact_sha256"])

    def test_corrupt_model_hash_fails_closed(self) -> None:
        archive, loader = self._archive(corrupt_hash=True)
        with self.assertRaisesRegex(AuthorStrategyPackageError, "model_artifact_hash_mismatch"):
            loader.load_bytes(archive)


class OrtActorTests(unittest.TestCase):
    def _model(self, path: Path, *, score_op: str = "ReduceSum") -> None:
        inputs = [
            helper.make_tensor_value_info("frame_i32", TensorProto.INT32, [1, 24]),
            helper.make_tensor_value_info("frame_presence_i32", TensorProto.INT32, [1, 24]),
            helper.make_tensor_value_info("option_i32", TensorProto.INT32, [1, 1024, 16]),
            helper.make_tensor_value_info("option_presence_i32", TensorProto.INT32, [1, 1024, 16]),
            helper.make_tensor_value_info("option_mask_i32", TensorProto.INT32, [1, 1024]),
        ]
        outputs = [
            helper.make_tensor_value_info("option_scores", TensorProto.INT32, [1, 1024]),
            helper.make_tensor_value_info("desired_count", TensorProto.INT32, [1]),
        ]
        axes = helper.make_tensor("axes", TensorProto.INT64, [1], [2])
        desired = helper.make_tensor("desired", TensorProto.INT32, [1], [1])
        nodes = (
            [helper.make_node("ReduceSum", ["option_i32", "axes"], ["option_scores"], keepdims=0)]
            if score_op == "ReduceSum"
            else [
                helper.make_node("ReduceSum", ["option_i32", "axes"], ["raw_scores"], keepdims=0),
                helper.make_node(score_op, ["raw_scores"], ["option_scores"]),
            ]
        )
        nodes.append(helper.make_node("Constant", [], ["desired_count"], value=desired))
        graph = helper.make_graph(nodes, "minimal-actor", inputs, outputs, initializer=[axes])
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 18)])
        model.ir_version = 10
        onnx.save(model, path)

    def test_onnx_import_and_ort_cpu_inference(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "actor.onnx"
            artifact = Path(root) / "actor.ort"
            self._model(source)
            self.assertEqual(inspect_onnx(source)["status"], "valid")
            report = import_onnx_to_ort(source, artifact)
            self.assertEqual(report["status"], "imported")
            tensors = PublicActorTensorizer.tensorize(
                _context([{"type": 13, "attackId": 11}, {"type": 14}])
            )
            scores, desired, _elapsed = OrtActor(artifact, timeout_ms=1000).run(tensors)
            self.assertEqual(len(scores), MAX_OPTIONS)
            self.assertEqual(desired, [1])

    def test_illegal_operator_is_rejected_before_import(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "actor.onnx"
            self._model(source, score_op="Identity")
            with self.assertRaisesRegex(OrtActorError, "model_operator_forbidden"):
                inspect_onnx(source)


if __name__ == "__main__":
    unittest.main()
