from __future__ import annotations

"""Fresh-process callback probe for developer-local `.ptcgbot` qualification.

This is deliberately not described as a production security sandbox.  It
enforces the public callback/output contract and removes ordinary network and
subprocess capabilities so local results match the published runtime profile.
"""

import argparse
import hashlib
import importlib
import inspect
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any


def _deny(*_args: Any, **_kwargs: Any) -> Any:
    raise PermissionError("competition_capability_denied")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest().upper()


def _deck(path: Path) -> list[int]:
    body = path.read_bytes()
    lines = body.splitlines(keepends=True)
    if len(lines) != 60 or any(not line.endswith(b"\n") for line in lines):
        raise RuntimeError("competition_deck_format_invalid")
    result: list[int] = []
    for line in lines:
        raw = line[:-1]
        if not raw or not raw.isdigit() or raw.startswith(b"0"):
            raise RuntimeError("competition_deck_format_invalid")
        value = int(raw)
        if not 1 <= value <= 2**31 - 1:
            raise RuntimeError("competition_deck_format_invalid")
        result.append(value)
    return result


def _validate_result(observation: dict[str, Any], result: Any, deck: list[int]) -> tuple[str, str]:
    if inspect.isawaitable(result) or inspect.isgenerator(result) or inspect.isasyncgen(result):
        raise RuntimeError("invalid_agent_output")
    if type(result) is not list or any(type(value) is not int for value in result):
        raise RuntimeError("invalid_agent_output")
    select = observation.get("select")
    if select is None and observation.get("current") is None:
        if result != deck:
            raise RuntimeError("invalid_agent_deck_bootstrap")
        return "deck_bootstrap", "official_card_ids"
    if type(select) is not dict or type(select.get("option")) is not list:
        raise RuntimeError("invalid_agent_selection_window")
    minimum = select.get("minCount")
    maximum = select.get("maxCount")
    if (
        type(minimum) is not int
        or type(maximum) is not int
        or not 0 <= minimum <= maximum <= len(select["option"])
        or not minimum <= len(result) <= maximum
        or len(result) != len(set(result))
        or any(index < 0 or index >= len(select["option"]) for index in result)
    ):
        raise RuntimeError("invalid_agent_output")
    return "selection", "current_option_indexes"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package = args.package.resolve(strict=True)
    transcript = json.loads(args.transcript.read_text(encoding="utf-8"))
    observations = transcript.get("observations")
    if type(observations) is not list or not observations:
        raise RuntimeError("competition_transcript_invalid")
    deck = _deck(package / "deck.csv")

    # Keep the output primitive before importing author code.
    write_bytes = Path.write_bytes
    socket.socket = _deny  # type: ignore[assignment]
    socket.create_connection = _deny  # type: ignore[assignment]
    subprocess.Popen = _deny  # type: ignore[assignment]
    subprocess.run = _deny  # type: ignore[assignment]
    subprocess.call = _deny  # type: ignore[assignment]
    subprocess.check_call = _deny  # type: ignore[assignment]
    subprocess.check_output = _deny  # type: ignore[assignment]
    os.system = _deny  # type: ignore[assignment]

    source = package / "src"
    sys.path[:] = [str(source)] + [item for item in sys.path if item != str(package)]
    module = importlib.import_module("submission.main")
    policy = getattr(module, "agent", None)
    if (
        not inspect.isfunction(policy)
        or inspect.iscoroutinefunction(policy)
        or inspect.isasyncgenfunction(policy)
        or inspect.isgeneratorfunction(policy)
    ):
        raise RuntimeError("competition_agent_entrypoint_invalid")

    trace: list[dict[str, Any]] = []
    for ordinal, observation in enumerate(observations):
        if type(observation) is not dict:
            raise RuntimeError("competition_transcript_invalid")
        result = policy(observation)
        call_kind, response_domain = _validate_result(observation, result, deck)
        trace.append(
            {
                "ordinal": ordinal,
                "call_kind": call_kind,
                "response_domain": response_domain,
                "option_fingerprint": _sha(observation.get("select")),
                "result": result,
            }
        )
    report = {
        "document_type": "ptcgbot_callback_probe_v2",
        "schema_version": 2,
        "status": "passed",
        "trace": trace,
    }
    write_bytes(args.output, _canonical(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
