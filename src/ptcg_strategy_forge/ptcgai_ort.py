from __future__ import annotations

import hashlib
from pathlib import Path
import time
from typing import Any

import numpy as np
import onnx
import onnxruntime as ort

from scripts.ai.ptcgdap.ptcgai_model_actor import PublicActorTensors
from scripts.ai.ptcgdap.ptcgai_model_package import (
    ALLOWED_ONNX_OPS,
    MODEL_MAX_BYTES,
    tensor_profile_document,
)


class OrtActorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _raise(code: str) -> None:
    raise OrtActorError(code)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _expected_io() -> tuple[dict[str, tuple[str, tuple[int, ...]]], dict[str, tuple[str, tuple[int, ...]]]]:
    profile = tensor_profile_document()
    inputs = {
        entry["name"]: (entry["dtype"], tuple(entry["shape"]))
        for entry in profile["inputs"]
    }
    outputs = {
        entry["name"]: (entry["dtype"], tuple(entry["shape"]))
        for entry in profile["outputs"]
    }
    return inputs, outputs


def _onnx_shape(value_info: Any) -> tuple[str, tuple[int, ...]]:
    tensor = value_info.type.tensor_type
    if tensor.elem_type != onnx.TensorProto.INT32:
        _raise("model_tensor_dtype_invalid")
    shape: list[int] = []
    for dim in tensor.shape.dim:
        if not dim.HasField("dim_value") or dim.dim_value < 1:
            _raise("model_dynamic_shape_forbidden")
        shape.append(int(dim.dim_value))
    return "int32", tuple(shape)


def inspect_onnx(path: Path) -> dict[str, Any]:
    source = Path(path)
    try:
        if source.is_symlink() or not source.is_file() or source.stat().st_size > MODEL_MAX_BYTES:
            _raise("model_resource_limit_exceeded")
        model = onnx.load(str(source), load_external_data=False)
        onnx.checker.check_model(model, full_check=True)
    except OrtActorError:
        raise
    except Exception as error:
        raise OrtActorError("model_onnx_invalid") from error
    if any(initializer.data_location == onnx.TensorProto.EXTERNAL or initializer.external_data for initializer in model.graph.initializer):
        _raise("model_external_data_forbidden")
    if len(model.opset_import) != 1 or model.opset_import[0].domain not in {"", "ai.onnx"} or model.opset_import[0].version != 18:
        _raise("model_opset_invalid")
    operators = sorted({node.op_type for node in model.graph.node})
    illegal = sorted(set(operators) - set(ALLOWED_ONNX_OPS))
    if illegal or any(node.domain not in {"", "ai.onnx"} for node in model.graph.node):
        _raise("model_operator_forbidden")
    expected_inputs, expected_outputs = _expected_io()
    actual_inputs = {entry.name: _onnx_shape(entry) for entry in model.graph.input}
    actual_outputs = {entry.name: _onnx_shape(entry) for entry in model.graph.output}
    if actual_inputs != expected_inputs or actual_outputs != expected_outputs:
        _raise("model_tensor_profile_invalid")
    value = source.read_bytes()
    return {
        "document_type": "ptcgai_model_inspection_v1",
        "status": "valid",
        "source_format": "onnx",
        "artifact_sha256": _sha(value),
        "artifact_bytes": len(value),
        "opset": 18,
        "operators": operators,
        "inputs": [entry for entry in tensor_profile_document()["inputs"]],
        "outputs": [entry for entry in tensor_profile_document()["outputs"]],
        "external_data": False,
        "custom_ops": False,
        "fixed_shape": True,
        "cpu_only": True,
    }


