"""Deterministic integer linear BC baseline with explicit count-head limits."""
import hashlib
import json
from pathlib import Path
import platform
import re
import tempfile
import random
from importlib.metadata import version, PackageNotFoundError

from .datasets import DatasetStore
from .replays import atomic_json, identity
from .resources_gate import check_pressure, heavy_job


def _features(row, index):
    return [v * p for v, p in zip(row["option_i32"][index], row["option_presence_i32"][index], strict=True)]


def _dependencies():
    try:
        return {name: version(name) for name in ("numpy", "onnx", "onnxruntime")}
    except PackageNotFoundError as error:
        raise ValueError("training_model_dependencies_missing_install_model_extra") from error


def _shuffled(rows, seed):
    rng = random.Random(seed)
    buffer = []
    for row in rows:
        buffer.append(row)
        if len(buffer) == 128:
            rng.shuffle(buffer)
            yield from buffer
            buffer.clear()
    rng.shuffle(buffer)
    yield from buffer


def _validate(row):
    if row["desired_count"] != row["frame_i32"][17]:
        raise ValueError("training_count_head_unsupported")
    if len(row["selected_rows"]) != row["desired_count"] or any(not row["model_eligible_mask"][i] for i in row["selected_rows"]):
        raise ValueError("training_label_outside_domain")


def predict(row, weights):
    _validate(row)
    scores = {}
    for i, eligible in enumerate(row["model_eligible_mask"]):
        if eligible:
            total = sum(v*w for v, w in zip(_features(row, i), weights, strict=True))
            scores[i] = ((total + 2**31) % 2**32) - 2**31
    return sorted(scores, key=lambda i: (-scores[i], row["semantic_keys"][i], i))[:row["desired_count"]]


def fit_epoch(rows, weights, *, progress=None):
    weights = list(weights)
    for index, row in enumerate(rows):
        if progress is not None and index % 128 == 0:
            progress()
        chosen = set(predict(row, weights))
        expected = set(row["selected_rows"])
        for positive, negative in zip(sorted(expected - chosen), sorted(chosen - expected), strict=True):
            good, bad = _features(row, positive), _features(row, negative)
            for i in range(16):
                delta = (good[i] > bad[i]) - (good[i] < bad[i])
                weights[i] = max(-16, min(16, weights[i] + delta))
    return weights


def export_equivalence(rows, weights, artifact):
    from .ptcgai_ort import OrtActor
    from scripts.ai.ptcgdap.ptcgai_model_actor import PublicActorTensors
    actor = OrtActor(artifact, timeout_ms=1000)
    count = 0
    for row in rows:
        size = len(row["option_i32"])
        tensors = PublicActorTensors(profile_id=row["profile_id"],
            frame_i32=tuple(row["frame_i32"]), frame_presence_i32=tuple(row["frame_presence_i32"]),
            option_i32=tuple(tuple(v) for v in row["option_i32"])+((0,)*16,)*(1024-size),
            option_presence_i32=tuple(tuple(v) for v in row["option_presence_i32"])+((0,)*16,)*(1024-size),
            option_mask_i32=tuple(row["option_mask_i32"])+(0,)*(1024-size), semantic_keys=tuple(row["semantic_keys"]),
            row_to_current_index=tuple(range(size)), current_index_to_row={i:i for i in range(size)},
            min_count=row["frame_i32"][17], max_count=row["frame_i32"][18])
        scores, desired, _ = actor.run(tensors)
        expected = [((sum(v*w for v,w in zip(_features(row, i), weights, strict=True))+2**31) % 2**32)-2**31 for i in range(size)]
        if scores[:size] != expected or desired != [row["desired_count"]]:
            raise ValueError("training_export_equivalence_failed")
        count += 1
    if not count:
        raise ValueError("training_holdout_empty")
    return {"status": "passed", "rows": count, "comparison": "exact_int32_scores_and_count"}


def evaluate_rows(rows, weights):
    count = correct = count_correct = 0
    contexts = {}
    for row in rows:
        selected = predict(row, weights)
        matched = set(selected) == set(row["selected_rows"])
        count += 1
        correct += matched
        count_correct += len(selected) == row["desired_count"]
        context = str(row["frame_i32"][16])
        summary = contexts.setdefault(context, {"rows": 0, "correct": 0})
        summary["rows"] += 1
        summary["correct"] += matched
    if not count:
        raise ValueError("training_holdout_empty")
    return {"rows": count, "exact_set_accuracy": correct/count, "count_accuracy": count_correct/count,
            "zero_one_loss": 1-correct/count, "contexts": contexts}


