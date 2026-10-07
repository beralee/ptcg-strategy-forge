import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scripts.ai.ptcgdap.cabt_tree_hash import jcs_canonical_json_bytes


class NativeTraceTests(unittest.TestCase):
    def test_recording_and_policy_share_exact_public_appearance_contract(self):
        import copy
        from tests.test_competitive_forge_v2 import _frame
        from ptcg_strategy_forge.native_trace import _trace_frame_error
        from scripts.ai.ptcgdap.competitive_policy_v2 import _frame_error
        frame = _frame()
        slot = frame['public_state']['self']['active'][0]
        slot['appeared_this_turn'] = True
        original = copy.deepcopy(frame)
        self.assertIsNone(_trace_frame_error(frame))
        self.assertEqual(original, frame)
        self.assertIsNone(_frame_error(frame))
        for key, value in [('appeared_this_turn', 1), ('unknown_slot_field', True), ('opponent_hand', [])]:
            bad = copy.deepcopy(frame)
            bad['public_state']['self']['active'][0][key] = value
            self.assertIsNotNone(_trace_frame_error(bad))

    def test_counter_change_cannot_reuse_old_option_fingerprint(self):
        import copy
        from tools.ptcgdap.public_counter_contract import counter_cases
        from tools.ptcgdap.build_competitive_policy_v2_contract import _sample_policy, _option, _frame
        from ptcg_strategy_forge.native_trace import _window, _trace_frame_error
        from scripts.ai.ptcgdap.cabt_tree_hash import public_observation_hash
        frame = counter_cases(_sample_policy, _option, _frame)[0]['frame']
        self.assertIsNone(_trace_frame_error(frame))
        for option in frame['options']:
            option['option_fingerprint'] = public_observation_hash({
                'profile_id': 'ptcgdap-scoped-option-fingerprint-v1',
                'public_observation_hash': frame['source']['public_observation_hash'],
                'window_id': frame['source']['window_id'], 'index': option['index'],
                'option': copy.deepcopy(option)})
        for key in ('remaining_damage_counters', 'target_pending_damage_counters'):
            changed = copy.deepcopy(frame)
            changed['options'][0][key] += 1
            with self.assertRaisesRegex(ValueError, 'native_trace_option_binding_invalid'):
                _window({'frame': changed, 'host': {}})

    def test_import_is_immutable_and_reverified(self):
        from ptcg_strategy_forge.native_trace import NativeTraceStore
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "recording"
            source.mkdir()
            self.write_trace(source)
            store = NativeTraceStore(root / "workspace")
            result = store.import_trace(source)
            self.assertEqual(result, store.import_trace(source))
            self.assertEqual(0, store.inspect(result["trace_id"])["decision_count"])
            receipt = store.root / result["trace_id"] / "receipt.json"
            data = json.loads(receipt.read_bytes())
            data["trace_sha256"] = "0"*64
            receipt.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "native_trace_receipt_invalid"):
                store.inspect(result["trace_id"])

    def write_trace(self, root):
        payload = {"document_type": "owner_step_witness_v1", "decision_ids": [], "engine_commit_delta": 0, "engine_rejection_delta": 0}
        envelope = {"document_type": "developer_decision_trace_record_v1", "schema_version": 1,
                    "native_match_id": root.name, "record_index": 0, "previous_record_sha256": None, "payload": payload}
        sha = hashlib.sha256(b"PTCGDAP_REPLAY_DIAGNOSTIC\0ptcgdap_developer_decision_record_canonical_json_v1\0" + jcs_canonical_json_bytes(envelope)).hexdigest().upper()
        (root / "developer_decisions.jsonl").write_text(json.dumps({**envelope, "record_sha256": sha})+"\n", encoding="utf-8")
        manifest = {"document_type": "developer_decision_trace_manifest_v1", "schema_version": 1, "native_match_id": root.name,
                    "complete": True, "record_count": 1, "decision_count": 0, "owner_step_count": 1, "chain_root_sha256": sha,
                    "dropped_record_count": 0, "private_replay_used": False, "visibility": "acting_policy_public_view_allow_list_v1"}
        (root / "developer_decision_trace_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_complete_hash_chain_and_incomplete_rejection(self):
        from ptcg_strategy_forge.native_trace import read_native_trace
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_trace(root)
            self.assertEqual("verified", read_native_trace(root)["status"])
            path = root / "developer_decision_trace_manifest.json"
            manifest = json.loads(path.read_bytes())
            manifest["complete"] = False
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "native_trace_incomplete"):
                read_native_trace(root)

    def test_mutated_payload_cannot_reuse_old_chain(self):
        from ptcg_strategy_forge.native_trace import read_native_trace
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_trace(root)
            path = root / "developer_decisions.jsonl"
            envelope = json.loads(path.read_bytes())
            envelope["payload"]["engine_commit_delta"] = 1
            path.write_text(json.dumps(envelope), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "native_trace_hash_mismatch"):
                read_native_trace(root)
