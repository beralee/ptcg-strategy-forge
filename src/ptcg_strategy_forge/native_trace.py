"""Read the existing Godot native trace with its diagnostic hash domain."""
import copy
import hashlib
import re
import shutil
import tempfile
from pathlib import Path

from scripts.ai.ptcgdap.cabt_tree_hash import jcs_canonical_json_bytes, public_observation_hash
from scripts.ai.ptcgdap.competitive_policy_v2 import _frame_error
from scripts.ai.ptcgdap.source_lock import load_json_bytes_strict
from .replays import atomic_json, identity

PREFIX = b"PTCGDAP_REPLAY_DIAGNOSTIC\0ptcgdap_developer_decision_record_canonical_json_v1\0"


class NativeTraceStore:
    def __init__(self, workspace):
        self.root = Path(workspace) / "data/native-traces"

    def import_trace(self, directory):
        source = Path(directory)
        verified = read_native_trace(source)
        receipt = {"document_type": "forge_native_trace_receipt_v1", "native_match_id": source.name,
                   "trace_sha256": verified["trace_sha256"],
                   "manifest_sha256": hashlib.sha256((source / "developer_decision_trace_manifest.json").read_bytes()).hexdigest()}
        trace_id = identity(receipt)
        target = self.root / trace_id
        if not target.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=self.root, prefix=".import-") as temp:
                ready = Path(temp) / "ready"
                recording = ready / source.name
                recording.mkdir(parents=True)
                for name in ("developer_decision_trace_manifest.json", "developer_decisions.jsonl"):
                    shutil.copyfile(source / name, recording / name)
                # Recheck the copied bytes; concurrent source writes cannot mint a receipt.
                copied = read_native_trace(recording)
                if copied["trace_sha256"] != receipt["trace_sha256"] or hashlib.sha256((recording / "developer_decision_trace_manifest.json").read_bytes()).hexdigest() != receipt["manifest_sha256"]:
                    raise ValueError("native_trace_source_changed")
                atomic_json(ready / "receipt.json", receipt)
                ready.rename(target)
        self.load(trace_id)
        return {"document_type": "forge_native_trace_import_v1", "status": "completed", "trace_id": trace_id}

    def load(self, trace_id):
        if not re.fullmatch(r"[a-f0-9]{64}", trace_id):
            raise ValueError("native_trace_identity_invalid")
        root = self.root / trace_id
        receipt = load_json_bytes_strict((root / "receipt.json").read_bytes())
        if identity(receipt) != trace_id:
            raise ValueError("native_trace_receipt_invalid")
        name = receipt["native_match_id"]
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in {".", ".."}:
            raise ValueError("native_trace_receipt_invalid")
        recording = root / name
        result = read_native_trace(recording)
        if result["trace_sha256"] != receipt["trace_sha256"] or hashlib.sha256((recording / "developer_decision_trace_manifest.json").read_bytes()).hexdigest() != receipt["manifest_sha256"]:
            raise ValueError("native_trace_receipt_invalid")
        return result

    def inspect(self, trace_id):
        result = self.load(trace_id)
        reasons = {}
        for decision in result["decisions"]:
            reason = native_eligibility(decision, dirty=result["dirty"])
            reasons[reason] = reasons.get(reason, 0) + 1
        return {"document_type": "forge_native_trace_inspection_v1", "status": "verified", "trace_id": trace_id,
                "decision_count": len(result["decisions"]),
                "engine_commit_witness_count": sum(d["engine_commit_witnessed"] for d in result["decisions"]),
                "dirty": result["dirty"], "eligibility_counts": reasons, "source_authenticated": False,
                "production_ready": False}


def native_eligibility(decision, *, dirty=False):
    if dirty:
        return "dirty_game"
    if not decision["engine_commit_witnessed"]:
        return "engine_commit_unwitnessed"
    host = decision["host"]
    if host.get("status") != "accepted" or host.get("error_code") or host.get("fallback_used"):
        return "host_rejected_or_fallback"
    base = decision["policy"].get("base_result", {})
    if base.get("owner_layer") in {"mandatory", "terminal"}:
        return "model_bypassed"
    if base.get("fallback_used"):
        return "base_fallback"
    if not base.get("node_audit"):
        return "target_model_frontier_unavailable"
    return "target_projection_not_verified"


