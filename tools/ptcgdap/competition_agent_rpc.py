from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from scripts.ai.ptcgdap.source_lock import canonical_json_v1_bytes, load_json_bytes_strict


REQUEST_KEYS = {
    "document_type",
    "schema_version",
    "session_token",
    "match_id",
    "seat",
    "ordinal",
    "observation",
    "request_sha256",
}
RESPONSE_KEYS = {
    "document_type",
    "schema_version",
    "session_token",
    "match_id",
    "seat",
    "ordinal",
    "request_sha256",
    "ok",
    "indexes",
    "error_code",
}
READY_KEYS = {
    "document_type",
    "schema_version",
    "session_token",
    "match_id",
    "seat",
    "contract_sha256",
}
REQUEST_V2_KEYS = REQUEST_KEYS | {"call_kind", "response_domain"}
RESPONSE_V2_KEYS = {
    "document_type",
    "schema_version",
    "session_token",
    "match_id",
    "seat",
    "ordinal",
    "request_sha256",
    "call_kind",
    "response_domain",
    "ok",
    "official_card_ids",
    "current_option_indexes",
    "error_code",
}


class RpcProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class RpcContract:
    value: dict[str, Any]
    canonical_sha256: str
    request_max_bytes: int
    response_max_bytes: int
    max_indexes: int
    minimum_index: int
    maximum_index: int
    minimum_decision_seconds: int
    maximum_decision_seconds: int
    default_decision_seconds: int
    poll_interval_seconds: float


def load_rpc_contract(repository_root: str | Path) -> RpcContract:
    path = (
        Path(repository_root).resolve()
        / "contracts/ptcgdap/competition_agent_rpc_contract.json"
    )
    try:
        raw = path.read_bytes()
        value = load_json_bytes_strict(raw)
        valid = (
            type(value) is dict
            and value["document_type"] == "ptcgdap_competition_agent_rpc_contract_v1"
            and value["schema_version"] == 1
            and value["transport"]["kind"] == "per_seat_filesystem_mailbox_v1"
            and value["transport"]["message_encoding"]
            == "utf8_sorted_key_json_finite_numbers_v1"
            and value["transport"]["one_in_flight_request_per_seat"] is True
            and value["transport"]["channel_shared_between_seats"] is False
            and value["request"]["persist_request"] is False
            and value["request"]["search_begin_input_ephemeral"] is True
            and value["response"]["persist_response"] is False
            and value["binding"]["session_token_required"] is True
            and value["binding"]["request_sha256_echo_required"] is True
            and value["binding"]["unknown_fields_fail_closed"] is True
            and value["production"]["agent_package_mount_read_only"] is True
            and value["production"]["channel_mount_private_to_one_seat"] is True
            and value["production"]["root_filesystem_read_only"] is True
            and value["production"]["temporary_filesystem_only"] is True
            and value["production"]["network_mode"] == "none"
            and value["production"]["service_credentials_visible"] is False
            and value["production"]["database_visible"] is False
            and value["production"]["opponent_package_visible"] is False
            and value["production"]["host_container_socket_visible"] is False
            and value["authority"]["agent_output"]
            == "current_request_index_list_only"
            and value["authority"]["engine_execution"] is False
            and value["authority"]["service_api"] is False
            and value["authority"]["player_runtime"] is False
        )
        request_max = value["request"]["max_bytes"]
        response_max = value["response"]["max_bytes"]
        max_indexes = value["response"]["max_indexes"]
        minimum_index = value["response"]["minimum_index"]
        maximum_index = value["response"]["maximum_index"]
        minimum_decision = value["timeouts"]["minimum_decision_seconds"]
        maximum_decision = value["timeouts"]["maximum_decision_seconds"]
        default_decision = value["timeouts"]["default_decision_seconds"]
        poll_ms = value["timeouts"]["poll_interval_milliseconds"]
        valid = valid and all(
            type(item) is int
            for item in (
                request_max,
                response_max,
                max_indexes,
                minimum_index,
                maximum_index,
                minimum_decision,
                maximum_decision,
                default_decision,
                poll_ms,
            )
        )
        valid = valid and (
            1024 <= request_max <= 64 * 1024 * 1024
            and 1024 <= response_max <= 1024 * 1024
            and 1 <= max_indexes <= 100_000
            and 0 <= minimum_index <= maximum_index <= 10_000_000
            and 1 <= minimum_decision <= default_decision <= maximum_decision <= 300
            and 1 <= poll_ms <= 1000
        )
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise RpcProtocolError("rpc_contract_invalid") from error
    if not valid:
        raise RpcProtocolError("rpc_contract_invalid")
    canonical = canonical_json_v1_bytes(value)
    return RpcContract(
        value=dict(value),
        canonical_sha256=_sha256(canonical),
        request_max_bytes=request_max,
        response_max_bytes=response_max,
        max_indexes=max_indexes,
        minimum_index=minimum_index,
        maximum_index=maximum_index,
        minimum_decision_seconds=minimum_decision,
        maximum_decision_seconds=maximum_decision,
        default_decision_seconds=default_decision,
        poll_interval_seconds=poll_ms / 1000.0,
    )


