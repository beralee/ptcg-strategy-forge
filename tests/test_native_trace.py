import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from scripts.ai.ptcgdap.cabt_tree_hash import jcs_canonical_json_bytes


class NativeTraceTests(unittest.TestCase):
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