def _window(record):
    frame = copy.deepcopy(record["frame"])
    host = record["host"]
    fingerprints = []
    for option in frame["options"]:
        fingerprint = option.pop("option_fingerprint")
        expected = public_observation_hash({"profile_id": "ptcgdap-scoped-option-fingerprint-v1",
            "public_observation_hash": frame["source"]["public_observation_hash"], "window_id": frame["source"]["window_id"],
            "index": option["index"], "option": option})
        if fingerprint != expected:
            raise ValueError("native_trace_option_binding_invalid")
        fingerprints.append(fingerprint)
    error = _frame_error(frame)
    if error:
        raise ValueError("native_trace_" + error)
    observation = {"schema_version": frame["schema_version"], "sequence": frame["sequence"], "seat": frame["seat"],
                   "prompt_kind": frame["prompt_kind"], "public_state": frame["public_state"]}
    if public_observation_hash(observation) != frame["source"]["public_observation_hash"]:
        raise ValueError("native_trace_observation_binding_invalid")
    window = {"public_observation_hash": frame["source"]["public_observation_hash"],
              "select_semantics": frame["select_semantics"], "options": frame["options"]}
    if public_observation_hash(window) != frame["source"]["window_id"]:
        raise ValueError("native_trace_window_binding_invalid")
    indexes = host["accepted_indexes"]
    if type(indexes) is not list or len(set(indexes)) != len(indexes) or any(type(i) is not int or not 0 <= i < len(fingerprints) for i in indexes):
        raise ValueError("native_trace_accepted_indexes_invalid")
    if [fingerprints[i] for i in indexes] != host["accepted_option_fingerprints"]:
        raise ValueError("native_trace_acceptance_binding_invalid")
    return {"decision_id": record["decision_id"], "frame": frame, "host": copy.deepcopy(host), "policy": copy.deepcopy(record["policy"])}


def read_native_trace(directory, *, max_bytes=256*1024**2):
    try:
        return _read_native_trace(Path(directory), max_bytes)
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError("native_trace_schema_invalid") from error


def _read_native_trace(root, max_bytes):
    manifest_path = root / "developer_decision_trace_manifest.json"
    trace_path = root / "developer_decisions.jsonl"
    if manifest_path.is_symlink() or trace_path.is_symlink() or trace_path.stat().st_size > max_bytes or manifest_path.stat().st_size > 1024**2:
        raise ValueError("native_trace_input_budget_invalid")
    manifest = load_json_bytes_strict(manifest_path.read_bytes())
    if manifest["document_type"] != "developer_decision_trace_manifest_v1" or manifest["schema_version"] != 1 or manifest["native_match_id"] != root.name:
        raise ValueError("native_trace_manifest_invalid")
    if manifest["complete"] is not True or manifest["dropped_record_count"] != 0:
        raise ValueError("native_trace_incomplete")
    if manifest["private_replay_used"] is not False or manifest["visibility"] != "acting_policy_public_view_allow_list_v1":
        raise ValueError("native_trace_visibility_invalid")
    previous = None
    records = steps = 0
    decisions = {}
    witnessed = set()
    dirty = False
    with trace_path.open("rb") as stream:
        for line in stream:
            if not line.strip():
                continue
            envelope = load_json_bytes_strict(line)
            stored = envelope.pop("record_sha256")
            if hashlib.sha256(PREFIX + jcs_canonical_json_bytes(envelope)).hexdigest().upper() != stored:
                raise ValueError("native_trace_hash_mismatch")
            if (envelope["document_type"] != "developer_decision_trace_record_v1" or envelope["schema_version"] != 1
                    or envelope["record_index"] != records or envelope["previous_record_sha256"] != previous
                    or envelope["native_match_id"] != root.name):
                raise ValueError("native_trace_chain_invalid")
            previous = stored
            records += 1
            payload = envelope["payload"]
            if payload["document_type"] == "decision_window_record_v1":
                decision = _window(payload)
                if decision["decision_id"] in decisions:
                    raise ValueError("native_trace_duplicate_decision")
                decisions[decision["decision_id"]] = decision
            elif payload["document_type"] == "owner_step_witness_v1":
                steps += 1
                if payload["engine_rejection_delta"]:
                    dirty = True
                ids = payload["decision_ids"]
                if any(i not in decisions or i in witnessed for i in ids):
                    raise ValueError("native_trace_witness_binding_invalid")
                # Multiple calls per step are not assigned fabricated one-to-one commits.
                if len(ids) == 1 and payload["engine_commit_delta"] == 1 and payload["engine_rejection_delta"] == 0:
                    witnessed.update(ids)
            else:
                raise ValueError("native_trace_record_type_invalid")
    if (records != manifest["record_count"] or len(decisions) != manifest["decision_count"]
            or steps != manifest["owner_step_count"] or previous != manifest["chain_root_sha256"]):
        raise ValueError("native_trace_manifest_count_mismatch")
    for decision_id, decision in decisions.items():
        decision["engine_commit_witnessed"] = decision_id in witnessed
    return {"document_type": "forge_verified_native_trace_v1", "status": "verified", "manifest": manifest,
            "trace_sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest(), "decisions": list(decisions.values()),
            "dirty": dirty, "source_authenticated": False, "bc_eligible": False}