def load_rpc_contract_v2(repository_root: str | Path) -> RpcContract:
    path = (
        Path(repository_root).resolve()
        / "contracts/ptcgdap/competition_agent_rpc_contract_v2.json"
    )
    try:
        value = load_json_bytes_strict(path.read_bytes())
        valid = (
            type(value) is dict
            and value["document_type"] == "ptcgdap_competition_agent_rpc_contract_v2"
            and value["schema_version"] == 2
            and value["transport"]["kind"] == "per_seat_filesystem_mailbox_v2"
            and value["transport"]["one_in_flight_request_per_seat"] is True
            and value["transport"]["channel_shared_between_seats"] is False
            and value["request"]["document_type"] == "competition_agent_request_v2"
            and value["request"]["call_kinds"] == ["deck_bootstrap", "selection"]
            and value["request"]["response_domains"]
            == ["official_card_ids", "current_option_indexes"]
            and value["request"]["persist_request"] is False
            and value["response"]["document_type"] == "competition_agent_response_v2"
            and value["response"]["deck_card_count"] == 60
            and value["response"]["persist_response"] is False
            and value["binding"]["call_kind_echo_required"] is True
            and value["binding"]["response_domain_echo_required"] is True
            and value["binding"]["unknown_fields_fail_closed"] is True
            and value["production"]["network_mode"] == "none"
            and value["production"]["opponent_package_visible"] is False
            and value["authority"]["deck_bootstrap"]
            == "signed_release_deck_exact_match_only"
            and value["authority"]["selection"]
            == "current_request_option_indexes_only"
            and value["authority"]["engine_execution"] is False
        )
        request_max = value["request"]["max_bytes"]
        response_max = value["response"]["max_bytes"]
        max_indexes = value["response"]["max_indexes"]
        minimum_index = value["response"]["minimum_index"]
        maximum_index = value["response"]["maximum_index"]
        minimum_decision = value["timeouts"]["minimum_decision_seconds"]
        maximum_decision = value["timeouts"]["maximum_decision_seconds"]
        default_decision = value["timeouts"]["default_decision_seconds"]
        poll_ms = value["timeouts"]["poll_interval_milliseconds"]
        valid = valid and all(
            type(item) is int
            for item in (
                request_max,
                response_max,
                max_indexes,
                minimum_index,
                maximum_index,
                minimum_decision,
                maximum_decision,
                default_decision,
                poll_ms,
            )
        )
        valid = valid and (
            1024 <= request_max <= 64 * 1024 * 1024
            and 1024 <= response_max <= 1024 * 1024
            and 60 <= max_indexes <= 100_000
            and 0 <= minimum_index <= maximum_index <= 10_000_000
            and 1 <= minimum_decision <= default_decision <= maximum_decision <= 300
            and 1 <= poll_ms <= 1000
        )
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise RpcProtocolError("rpc_contract_invalid") from error
    if not valid:
        raise RpcProtocolError("rpc_contract_invalid")
    canonical = canonical_json_v1_bytes(value)
    return RpcContract(
        value=dict(value),
        canonical_sha256=_sha256(canonical),
        request_max_bytes=request_max,
        response_max_bytes=response_max,
        max_indexes=max_indexes,
        minimum_index=minimum_index,
        maximum_index=maximum_index,
        minimum_decision_seconds=minimum_decision,
        maximum_decision_seconds=maximum_decision,
        default_decision_seconds=default_decision,
        poll_interval_seconds=poll_ms / 1000.0,
    )