def write_linear_actor_onnx(output: Path, weights: list[int]) -> dict[str, Any]:
    target = Path(output)
    if target.exists() or target.is_symlink():
        _raise("model_output_exists")
    if (
        type(weights) is not list
        or len(weights) != 16
        or any(type(value) is not int or not -(2**31) <= value < 2**31 for value in weights)
    ):
        _raise("model_training_weights_invalid")
    try:
        parent = target.parent.resolve(strict=True)
        if not parent.is_dir() or parent.is_symlink():
            _raise("model_output_parent_invalid")
        inputs = [
            onnx.helper.make_tensor_value_info("frame_i32", onnx.TensorProto.INT32, [1, 24]),
            onnx.helper.make_tensor_value_info("frame_presence_i32", onnx.TensorProto.INT32, [1, 24]),
            onnx.helper.make_tensor_value_info("option_i32", onnx.TensorProto.INT32, [1, 1024, 16]),
            onnx.helper.make_tensor_value_info("option_presence_i32", onnx.TensorProto.INT32, [1, 1024, 16]),
            onnx.helper.make_tensor_value_info("option_mask_i32", onnx.TensorProto.INT32, [1, 1024]),
        ]
        outputs = [
            onnx.helper.make_tensor_value_info("option_scores", onnx.TensorProto.INT32, [1, 1024]),
            onnx.helper.make_tensor_value_info("desired_count", onnx.TensorProto.INT32, [1]),
        ]
        initializers = [
            onnx.helper.make_tensor("linear_weights", onnx.TensorProto.INT32, [16, 1], weights),
            onnx.helper.make_tensor("score_shape", onnx.TensorProto.INT64, [2], [1, 1024]),
            onnx.helper.make_tensor("count_index", onnx.TensorProto.INT64, [1], [17]),
            onnx.helper.make_tensor("count_shape", onnx.TensorProto.INT64, [1], [1]),
        ]
        nodes = [
            onnx.helper.make_node("Mul", ["option_i32", "option_presence_i32"], ["present_options"]),
            onnx.helper.make_node("MatMul", ["present_options", "linear_weights"], ["raw_scores"]),
            onnx.helper.make_node("Reshape", ["raw_scores", "score_shape"], ["option_scores"]),
            onnx.helper.make_node("Gather", ["frame_i32", "count_index"], ["raw_count"], axis=1),
            onnx.helper.make_node("Reshape", ["raw_count", "count_shape"], ["desired_count"]),
        ]
        graph = onnx.helper.make_graph(nodes, "ptcgai-linear-actor-v1", inputs, outputs, initializer=initializers)
        model = onnx.helper.make_model(graph, opset_imports=[onnx.helper.make_opsetid("", 18)])
        model.ir_version = 10
        onnx.checker.check_model(model, full_check=True)
        onnx.save(model, target)
        return inspect_onnx(target)
    except OrtActorError:
        raise
    except Exception as error:
        if target.exists():
            target.unlink()
        raise OrtActorError("model_export_failed") from error


def _session_options() -> ort.SessionOptions:
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    options.enable_mem_pattern = False
    options.enable_cpu_mem_arena = True
    return options


