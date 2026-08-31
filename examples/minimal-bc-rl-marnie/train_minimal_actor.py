from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import random
import sys
from typing import Any


WORKSPACE = Path(__file__).resolve().parent
ROOT = WORKSPACE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ai.ptcgdap.author_strategy_package import (  # noqa: E402
    CABT_CONTRACT_SHA256,
    CARD_CATALOG_SHA256,
)
from scripts.ai.ptcgdap.ptcgai_model_actor import (  # noqa: E402
    PublicActorTensorizer,
    PublicActorTensors,
)
from scripts.ai.ptcgdap.ptcgai_model_package import (  # noqa: E402
    build_model_manifest,
    canonical_bytes,
)
from src.ptcg_strategy_forge.ptcgai_ort import (  # noqa: E402
    OrtActor,
    import_onnx_to_ort,
    write_linear_actor_onnx,
)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _scenario_context(document: dict[str, Any]) -> tuple[dict[str, Any], dict[int, str]]:
    raw = document["raw_observation"]
    current = raw["current"]
    select = raw["select"]
    chooser = current["yourIndex"]
    opponent = 1 - chooser
    players = current["players"]
    context = {
        "clocks": {
            "turn": current["turn"],
            "turn_action_count": current["turnActionCount"],
            "remaining_overage_time": raw["remainingOverageTime"],
            "acting_prizes_remaining": len(players[chooser]["prize"]),
            "opponent_prizes_remaining": len(players[opponent]["prize"]),
            "acting_deck_count": players[chooser]["deckCount"],
            "opponent_deck_count": players[opponent]["deckCount"],
            "acting_hand_count": players[chooser]["handCount"],
            "opponent_hand_count": players[opponent]["handCount"],
        },
        "public_state": {
            "turn_flags": {
                "first_player": current["firstPlayer"],
                "result": current["result"],
                "supporter_played": current["supporterPlayed"],
                "stadium_played": current["stadiumPlayed"],
                "energy_attached": current["energyAttached"],
                "retreated": current["retreated"],
            }
        },
        "select_semantics": {
            "select_type_raw": select["type"],
            "select_context_raw": select["context"],
            "min_count": select["minCount"],
            "max_count": select["maxCount"],
            "remain_damage_counter": select["remainDamageCounter"],
            "remain_energy_cost": select["remainEnergyCost"],
            "options": [
                {"index": index, "fingerprint": "0" * 64, "raw": option}
                for index, option in enumerate(select["option"])
            ],
        },
    }
    local_uids = {
        row["index"]: row["local_card_uid"]
        for row in document["local_uid_bindings"]["options"]
        if row["local_card_uid"] is not None
    }
    return context, local_uids


def _examples() -> tuple[list[tuple[PublicActorTensors, int, str]], set[str]]:
    deck = json.loads((WORKSPACE / "package/deck/deck_manifest.json").read_text(encoding="utf-8"))
    allowed_uids = {row["local_card_uid"] for row in deck["cards"]}
    result: list[tuple[PublicActorTensors, int, str]] = []
    suite = json.loads((WORKSPACE / "scenario-suite.json").read_text(encoding="utf-8"))
    for case in suite["cases"]:
        # BC/RL may learn only adapter-owned same-tier preferences. Mandatory,
        # terminal, tier, veto and Base-fallback cases remain safety gates and
        # are intentionally absent from the training labels.
        if (
            case["expect"]["status"] != "passed"
            or len(case["expect"].get("selected_indexes", [])) != 1
            or "matched_rule_id" not in case["expect"]
        ):
            continue
        document = json.loads((WORKSPACE / case["path"]).read_text(encoding="utf-8"))
        context, local_uids = _scenario_context(document)
        tensors = PublicActorTensorizer.tensorize(
            context,
            local_option_uids=local_uids,
            allowed_card_uids=allowed_uids,
        )
        result.append((tensors, int(case["expect"]["selected_indexes"][0]), case["id"]))
    if not result:
        raise RuntimeError("minimal_training_examples_missing")
    return result, allowed_uids


def _score(weights: list[int], row: tuple[int, ...]) -> int:
    # Match int32 MatMul semantics while keeping training deterministic.
    unsigned = sum(weight * feature for weight, feature in zip(weights, row)) & 0xFFFFFFFF
    return unsigned - 0x100000000 if unsigned >= 0x80000000 else unsigned


def _predict(weights: list[int], tensors: PublicActorTensors) -> int:
    ranked = sorted(
        range(len(tensors.row_to_current_index)),
        key=lambda row: (
            -_score(weights, tensors.option_i32[row]),
            tensors.semantic_keys[row],
            tensors.row_to_current_index[row],
        ),
    )
    return tensors.row_to_current_index[ranked[0]]


def _bounded_update(
    weights: list[int], tensors: PublicActorTensors, teacher: int, predicted: int
) -> None:
    teacher_row = tensors.option_i32[tensors.current_index_to_row[teacher]]
    predicted_row = tensors.option_i32[tensors.current_index_to_row[predicted]]
    for index, (wanted, observed) in enumerate(zip(teacher_row, predicted_row)):
        if wanted == observed:
            continue
        weights[index] = max(-16, min(16, weights[index] + (1 if wanted > observed else -1)))


def _accuracy(weights: list[int], examples: list[tuple[PublicActorTensors, int, str]]) -> float:
    return sum(_predict(weights, tensors) == teacher for tensors, teacher, _ in examples) / len(examples)