def build_request_v2(
    *,
    session_token: str,
    match_id: str,
    seat: int,
    ordinal: int,
    observation: Mapping[str, Any],
    contract: RpcContract,
) -> dict[str, Any]:
    copied = _plain_json_tree(observation)
    if type(copied) is not dict:
        raise RpcProtocolError("rpc_request_invalid")
    if copied.get("select") is None and copied.get("current") is None:
        call_kind = "deck_bootstrap"
        response_domain = "official_card_ids"
    elif type(copied.get("select")) is dict:
        call_kind = "selection"
        response_domain = "current_option_indexes"
    else:
        raise RpcProtocolError("rpc_request_invalid")
    unsigned = {
        "document_type": "competition_agent_request_v2",
        "schema_version": 2,
        "session_token": session_token,
        "match_id": match_id,
        "seat": seat,
        "ordinal": ordinal,
        "call_kind": call_kind,
        "response_domain": response_domain,
        "observation": copied,
    }
    value = {**unsigned, "request_sha256": _sha256(_canonical_rpc_json_bytes(unsigned))}
    return validate_request_v2(value, contract)


def validate_request_v2(value: Any, contract: RpcContract) -> dict[str, Any]:
    if type(value) is not dict or set(value) != REQUEST_V2_KEYS:
        raise RpcProtocolError("rpc_request_invalid")
    request = dict(value)
    expected_domain = {
        "deck_bootstrap": "official_card_ids",
        "selection": "current_option_indexes",
    }.get(request["call_kind"])
    if (
        request["document_type"] != "competition_agent_request_v2"
        or request["schema_version"] != 2
        or expected_domain is None
        or request["response_domain"] != expected_domain
        or not _token(request["session_token"])
        or not _identifier(request["match_id"])
        or request["seat"] not in (0, 1)
        or type(request["ordinal"]) is not int
        or request["ordinal"] < 0
        or type(request["observation"]) is not dict
        or not _sha256_value(request["request_sha256"])
    ):
        raise RpcProtocolError("rpc_request_invalid")
    if request["call_kind"] == "deck_bootstrap":
        if request["observation"].get("select") is not None or request["observation"].get("current") is not None:
            raise RpcProtocolError("rpc_request_domain_mismatch")
    elif type(request["observation"].get("select")) is not dict:
        raise RpcProtocolError("rpc_request_domain_mismatch")
    unsigned = dict(request)
    supplied = unsigned.pop("request_sha256")
    canonical = _canonical_rpc_json_bytes(unsigned)
    if len(canonical) > contract.request_max_bytes:
        raise RpcProtocolError("rpc_request_too_large")
    if _sha256(canonical) != supplied:
        raise RpcProtocolError("rpc_request_hash_invalid")
    return request


def build_response_v2(
    request: Mapping[str, Any],
    *,
    result: list[int] | None,
    error_code: str | None,
    contract: RpcContract,
) -> dict[str, Any]:
    domain = request["response_domain"]
    value = {
        "document_type": "competition_agent_response_v2",
        "schema_version": 2,
        "session_token": request["session_token"],
        "match_id": request["match_id"],
        "seat": request["seat"],
        "ordinal": request["ordinal"],
        "request_sha256": request["request_sha256"],
        "call_kind": request["call_kind"],
        "response_domain": domain,
        "ok": error_code is None,
        "official_card_ids": result if error_code is None and domain == "official_card_ids" else None,
        "current_option_indexes": result if error_code is None and domain == "current_option_indexes" else None,
        "error_code": error_code,
    }
    return validate_response_v2(value, contract, request=request)