def import_onnx_to_ort(source: Path, output: Path) -> dict[str, Any]:
    source_path = Path(source)
    output_path = Path(output)
    inspection = inspect_onnx(source_path)
    if output_path.exists() or output_path.is_symlink():
        _raise("model_output_exists")
    try:
        parent = output_path.parent.resolve(strict=True)
        if not parent.is_dir() or parent.is_symlink():
            _raise("model_output_parent_invalid")
        target = parent / output_path.name
        options = _session_options()
        options.optimized_model_filepath = str(target)
        options.add_session_config_entry("session.save_model_format", "ORT")
        ort.InferenceSession(
            str(source_path.resolve(strict=True)),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        result = inspect_ort(target)
    except OrtActorError:
        raise
    except Exception as error:
        if output_path.exists():
            output_path.unlink()
        raise OrtActorError("model_import_failed") from error
    return {
        **result,
        "status": "imported",
        "source_onnx_sha256": inspection["artifact_sha256"],
        "source_operators": inspection["operators"],
    }


def _runtime_io(session: ort.InferenceSession) -> tuple[dict[str, tuple[str, tuple[int, ...]]], dict[str, tuple[str, tuple[int, ...]]]]:
    def convert(items: list[Any]) -> dict[str, tuple[str, tuple[int, ...]]]:
        result: dict[str, tuple[str, tuple[int, ...]]] = {}
        for item in items:
            if item.type != "tensor(int32)" or any(type(dim) is not int or dim < 1 for dim in item.shape):
                _raise("model_tensor_profile_invalid")
            result[item.name] = ("int32", tuple(item.shape))
        return result

    return convert(session.get_inputs()), convert(session.get_outputs())


def inspect_ort(path: Path) -> dict[str, Any]:
    source = Path(path)
    try:
        if source.is_symlink() or not source.is_file():
            _raise("model_artifact_missing")
        value = source.read_bytes()
        if not value or len(value) > MODEL_MAX_BYTES:
            _raise("model_resource_limit_exceeded")
        session = ort.InferenceSession(
            value,
            sess_options=_session_options(),
            providers=["CPUExecutionProvider"],
        )
        inputs, outputs = _runtime_io(session)
    except OrtActorError:
        raise
    except Exception as error:
        raise OrtActorError("model_ort_invalid") from error
    expected_inputs, expected_outputs = _expected_io()
    if inputs != expected_inputs or outputs != expected_outputs:
        _raise("model_tensor_profile_invalid")
    if session.get_providers() != ["CPUExecutionProvider"]:
        _raise("model_execution_provider_invalid")
    return {
        "document_type": "ptcgai_model_inspection_v1",
        "status": "valid",
        "source_format": "ort",
        "artifact_sha256": _sha(value),
        "artifact_bytes": len(value),
        "runtime_version": ort.__version__,
        "execution_providers": session.get_providers(),
        "inputs": [entry for entry in tensor_profile_document()["inputs"]],
        "outputs": [entry for entry in tensor_profile_document()["outputs"]],
        "fixed_shape": True,
        "cpu_only": True,
    }


class OrtActor:
    __slots__ = ("_session", "_timeout_ms")

    def __init__(self, artifact: bytes | Path, *, timeout_ms: int = 25) -> None:
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 1000:
            _raise("model_timeout_profile_invalid")
        try:
            value = artifact if type(artifact) is bytes else Path(artifact).read_bytes()
            if type(value) is not bytes or not value or len(value) > MODEL_MAX_BYTES:
                _raise("model_resource_limit_exceeded")
            session = ort.InferenceSession(
                value,
                sess_options=_session_options(),
                providers=["CPUExecutionProvider"],
            )
            inputs, outputs = _runtime_io(session)
            expected_inputs, expected_outputs = _expected_io()
            if inputs != expected_inputs or outputs != expected_outputs:
                _raise("model_tensor_profile_invalid")
        except OrtActorError:
            raise
        except Exception as error:
            raise OrtActorError("model_unavailable") from error
        self._session = session
        self._timeout_ms = timeout_ms

    def run(self, tensors: PublicActorTensors) -> tuple[list[int], list[int], float]:
        feeds = {
            "frame_i32": np.asarray([tensors.frame_i32], dtype=np.int32),
            "frame_presence_i32": np.asarray([tensors.frame_presence_i32], dtype=np.int32),
            "option_i32": np.asarray([tensors.option_i32], dtype=np.int32),
            "option_presence_i32": np.asarray([tensors.option_presence_i32], dtype=np.int32),
            "option_mask_i32": np.asarray([tensors.option_mask_i32], dtype=np.int32),
        }
        started = time.perf_counter_ns()
        try:
            scores, desired = self._session.run(["option_scores", "desired_count"], feeds)
        except Exception as error:
            raise OrtActorError("model_inference_failed") from error
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        if elapsed_ms > self._timeout_ms:
            _raise("model_timeout")
        if scores.dtype != np.int32 or scores.shape != (1, 1024) or desired.dtype != np.int32 or desired.shape != (1,):
            _raise("model_output_shape_invalid")
        return scores[0].tolist(), desired.tolist(), elapsed_ms


def conformance(path: Path) -> dict[str, Any]:
    inspection = inspect_ort(path)
    actor = OrtActor(path)
    profile = tensor_profile_document()
    zeros = PublicActorTensors(
        profile_id=profile["profile_id"],
        frame_i32=(0,) * profile["frame_width"],
        frame_presence_i32=(0,) * profile["frame_width"],
        option_i32=((0,) * profile["option_width"],) * profile["max_options"],
        option_presence_i32=((0,) * profile["option_width"],) * profile["max_options"],
        option_mask_i32=(0,) * profile["max_options"],
        semantic_keys=(),
        row_to_current_index=(),
        current_index_to_row={},
        min_count=0,
        max_count=0,
    )
    scores, desired, elapsed = actor.run(zeros)
    return {
        "document_type": "ptcgai_model_conformance_v1",
        "status": "passed",
        "artifact_sha256": inspection["artifact_sha256"],
        "zero_vector_score_count": len(scores),
        "zero_vector_desired_count": desired,
        "elapsed_ms": round(elapsed, 6),
        "cpu_only": True,
        "remote_inference": False,
    }


__all__ = [
    "OrtActor",
    "OrtActorError",
    "conformance",
    "import_onnx_to_ort",
    "inspect_onnx",
    "inspect_ort",
    "write_linear_actor_onnx",
]