def _train(examples: list[tuple[PublicActorTensors, int, str]]) -> tuple[list[int], dict[str, Any]]:
    weights = [0] * 16
    bc_updates = 0
    for _epoch in range(8):
        for tensors, teacher, _case_id in examples:
            predicted = _predict(weights, tensors)
            if predicted != teacher:
                _bounded_update(weights, tensors, teacher, predicted)
                bc_updates += 1
    bc_accuracy = _accuracy(weights, examples)

    # Small deterministic contextual-bandit phase. The environment reward is
    # +1 for the public teacher action and -1 otherwise; this is deliberately
    # a local demonstration, not a promotable full-game RL claim.
    rng = random.Random(20260830)
    rewards: list[int] = []
    rl_updates = 0
    for episode in range(64):
        tensors, teacher, _case_id = examples[episode % len(examples)]
        if rng.random() < 0.20:
            action = rng.choice(list(tensors.row_to_current_index))
        else:
            action = _predict(weights, tensors)
        reward = 1 if action == teacher else -1
        rewards.append(reward)
        if reward < 0:
            _bounded_update(weights, tensors, teacher, action)
            rl_updates += 1
    return weights, {
        "bc": {
            "objective": "public_teacher_action_imitation",
            "epochs": 8,
            "updates": bc_updates,
            "accuracy": bc_accuracy,
        },
        "rl": {
            "objective": "offline_contextual_bandit_teacher_reward",
            "episodes": len(rewards),
            "updates": rl_updates,
            "reward_sum": sum(rewards),
            "mean_reward": sum(rewards) / len(rewards),
            "epsilon": 0.20,
        },
        "final_teacher_accuracy": _accuracy(weights, examples),
    }


def main() -> int:
    examples, allowed_uids = _examples()
    weights, metrics = _train(examples)
    model_source = WORKSPACE / "model-source/actor.onnx"
    actor_path = WORKSPACE / "package/model/actor.ort"
    manifest_path = WORKSPACE / "package/model/model_manifest.json"
    # Keep converter intermediates outside the package. The resulting frozen
    # artifact is hashed into the manifest; package builds never reconvert it.
    staging_root = WORKSPACE / "build/.minimal-bc-rl-staging"
    staging_root.mkdir(parents=True, exist_ok=True)
    onnx_path = staging_root / "actor.onnx"
    ort_path = staging_root / "actor.ort"
    for stale in (onnx_path, ort_path):
        if stale.exists():
            stale.unlink()
    try:
        write_linear_actor_onnx(onnx_path, weights)
        import_report = import_onnx_to_ort(onnx_path, ort_path)
        actor = OrtActor(ort_path, timeout_ms=1000)
        runtime_correct = 0
        runtime_elapsed_ms: list[float] = []
        for tensors, teacher, _case_id in examples:
            scores, desired, elapsed_ms = actor.run(tensors)
            predicted = sorted(
                tensors.row_to_current_index,
                key=lambda index: (
                    -scores[tensors.current_index_to_row[index]],
                    tensors.semantic_keys[tensors.current_index_to_row[index]],
                    index,
                ),
            )[0]
            runtime_correct += int(predicted == teacher and desired == [tensors.min_count])
            runtime_elapsed_ms.append(elapsed_ms)
        actor_bytes = ort_path.read_bytes()
        manifest = build_model_manifest(
            actor_bytes,
            model_id="dev.codex.minimal-bc-rl-marnie.actor",
            cabt_contract_sha256=CABT_CONTRACT_SHA256,
            card_catalog_sha256=CARD_CATALOG_SHA256,
            training_method="bc_rl",
            source_run_id="minimal-public-bc-rl-20260830",
        )
        model_source.parent.mkdir(parents=True, exist_ok=True)
        actor_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(onnx_path, model_source)
        os.replace(ort_path, actor_path)
        manifest_path.write_bytes(canonical_bytes(manifest))
    finally:
        for stale in (onnx_path, ort_path):
            if stale.exists():
                stale.unlink()

    report = {
        "document_type": "minimal_ptcgai_bc_rl_training_report_v1",
        "schema_version": 1,
        "status": "passed" if metrics["final_teacher_accuracy"] == 1.0 and runtime_correct == len(examples) else "failed",
        "run_id": "minimal-public-bc-rl-20260830",
        "example_count": len(examples),
        "case_ids": [case_id for _tensors, _teacher, case_id in examples],
        "allowed_local_uid_count": len(allowed_uids),
        "weights_i32": weights,
        "metrics": metrics,
        "runtime_conformance": {
            "correct_examples": runtime_correct,
            "total_examples": len(examples),
            "maximum_elapsed_ms": max(runtime_elapsed_ms),
            "cpu_only": True,
            "fixed_shape": True,
        },
        "artifact": {
            "path": "package/model/actor.ort",
            "sha256": _sha(actor_path.read_bytes()),
            "bytes": actor_path.stat().st_size,
            "source_onnx_sha256": import_report["source_onnx_sha256"],
        },
        "claims": {
            "training_method": "bc_rl",
            "rl_scope": "offline_contextual_bandit",
            "promotable_training_run": False,
            "full_game_rl": False,
            "public_only": True,
            "production_authority": False,
        },
    }
    report_path = WORKSPACE / "build/minimal-bc-rl-training-report.json"
    report_path.write_bytes(canonical_bytes(report))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