def validate_response_v2(
    value: Any,
    contract: RpcContract,
    *,
    request: Mapping[str, Any],
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != RESPONSE_V2_KEYS:
        raise RpcProtocolError("rpc_response_invalid")
    response = dict(value)
    bindings = (
        "session_token", "match_id", "seat", "ordinal", "request_sha256",
        "call_kind", "response_domain",
    )
    if (
        response["document_type"] != "competition_agent_response_v2"
        or response["schema_version"] != 2
        or any(response[field] != request[field] for field in bindings)
    ):
        raise RpcProtocolError("rpc_response_domain_mismatch")
    if type(response["ok"]) is not bool:
        raise RpcProtocolError("rpc_response_invalid")
    if response["ok"]:
        if response["error_code"] is not None:
            raise RpcProtocolError("rpc_response_invalid")
        if response["response_domain"] == "official_card_ids":
            result = response["official_card_ids"]
            if response["current_option_indexes"] is not None:
                raise RpcProtocolError("rpc_response_domain_mismatch")
            if (
                type(result) is not list
                or len(result) != 60
                or any(type(card_id) is not int or card_id < 1 or card_id > 2**31 - 1 for card_id in result)
            ):
                raise RpcProtocolError("rpc_response_invalid")
        else:
            result = response["current_option_indexes"]
            if response["official_card_ids"] is not None:
                raise RpcProtocolError("rpc_response_domain_mismatch")
            select = request["observation"].get("select")
            if type(select) is not dict or type(select.get("option")) is not list:
                raise RpcProtocolError("rpc_response_invalid")
            minimum = select.get("minCount")
            maximum = select.get("maxCount")
            if (
                type(result) is not list
                or type(minimum) is not int
                or type(maximum) is not int
                or not 0 <= minimum <= maximum <= len(select["option"])
                or not minimum <= len(result) <= maximum
                or len(result) > contract.max_indexes
                or any(type(index) is not int or index < 0 or index >= len(select["option"]) for index in result)
                or len(set(result)) != len(result)
            ):
                raise RpcProtocolError("rpc_response_invalid")
    elif (
        response["official_card_ids"] is not None
        or response["current_option_indexes"] is not None
        or not _error_code(response["error_code"])
    ):
        raise RpcProtocolError("rpc_response_invalid")
    if len(_canonical_rpc_json_bytes(response)) > contract.response_max_bytes:
        raise RpcProtocolError("rpc_response_too_large")
    return response


def build_request(
    *,
    session_token: str,
    match_id: str,
    seat: int,
    ordinal: int,
    observation: Mapping[str, Any],
    contract: RpcContract,
) -> dict[str, Any]:
    unsigned = {
        "document_type": "competition_agent_request_v1",
        "schema_version": 1,
        "session_token": session_token,
        "match_id": match_id,
        "seat": seat,
        "ordinal": ordinal,
        "observation": _plain_json_tree(observation),
    }
    value = {**unsigned, "request_sha256": _sha256(_canonical_rpc_json_bytes(unsigned))}
    return validate_request(value, contract)


def _plain_json_tree(value: Any) -> Any:
    """Copy mapping subclasses (such as Kaggle Struct) into strict JSON types."""

    if isinstance(value, Mapping):
        if not all(type(key) is str for key in value):
            raise RpcProtocolError("rpc_request_invalid")
        return {key: _plain_json_tree(item) for key, item in value.items()}
    if type(value) is list:
        return [_plain_json_tree(item) for item in value]
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise RpcProtocolError("rpc_request_invalid")


def validate_request(value: Any, contract: RpcContract) -> dict[str, Any]:
    if type(value) is not dict or set(value) != REQUEST_KEYS:
        raise RpcProtocolError("rpc_request_invalid")
    request = dict(value)
    if (
        request["document_type"] != "competition_agent_request_v1"
        or request["schema_version"] != 1
        or not _token(request["session_token"])
        or not _identifier(request["match_id"])
        or request["seat"] not in (0, 1)
        or type(request["ordinal"]) is not int
        or request["ordinal"] < 0
        or type(request["observation"]) is not dict
        or not _sha256_value(request["request_sha256"])
    ):
        raise RpcProtocolError("rpc_request_invalid")
    unsigned = dict(request)
    supplied = unsigned.pop("request_sha256")
    try:
        canonical = _canonical_rpc_json_bytes(unsigned)
    except (TypeError, ValueError) as error:
        raise RpcProtocolError("rpc_request_invalid") from error
    if len(canonical) > contract.request_max_bytes:
        raise RpcProtocolError("rpc_request_too_large")
    if _sha256(canonical) != supplied:
        raise RpcProtocolError("rpc_request_hash_invalid")
    return request


def build_response(
    request: Mapping[str, Any],
    *,
    indexes: list[int] | None,
    error_code: str | None,
    contract: RpcContract,
) -> dict[str, Any]:
    value = {
        "document_type": "competition_agent_response_v1",
        "schema_version": 1,
        "session_token": request["session_token"],
        "match_id": request["match_id"],
        "seat": request["seat"],
        "ordinal": request["ordinal"],
        "request_sha256": request["request_sha256"],
        "ok": error_code is None,
        "indexes": indexes if error_code is None else None,
        "error_code": error_code,
    }
    validate_response(
        value,
        contract,
        session_token=request["session_token"],
        match_id=request["match_id"],
        seat=request["seat"],
        ordinal=request["ordinal"],
        request_sha256=request["request_sha256"],
    )
    return value


def validate_response(
    value: Any,
    contract: RpcContract,
    *,
    session_token: str,
    match_id: str,
    seat: int,
    ordinal: int,
    request_sha256: str,
) -> dict[str, Any]:
    if type(value) is not dict or set(value) != RESPONSE_KEYS:
        raise RpcProtocolError("rpc_response_invalid")
    response = dict(value)
    if (
        response["document_type"] != "competition_agent_response_v1"
        or response["schema_version"] != 1
        or response["session_token"] != session_token
        or response["match_id"] != match_id
        or response["seat"] != seat
        or response["ordinal"] != ordinal
        or response["request_sha256"] != request_sha256
    ):
        raise RpcProtocolError("rpc_response_binding_mismatch")
    if type(response["ok"]) is not bool:
        raise RpcProtocolError("rpc_response_invalid")
    if response["ok"]:
        indexes = response["indexes"]
        if (
            response["error_code"] is not None
            or type(indexes) is not list
            or len(indexes) > contract.max_indexes
            or not all(
                type(index) is int
                and contract.minimum_index <= index <= contract.maximum_index
                for index in indexes
            )
        ):
            raise RpcProtocolError("rpc_response_invalid")
    elif (
        response["indexes"] is not None
        or not _error_code(response["error_code"])
    ):
        raise RpcProtocolError("rpc_response_invalid")
    canonical = _canonical_rpc_json_bytes(response)
    if len(canonical) > contract.response_max_bytes:
        raise RpcProtocolError("rpc_response_too_large")
    return response


class FileRpcAgentClient:
    def __init__(
        self,
        *,
        channel: str | Path,
        session_token: str,
        match_id: str,
        seat: int,
        decision_timeout_seconds: int,
        contract: RpcContract,
        wire_generation: int = 1,
    ) -> None:
        self.channel = _safe_channel(channel)
        if (
            not _token(session_token)
            or not _identifier(match_id)
            or seat not in (0, 1)
            or type(decision_timeout_seconds) is not int
            or wire_generation not in (1, 2)
            or not contract.minimum_decision_seconds
            <= decision_timeout_seconds
            <= contract.maximum_decision_seconds
        ):
            raise RpcProtocolError("rpc_client_configuration_invalid")
        self.session_token = session_token
        self.match_id = match_id
        self.seat = seat
        self.timeout = decision_timeout_seconds
        self.contract = contract
        self.wire_generation = wire_generation
        self.ordinal = 0
        self.closed = False
        self.last_error_code: str | None = None
        self._call_lock = threading.Lock()

    def wait_ready(self, *, timeout_seconds: int) -> None:
        ready_path = self.channel / "ready.json"
        _wait_for(ready_path, timeout_seconds, self.contract.poll_interval_seconds)
        ready = _read_json(ready_path, self.contract.response_max_bytes)
        if (
            type(ready) is not dict
            or set(ready) != READY_KEYS
            or ready["document_type"]
            != f"competition_agent_ready_v{self.wire_generation}"
            or ready["schema_version"] != self.wire_generation
            or ready["session_token"] != self.session_token
            or ready["match_id"] != self.match_id
            or ready["seat"] != self.seat
            or ready["contract_sha256"] != self.contract.canonical_sha256
        ):
            raise RpcProtocolError("rpc_ready_binding_mismatch")

    def __call__(self, observation: dict[str, Any]) -> list[int]:
        if self.closed:
            raise RpcProtocolError("rpc_client_closed")
        if not self._call_lock.acquire(blocking=False):
            raise RpcProtocolError("rpc_concurrent_call")
        try:
            return self._call_once(observation)
        finally:
            self._call_lock.release()

    def _call_once(self, observation: dict[str, Any]) -> list[int]:
        ordinal = self.ordinal
        try:
            request_builder = (
                build_request_v2 if self.wire_generation == 2 else build_request
            )
            request = request_builder(
                session_token=self.session_token,
                match_id=self.match_id,
                seat=self.seat,
                ordinal=ordinal,
                observation=observation,
                contract=self.contract,
            )
        except RpcProtocolError as error:
            code = str(error)
            self.last_error_code = code if _error_code(code) else "rpc_request_invalid"
            raise
        except BaseException as error:
            self.last_error_code = _request_failure_code(error)
            raise
        request_path = self.channel / f"request-{ordinal:08d}.json"
        response_path = self.channel / f"response-{ordinal:08d}.json"
        _atomic_write(request_path, request, self.contract.request_max_bytes)
        try:
            _wait_for(response_path, self.timeout, self.contract.poll_interval_seconds)
            raw_response = _read_json(response_path, self.contract.response_max_bytes)
            if self.wire_generation == 2:
                response = validate_response_v2(
                    raw_response,
                    self.contract,
                    request=request,
                )
            else:
                response = validate_response(
                    raw_response,
                    self.contract,
                    session_token=self.session_token,
                    match_id=self.match_id,
                    seat=self.seat,
                    ordinal=ordinal,
                    request_sha256=request["request_sha256"],
                )
            if not response["ok"]:
                self.last_error_code = response["error_code"]
                raise RpcProtocolError(f"rpc_agent_error:{response['error_code']}")
            self.last_error_code = None
            self.ordinal += 1
            if self.wire_generation == 2:
                field = (
                    "official_card_ids"
                    if response["response_domain"] == "official_card_ids"
                    else "current_option_indexes"
                )
                return list(response[field])
            return list(response["indexes"])
        finally:
            request_path.unlink(missing_ok=True)
            response_path.unlink(missing_ok=True)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        _atomic_write(
            self.channel / "stop.json",
            {
                "document_type": f"competition_agent_stop_v{self.wire_generation}",
                "schema_version": self.wire_generation,
                "session_token": self.session_token,
                "match_id": self.match_id,
                "seat": self.seat,
            },
            self.contract.response_max_bytes,
        )


class FileRpcAgentServer:
    def __init__(
        self,
        *,
        channel: str | Path,
        session_token: str,
        match_id: str,
        seat: int,
        policy: Callable[[dict[str, Any]], list[int]],
        contract: RpcContract,
        wire_generation: int = 1,
    ) -> None:
        self.channel = _safe_channel(channel)
        if (
            not _token(session_token)
            or not _identifier(match_id)
            or seat not in (0, 1)
            or wire_generation not in (1, 2)
        ):
            raise RpcProtocolError("rpc_server_configuration_invalid")
        self.session_token = session_token
        self.match_id = match_id
        self.seat = seat
        self.policy = policy
        self.contract = contract
        self.wire_generation = wire_generation

    def serve(self) -> None:
        _atomic_write(
            self.channel / "ready.json",
            {
                "document_type": f"competition_agent_ready_v{self.wire_generation}",
                "schema_version": self.wire_generation,
                "session_token": self.session_token,
                "match_id": self.match_id,
                "seat": self.seat,
                "contract_sha256": self.contract.canonical_sha256,
            },
            self.contract.response_max_bytes,
        )
        ordinal = 0
        stop = self.channel / "stop.json"
        try:
            while True:
                if stop.exists():
                    self._validate_stop(_read_json(stop, self.contract.response_max_bytes))
                    return
                request_path = self.channel / f"request-{ordinal:08d}.json"
                if not request_path.exists():
                    time.sleep(self.contract.poll_interval_seconds)
                    continue
                raw_request = _read_json(
                    request_path, self.contract.request_max_bytes
                )
                request = (
                    validate_request_v2(raw_request, self.contract)
                    if self.wire_generation == 2
                    else validate_request(raw_request, self.contract)
                )
                if (
                    request["session_token"] != self.session_token
                    or request["match_id"] != self.match_id
                    or request["seat"] != self.seat
                    or request["ordinal"] != ordinal
                ):
                    raise RpcProtocolError("rpc_request_binding_mismatch")
                try:
                    result = self.policy(dict(request["observation"]))
                except BaseException:
                    response = self._response(
                        request, result=None, error_code="agent_exception"
                    )
                else:
                    try:
                        response = self._response(
                            request, result=result, error_code=None
                        )
                    except (RpcProtocolError, TypeError, ValueError):
                        response = self._response(
                            request,
                            result=None,
                            error_code="invalid_agent_output",
                        )
                _atomic_write(
                    self.channel / f"response-{ordinal:08d}.json",
                    response,
                    self.contract.response_max_bytes,
                )
                ordinal += 1
        finally:
            (self.channel / "ready.json").unlink(missing_ok=True)
            stop.unlink(missing_ok=True)

    def _response(
        self,
        request: Mapping[str, Any],
        *,
        result: list[int] | None,
        error_code: str | None,
    ) -> dict[str, Any]:
        if self.wire_generation == 2:
            return build_response_v2(
                request,
                result=result,
                error_code=error_code,
                contract=self.contract,
            )
        return build_response(
            request,
            indexes=result,
            error_code=error_code,
            contract=self.contract,
        )

    def _validate_stop(self, value: Any) -> None:
        if (
            type(value) is not dict
            or set(value)
            != {"document_type", "schema_version", "session_token", "match_id", "seat"}
            or value["document_type"]
            != f"competition_agent_stop_v{self.wire_generation}"
            or value["schema_version"] != self.wire_generation
            or value["session_token"] != self.session_token
            or value["match_id"] != self.match_id
            or value["seat"] != self.seat
        ):
            raise RpcProtocolError("rpc_stop_binding_mismatch")


def _safe_channel(value: str | Path) -> Path:
    requested = Path(value)
    requested.mkdir(parents=True, exist_ok=True)
    if requested.is_symlink():
        raise RpcProtocolError("rpc_channel_unsafe")
    channel = requested.resolve()
    if not channel.is_dir():
        raise RpcProtocolError("rpc_channel_unsafe")
    return channel


def _atomic_write(path: Path, value: Mapping[str, Any], maximum: int) -> None:
    body = _canonical_rpc_json_bytes(value)
    if len(body) > maximum:
        raise RpcProtocolError("rpc_message_too_large")
    temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path, maximum: int) -> Any:
    try:
        if path.is_symlink() or path.stat().st_size > maximum:
            raise RpcProtocolError("rpc_message_invalid")
        return load_json_bytes_strict(path.read_bytes())
    except OSError as error:
        raise RpcProtocolError("rpc_message_invalid") from error


