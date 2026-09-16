"""Audited local BC datasets. Playback data never implies decision evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import sqlite3

from .replays import atomic_json, canonical, identity
from .sdk import _ROOT, _scenario_actor_context
from scripts.ai.ptcgdap.cabt_envelope import parse_raw_cabt_envelope
from scripts.ai.ptcgdap.public_observation_firewall import PublicObservationFirewall
from scripts.ai.ptcgdap.ptcgai_model_actor import PublicActorTensorizer


def decision_rows(trace, *, allow_fixture=False):
    try:
        return _decision_rows(trace, allow_fixture=allow_fixture)
    except (KeyError, TypeError, IndexError, AttributeError, RecursionError) as error:
        raise ValueError("dataset_trace_schema_invalid") from error


def _decision_rows(trace, *, allow_fixture=False):
    if not isinstance(trace, dict) or trace.get("document_type") != "forge_decision_trace_v1" or trace.get("schema_version") != 1:
        raise ValueError("dataset_decision_trace_unavailable")
    # Until a reviewed engine trace adapter exists, self-declared engine authority
    # is not accepted. This schema is an explicit developer fixture/import lane.
    if trace.get("evidence_kind") != "test_fixture":
        raise ValueError("dataset_source_adapter_unavailable")
    if not allow_fixture:
        raise ValueError("dataset_fixture_requires_opt_in")
    required = {"document_type", "schema_version", "evidence_kind", "game_id", "related_match_id",
                "engine_version", "contract_sha256", "decisions"}
    if set(trace) != required or not isinstance(trace["decisions"], list):
        raise ValueError("dataset_trace_schema_invalid")
    if not isinstance(trace["contract_sha256"], str) or not re.fullmatch(r"[a-fA-F0-9]{64}", trace["contract_sha256"]):
        raise ValueError("dataset_contract_identity_invalid")
    for key in ("game_id", "related_match_id", "engine_version"):
        if not isinstance(trace[key], str) or not re.fullmatch(r"[A-Za-z0-9_.+-]{1,128}", trace[key]):
            raise ValueError("dataset_identity_invalid")
    rows = []
    windows = set()
    for decision in trace["decisions"]:
        expected = {"window_id", "seat", "predecision", "accepted", "selected_indexes", "rule_selected_indexes",
                    "mandatory_indexes", "terminal_indexes", "base_hard_tiers", "base_vetoed_indexes"}
        if not isinstance(decision, dict) or set(decision) != expected:
            raise ValueError("dataset_decision_schema_invalid")
        window = decision["window_id"]
        if not isinstance(window, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", window) or window in windows:
            raise ValueError("dataset_window_identity_invalid")
        windows.add(window)
        if decision["accepted"] is not True:
            raise ValueError("dataset_choice_not_accepted")
        if decision["mandatory_indexes"] or decision["terminal_indexes"]:
            raise ValueError("dataset_model_bypassed")
        scenario = decision["predecision"]
        raw = scenario["raw_observation"]
        if set(raw) != {"select", "logs", "current", "search_begin_input", "step", "remainingOverageTime"}:
            raise ValueError("dataset_observation_fields_invalid")
        if type(decision["seat"]) is not int or decision["seat"] not in (0, 1) or raw["current"]["yourIndex"] != decision["seat"]:
            raise ValueError("dataset_seat_mismatch")
        parsed = parse_raw_cabt_envelope(raw, contract_root=_ROOT / "contracts/ptcgdap")
        if not parsed.ok or parsed.envelope.unknown_fields:
            raise ValueError("dataset_observation_fields_invalid")
        if not PublicObservationFirewall.load_default().project(parsed).accepted:
            raise ValueError("dataset_hidden_field")
        context, local_uids = _scenario_actor_context(scenario)
        catalog = json.loads((_ROOT / "data/developer/supported-cards-v1.json").read_text(encoding="utf-8"))
        allowed = {row["card_uid"] for row in catalog["cards"] if row["usable"]}
        tensors = PublicActorTensorizer.tensorize(context, local_option_uids=local_uids, allowed_card_uids=allowed)
        indexes = set(tensors.current_index_to_row)
        selected = decision["selected_indexes"]
        rule = decision["rule_selected_indexes"]
        for values in (selected, rule, decision["base_vetoed_indexes"]):
            if type(values) is not list or any(type(i) is not int or i not in indexes for i in values) or len(values) != len(set(values)):
                raise ValueError("dataset_label_invalid")
        if not rule or not tensors.min_count <= len(selected) <= tensors.max_count:
            raise ValueError("dataset_label_count_invalid")
        tiers = decision["base_hard_tiers"]
        if not isinstance(tiers, list) or len(tiers) != len(indexes):
            raise ValueError("dataset_base_authority_invalid")
        tier_map = {}
        for tier in tiers:
            if (set(tier) != {"index", "tier"} or type(tier["index"]) is not int or tier["index"] in tier_map
                    or not isinstance(tier["tier"], list) or not tier["tier"] or any(type(v) is not int for v in tier["tier"])):
                raise ValueError("dataset_base_authority_invalid")
            tier_map[tier["index"]] = tier["tier"]
        if set(tier_map) != indexes or any(tier_map[i] != tier_map[rule[0]] for i in rule):
            raise ValueError("dataset_base_authority_invalid")
        eligible = {i for i in indexes if i not in decision["base_vetoed_indexes"] and tier_map[i] == tier_map[rule[0]]}
        if not set(selected) <= eligible:
            raise ValueError("dataset_label_outside_model_domain")
        count = len(indexes)
        row = {
            "game_id": trace["game_id"], "related_match_id": trace["related_match_id"], "window_id": window,
            "seat": decision["seat"], "evidence_kind": trace["evidence_kind"], "profile_id": tensors.profile_id,
            "source_engine_version": trace["engine_version"], "source_contract_sha256": trace["contract_sha256"],
            "frame_i32": list(tensors.frame_i32), "frame_presence_i32": list(tensors.frame_presence_i32),
            "option_i32": [list(v) for v in tensors.option_i32[:count]],
            "option_presence_i32": [list(v) for v in tensors.option_presence_i32[:count]],
            "option_mask_i32": list(tensors.option_mask_i32[:count]),
            "model_eligible_mask": [int(i in eligible) for i in tensors.row_to_current_index],
            "selected_rows": sorted(tensors.current_index_to_row[i] for i in selected),
            "desired_count": len(selected), "semantic_keys": list(tensors.semantic_keys),
        }
        row["row_id"] = identity(row)
        rows.append(row)
    return rows


class DatasetStore:
    def __init__(self, workspace):
        self.root = Path(workspace) / "data"

    def path(self, dataset_id):
        if not re.fullmatch(r"[a-f0-9]{64}", dataset_id):
            raise ValueError("dataset_identity_invalid")
        return self.root / "datasets" / dataset_id

    def build(self, sources, *, allow_fixture=False, max_bytes=256*1024**2, shard_rows=4096):
        if type(shard_rows) is not int or not 1 <= shard_rows <= 65536:
            raise ValueError("dataset_shard_size_invalid")
        parent = self.root / "datasets"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent, prefix=".dataset-") as name:
            staging = Path(name) / "ready"
            staging.mkdir()
            db = sqlite3.connect(Path(name) / "sort.sqlite3")
            source_ids = set()
            total = output_bytes = duplicates = 0
            try:
                db.execute("CREATE TABLE rows (game TEXT, seat INTEGER, window TEXT, payload BLOB, PRIMARY KEY(game, seat, window))")
                for source in sorted(map(Path, sources)):
                    total += source.stat().st_size
                    if source.is_symlink() or total > max_bytes:
                        raise ValueError("dataset_input_budget_exceeded")
                    payload = source.read_bytes()
                    source_ids.add(hashlib.sha256(payload).hexdigest())
                    for row in decision_rows(json.loads(payload), allow_fixture=allow_fixture):
                        key = (row["game_id"], row["seat"], row["window_id"])
                        encoded = canonical(row)+b"\n"
                        previous = db.execute("SELECT payload FROM rows WHERE game=? AND seat=? AND window=?", key).fetchone()
                        if previous:
                            if previous[0] != encoded:
                                raise ValueError("dataset_window_identity_conflict")
                            duplicates += 1
                            continue
                        output_bytes += len(encoded)
                        if output_bytes > max_bytes:
                            raise ValueError("dataset_output_budget_exceeded")
                        db.execute("INSERT INTO rows VALUES (?,?,?,?)", (*key, encoded))
                    db.commit()
                count = db.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
                if not count:
                    raise ValueError("dataset_no_eligible_decisions")
                shards = []
                full_hash = hashlib.sha256()
                stream = None
                try:
                    for index, (encoded,) in enumerate(db.execute("SELECT payload FROM rows ORDER BY game,seat,window")):
                        if index % shard_rows == 0:
                            if stream:
                                stream.close()
                                shards[-1]["sha256"] = shard_hash.hexdigest()
                            filename = "rows.jsonl" if count <= shard_rows else f"rows-{len(shards):05d}.jsonl"
                            stream = (staging / filename).open("xb")
                            shard_hash = hashlib.sha256()
                            shards.append({"path": filename, "row_count": 0})
                        stream.write(encoded)
                        shard_hash.update(encoded)
                        full_hash.update(encoded)
                        shards[-1]["row_count"] += 1
                    shards[-1]["sha256"] = shard_hash.hexdigest()
                finally:
                    if stream:
                        stream.close()
            finally:
                db.close()
            document = {"document_type": "forge_bc_dataset_v1", "schema_version": 1,
                        "sources": sorted(source_ids), "row_count": count, "shards": shards,
                        "profile_id": "competitive_public_actor_i32_v1", "rows_sha256": full_hash.hexdigest(),
                        "converter_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        "evidence_kind": "test_fixture", "engine_witnessed": False, "production_ready": False}
            dataset_id = identity(document)
            target = self.path(dataset_id)
            if target.exists():
                if self.audit(dataset_id)["status"] != "passed":
                    raise ValueError("dataset_existing_artifact_corrupt")
            else:
                atomic_json(staging / "manifest.json", document)
                staging.rename(target)
        return {**document, "dataset_id": dataset_id, "status": "completed", "duplicates_removed": duplicates}

    def audit(self, dataset_id):
        root = self.path(dataset_id)
        try:
            manifest = json.loads((root / "manifest.json").read_bytes())
            valid = identity(manifest) == dataset_id
            shards = manifest.get("shards", [{"path": "rows.jsonl", "sha256": manifest["rows_sha256"], "row_count": manifest["row_count"]}])
            seen = set()
            full_hash = hashlib.sha256()
            count = 0
            for shard in shards:
                filename = shard["path"]
                if not re.fullmatch(r"rows(?:-\d{5})?\.jsonl", filename) or filename in seen:
                    raise ValueError("dataset_shard_invalid")
                seen.add(filename)
                if (root / filename).is_symlink():
                    raise ValueError("dataset_shard_invalid")
                shard_hash = hashlib.sha256()
                shard_count = 0
                with (root / filename).open("rb") as stream:
                    for line in stream:
                        shard_hash.update(line)
                        full_hash.update(line)
                        row = json.loads(line)
                        stored = row.pop("row_id")
                        if identity(row) != stored:
                            raise ValueError("dataset_row_integrity_failed")
                        shard_count += 1
                count += shard_count
                valid = valid and shard_count == shard["row_count"] and shard_hash.hexdigest() == shard["sha256"]
            valid = valid and count == manifest["row_count"] and full_hash.hexdigest() == manifest["rows_sha256"]
        except (OSError, ValueError, KeyError, TypeError):
            valid = False
        return {"document_type": "forge_dataset_audit_v1", "dataset_id": dataset_id, "status": "passed" if valid else "failed"}

    def rows(self, dataset_id):
        if self.audit(dataset_id)["status"] != "passed":
            raise ValueError("dataset_integrity_failed")
        root = self.path(dataset_id)
        manifest = json.loads((root / "manifest.json").read_bytes())
        for shard in manifest.get("shards", [{"path": "rows.jsonl"}]):
            with (root / shard["path"]).open(encoding="utf-8") as stream:
                for line in stream:
                    yield json.loads(line)

    def stats(self, dataset_id):
        groups = set()
        counts = {}
        count = 0
        tensors = {}
        contexts = {}
        for row in self.rows(dataset_id):
            count += 1
            groups.add(row["related_match_id"])
            key = str(row["desired_count"])
            counts[key] = counts.get(key, 0) + 1
            context = str(row["frame_i32"][16])
            contexts[context] = contexts.get(context, 0)+1
            tensor_id = identity({key: row[key] for key in ("profile_id", "frame_i32", "frame_presence_i32", "option_i32", "option_presence_i32", "option_mask_i32", "model_eligible_mask")})
            group = tensors.setdefault(tensor_id, {"count": 0, "labels": set()})
            group["count"] += 1
            group["labels"].add(identity([row["selected_rows"], row["desired_count"]]))
        return {"document_type": "forge_dataset_stats_v1", "status": "passed", "dataset_id": dataset_id,
                "row_count": count, "related_matches": len(groups), "desired_count_distribution": counts,
                "context_distribution": contexts, "duplicate_tensor_groups": sum(g["count"] > 1 for g in tensors.values()),
                "conflicting_tensor_groups": sum(len(g["labels"]) > 1 for g in tensors.values())}

    def split(self, dataset_id, *, seed=20260908, ratios=(80, 10, 10)):
        if len(ratios) != 3 or sum(ratios) != 100 or any(type(v) is not int or v < 0 for v in ratios):
            raise ValueError("dataset_split_ratios_invalid")
        groups = {}
        for row in self.rows(dataset_id):
            group = row["related_match_id"]
            bucket = int(identity([seed, group])[:16], 16) % 100
            groups[group] = "train" if bucket < ratios[0] else "validation" if bucket < sum(ratios[:2]) else "test"
        document = {"document_type": "forge_dataset_split_v1", "dataset_id": dataset_id, "seed": seed,
                    "ratios": list(ratios), "groups": groups}
        split_id = identity(document)
        target = self.root / "splits" / (split_id + ".json")
        if target.exists() and json.loads(target.read_bytes()) != document:
            raise ValueError("dataset_split_identity_conflict")
        if not target.exists():
            atomic_json(target, document)
        return {**document, "split_id": split_id, "status": "completed"}

    def export(self, dataset_id, output):
        if self.audit(dataset_id)["status"] != "passed":
            raise ValueError("dataset_integrity_failed")
        target = Path(output)
        if target.exists():
            raise ValueError("dataset_export_exists")
        shutil.copytree(self.path(dataset_id), target)
        return {"document_type": "forge_dataset_export_v1", "status": "completed", "dataset_id": dataset_id, "path": str(target)}