class TrainingService:
    def __init__(self, workspace):
        self.workspace = Path(workspace)
        self.data = DatasetStore(workspace)

    def _split(self, dataset_id, split_id):
        if not re.fullmatch(r"[a-f0-9]{64}", split_id):
            raise ValueError("training_split_invalid")
        path = self.workspace / "data/splits" / (split_id + ".json")
        split = json.loads(path.read_bytes())
        if identity(split) != split_id or split["dataset_id"] != dataset_id:
            raise ValueError("training_split_invalid")
        groups = {row["related_match_id"] for row in self.data.rows(dataset_id)}
        if set(split["groups"]) != groups or any(value not in {"train", "validation", "test"} for value in split["groups"].values()):
            raise ValueError("training_split_invalid")
        return split

    def bc(self, dataset_id, split_id, *, epochs=8, seed=20260909, resume=False, allow_fixture=False):
        from .jobs import JobStore
        jobs = JobStore()
        inputs = {"workspace": str(self.workspace.resolve()), "dataset_id": dataset_id, "split_id": split_id,
                  "epochs": epochs, "seed": seed, "allow_fixture": allow_fixture}
        job_id = jobs.start("training.bc", inputs)
        def progress():
            if jobs.cancelled(job_id):
                raise ValueError("training_cancelled")
            jobs.heartbeat(job_id)
            check_pressure()
        try:
            result = self._bc(dataset_id, split_id, epochs=epochs, seed=seed, resume=resume,
                              allow_fixture=allow_fixture, progress=progress)
            jobs.finish(job_id, "completed", {"run_id": result["run_id"]})
            return {**result, "job_id": job_id}
        except BaseException as error:
            code = str(error) if isinstance(error, ValueError) else "training_interrupted" if isinstance(error, KeyboardInterrupt) else "training_failed"
            status = "cancelled" if code == "training_cancelled" else "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
            try:
                jobs.finish(job_id, status, {"code": code})
            except ValueError:
                pass  # A superseded attempt has no authority over its replacement.
            raise

    def _bc(self, dataset_id, split_id, *, epochs, seed, resume, allow_fixture, progress):
        if type(epochs) is not int or not 1 <= epochs <= 1000 or type(seed) is not int:
            raise ValueError("training_config_invalid")
        if self.data.audit(dataset_id)["status"] != "passed":
            raise ValueError("dataset_integrity_failed")
        manifest = json.loads((self.data.path(dataset_id) / "manifest.json").read_bytes())
        if manifest["evidence_kind"] == "test_fixture" and not allow_fixture:
            raise ValueError("training_fixture_requires_opt_in")
        split = self._split(dataset_id, split_id)
        scope = {"dataset_id": dataset_id, "split_id": split_id, "epochs": epochs, "seed": seed,
                 "algorithm": "integer_linear_margin_bc_v1", "count_head": "minimum_count_only",
                 "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 "exporter_sha256": hashlib.sha256(Path(__file__).with_name("ptcgai_ort.py").read_bytes()).hexdigest(),
                 "dependencies": _dependencies(),
                 "python": platform.python_version()}
        run_id = identity(scope)
        root = self.workspace / "runs" / run_id
        root.mkdir(parents=True, exist_ok=True)
        checkpoint = root / "checkpoint.json"
        history = []
        def rows(partition):
            for index, row in enumerate(self.data.rows(dataset_id)):
                if index % 128 == 0:
                    progress()
                if split["groups"].get(row["related_match_id"]) == partition:
                    _validate(row)
                    yield row
        # No training or model selection may read the test partition.
        for partition in ("train", "validation", "test"):
            if next(rows(partition), None) is None:
                raise ValueError("training_holdout_empty")
        weights = [0]*16
        best = list(weights)
        best_score = -1
        start_epoch = 0
        if checkpoint.exists():
            if not resume:
                raise ValueError("training_run_exists_use_resume")
            saved = json.loads(checkpoint.read_bytes())
            seal = saved.pop("sha256", None)
            if identity(saved) != seal or saved["scope"] != scope:
                raise ValueError("training_checkpoint_incompatible")
            weights, best, best_score = saved["weights"], saved["best_weights"], saved["best_score"]
            history, start_epoch = saved["history"], saved["epoch"]
        with heavy_job(workers=1):
            for epoch in range(start_epoch, epochs):
                progress()
                weights = fit_epoch(_shuffled(rows("train"), seed+epoch), weights, progress=progress)
                validation = evaluate_rows(rows("validation"), weights)
                if validation["exact_set_accuracy"] > best_score:
                    best, best_score = list(weights), validation["exact_set_accuracy"]
                history.append({"epoch": epoch+1, "validation": validation})
                saved = {"scope": scope, "epoch": epoch+1, "weights": weights, "best_weights": best,
                         "best_score": best_score, "history": history}
                atomic_json(checkpoint, {**saved, "sha256": identity(saved)})
            # Test is measured once after selecting the best validation checkpoint.
            test = evaluate_rows(rows("test"), best)
            from .ptcgai_ort import write_linear_actor_onnx, import_onnx_to_ort, conformance
            onnx_path = root / "actor.onnx"
            ort_path = root / "actor.ort"
            with tempfile.TemporaryDirectory(dir=root, prefix=".export-") as temp:
                expected = Path(temp) / "actor.onnx"
                write_linear_actor_onnx(expected, best)
                if onnx_path.exists() and onnx_path.read_bytes() != expected.read_bytes():
                    raise ValueError("training_export_integrity_failed")
                if not onnx_path.exists():
                    expected.rename(onnx_path)
            if not ort_path.exists():
                import_onnx_to_ort(onnx_path, ort_path)
            checked = conformance(ort_path)
            if checked["status"] != "passed":
                raise ValueError("training_export_conformance_failed")
            equivalence = export_equivalence(rows("test"), best, ort_path)
        report = {"document_type": "forge_bc_training_run_v1", "status": "completed", "run_id": run_id,
                  "scope": scope, "weights": best, "history": history, "test": test,
                  "actor_onnx": str(onnx_path), "actor_ort": str(ort_path),
                  "actor_sha256": hashlib.sha256(ort_path.read_bytes()).hexdigest(), "conformance": checked,
                  "onnx_sha256": hashlib.sha256(onnx_path.read_bytes()).hexdigest(), "export_equivalence": equivalence,
                  "evidence_kind": manifest["evidence_kind"], "engine_evaluated": False, "production_ready": False}
        atomic_json(root / "run.json", report)
        return report

    def load_run(self, run_id):
        if not re.fullmatch(r"[a-f0-9]{64}", run_id):
            raise ValueError("training_run_invalid")
        root = self.workspace / "runs" / run_id
        report = json.loads((root / "run.json").read_bytes())
        checkpoint = json.loads((root / "checkpoint.json").read_bytes())
        seal = checkpoint.pop("sha256", None)
        if (identity(report["scope"]) != run_id or identity(checkpoint) != seal
                or checkpoint["scope"] != report["scope"] or checkpoint["best_weights"] != report["weights"]
                or hashlib.sha256((root / "actor.onnx").read_bytes()).hexdigest() != report["onnx_sha256"]
                or hashlib.sha256((root / "actor.ort").read_bytes()).hexdigest() != report["actor_sha256"]):
            raise ValueError("training_run_integrity_failed")
        return report

    def evaluate(self, run_id):
        report = self.load_run(run_id)
        scope = report["scope"]
        split = self._split(scope["dataset_id"], scope["split_id"])
        with heavy_job(workers=1):
            metrics = evaluate_rows((r for r in self.data.rows(scope["dataset_id"])
                                     if split["groups"][r["related_match_id"]] == "test"), report["weights"])
        return {"document_type": "forge_offline_evaluation_v1", "status": "completed", "run_id": run_id,
                "dataset_id": scope["dataset_id"], "split_id": scope["split_id"], "metrics": metrics,
                "engine_evaluated": False, "evidence_kind": report["evidence_kind"]}

    def compare(self, candidate, baseline):
        first = self.evaluate(candidate)
        second = self.evaluate(baseline)
        if (first["dataset_id"], first["split_id"]) != (second["dataset_id"], second["split_id"]):
            raise ValueError("evaluation_inputs_not_comparable")
        return {"document_type": "forge_offline_comparison_v1", "status": "completed", "candidate": first,
                "baseline": second, "exact_set_accuracy_delta": first["metrics"]["exact_set_accuracy"] - second["metrics"]["exact_set_accuracy"],
                "engine_evaluated": False}