def _wait_for(path: Path, timeout_seconds: int, poll_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not path.is_file():
        if time.monotonic() >= deadline:
            raise RpcProtocolError("rpc_timeout")
        time.sleep(poll_seconds)


def _sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest().upper()


def _canonical_rpc_json_bytes(value: Any) -> bytes:
    """Deterministic RPC encoding; unlike artifact JSON, CABT raw contains floats."""

    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise RpcProtocolError("rpc_message_invalid") from error


def _sha256_value(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(
        character in "0123456789ABCDEF" for character in value
    )


def _identifier(value: object) -> bool:
    return type(value) is str and 1 <= len(value) <= 128 and all(
        character.isascii() and (character.isalnum() or character in "-._:")
        for character in value
    )


def _token(value: object) -> bool:
    return type(value) is str and 32 <= len(value) <= 256 and all(
        character.isascii() and (character.isalnum() or character in "-._~")
        for character in value
    )


def _error_code(value: object) -> bool:
    return type(value) is str and 1 <= len(value) <= 80 and all(
        character.isascii() and (character.isalnum() or character in "-._:")
        for character in value
    )


def _request_failure_code(error: BaseException) -> str:
    labels = {
        AttributeError: "attribute_error",
        MemoryError: "memory_error",
        OSError: "os_error",
        OverflowError: "overflow_error",
        RecursionError: "recursion_error",
        TypeError: "type_error",
        ValueError: "value_error",
    }
    for kind, label in labels.items():
        if isinstance(error, kind):
            return "rpc_request_" + label
    return "rpc_request_failure"


__all__ = [
    "FileRpcAgentClient",
    "FileRpcAgentServer",
    "RpcContract",
    "RpcProtocolError",
    "build_request",
    "build_request_v2",
    "build_response",
    "build_response_v2",
    "load_rpc_contract",
    "load_rpc_contract_v2",
    "validate_request",
    "validate_request_v2",
    "validate_response",
    "validate_response_v2",
]
