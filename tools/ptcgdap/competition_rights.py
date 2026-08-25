from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Mapping

from scripts.ai.ptcgdap.source_lock import canonical_json_v1_bytes, load_json_bytes_strict


class RightsMode(StrEnum):
    EXPLICIT_AUTHORIZED = "explicit_authorized"
    USER_SUPPLIED_PRIVATE = "user_supplied_private"
    CLEAN_ROOM = "clean_room"


_FORBIDDEN_COMPONENTS = frozenset(
    {
        "cg.dll",
        "en_card_data.csv",
        "competition_files.sha256.json",
        "licenseRef-ptcg-abc-competition-use-only".casefold(),
    }
)
_FORBIDDEN_SEQUENCES = (
    ("official_data", "kaggle_bundle"),
    ("ptcg_engine", "ptcgprogram 22"),
)
_PRIVATE_ONLY_CAPABILITIES = frozenset({"read_private_bundle"})
_FORBIDDEN_PRIVATE_CAPABILITIES = frozenset(
    {
        "cache_private_bundle",
        "copy_private_bundle",
        "upload_private_bundle",
        "redistribute_private_bundle",
        "public_service",
    }
)


@dataclass(frozen=True, slots=True)
class RightsDecision:
    accepted: bool
    mode: RightsMode
    error_code: str
    operation: str
    claims: dict[str, bool]
    findings: list[str]


class CompetitionRightsGate:
    """Fail-closed W0 gate.  It records authorization; it never manufactures it."""

    def __init__(
        self,
        *,
        mode: RightsMode,
        private_bundle_root: Path | None = None,
        authorization_receipt: Mapping[str, Any] | None = None,
    ) -> None:
        self.mode = mode
        self.private_bundle_root = private_bundle_root
        self.authorization_receipt = (
            dict(authorization_receipt) if authorization_receipt is not None else None
        )

    @classmethod
    def clean_room_default(cls) -> CompetitionRightsGate:
        return cls(mode=RightsMode.CLEAN_ROOM)

    @classmethod
    def user_supplied_private(cls, root: str | Path) -> CompetitionRightsGate:
        requested = Path(root)
        if requested.is_symlink() or not requested.is_dir():
            raise ValueError("rights_private_bundle_invalid")
        return cls(mode=RightsMode.USER_SUPPLIED_PRIVATE, private_bundle_root=requested.resolve())

    @classmethod
    def explicit_authorized(
        cls, receipt: Mapping[str, Any] | str | Path | None
    ) -> CompetitionRightsGate:
        if receipt is None:
            raise ValueError("rights_authorization_receipt_required")
        if isinstance(receipt, (str, Path)):
            path = Path(receipt)
            if path.is_symlink() or not path.is_file():
                raise ValueError("rights_authorization_receipt_invalid")
            try:
                loaded = load_json_bytes_strict(path.read_bytes())
            except (OSError, UnicodeError, ValueError) as error:
                raise ValueError("rights_authorization_receipt_invalid") from error
        else:
            loaded = dict(receipt)
        _validate_authorization_receipt(loaded)
        return cls(mode=RightsMode.EXPLICIT_AUTHORIZED, authorization_receipt=loaded)

    def authorize(
        self,
        *,
        operation: str,
        requested_capabilities: Iterable[str] = (),
    ) -> RightsDecision:
        capabilities = frozenset(requested_capabilities)
        if not _identifier(operation) or any(not _identifier(item) for item in capabilities):
            return self._decision(False, "rights_request_invalid", operation, [])
        if self.mode is RightsMode.CLEAN_ROOM:
            forbidden = capabilities & (
                _FORBIDDEN_PRIVATE_CAPABILITIES | {"official_engine_hosting", "official_runtime_redistribution"}
            )
            return self._decision(
                not forbidden,
                "" if not forbidden else "rights_operation_not_authorized",
                operation,
                sorted(forbidden),
            )
        if self.mode is RightsMode.USER_SUPPLIED_PRIVATE:
            forbidden = capabilities - _PRIVATE_ONLY_CAPABILITIES
            return self._decision(
                not forbidden and operation == "local_private_oracle",
                "" if not forbidden and operation == "local_private_oracle" else "rights_operation_not_authorized",
                operation,
                sorted(forbidden),
            )
        assert self.authorization_receipt is not None
        allowed = frozenset(self.authorization_receipt["allowed_capabilities"])
        forbidden = capabilities - allowed
        return self._decision(
            not forbidden,
            "" if not forbidden else "rights_operation_not_authorized",
            operation,
            sorted(forbidden),
        )

    def audit_distribution(self, root: str | Path) -> RightsDecision:
        requested = Path(root)
        if requested.is_symlink() or not requested.is_dir():
            return self._decision(False, "rights_distribution_root_invalid", "distribution_audit", [])
        findings: list[str] = []
        for path in requested.rglob("*"):
            if path.is_symlink():
                findings.append(path.relative_to(requested).as_posix())
                continue
            if not path.is_file():
                continue
            relative = path.relative_to(requested).as_posix()
            folded = tuple(part.casefold() for part in Path(relative).parts)
            if any(_contains_sequence(folded, sequence) for sequence in _FORBIDDEN_SEQUENCES):
                findings.append(relative)
            elif any(part in _FORBIDDEN_COMPONENTS for part in folded):
                findings.append(relative)
        findings = sorted(set(findings), key=lambda value: value.encode("utf-8"))
        accepted = not findings or self.mode is RightsMode.EXPLICIT_AUTHORIZED
        return self._decision(
            accepted,
            "" if accepted else "rights_forbidden_inventory",
            "distribution_audit",
            findings,
        )

    def _decision(
        self, accepted: bool, error_code: str, operation: str, findings: list[str]
    ) -> RightsDecision:
        authorized = self.mode is RightsMode.EXPLICIT_AUTHORIZED
        claims = {
            "official_engine_hosting": authorized,
            "official_runtime_redistribution": authorized,
            "public_service": self.mode is not RightsMode.USER_SUPPLIED_PRIVATE,
            "read_private_bundle": self.mode is RightsMode.USER_SUPPLIED_PRIVATE,
            "cache_private_bundle": False,
            "upload_private_bundle": False,
            "clean_room_distribution": self.mode is RightsMode.CLEAN_ROOM,
        }
        return RightsDecision(accepted, self.mode, error_code, operation, claims, list(findings))


def _validate_authorization_receipt(value: Any) -> None:
    required = {
        "document_type",
        "schema_version",
        "authorization_id",
        "authority",
        "scope",
        "allowed_capabilities",
        "evidence_sha256",
    }
    if (
        type(value) is not dict
        or set(value) != required
        or value["document_type"] != "ptcgdap_competition_rights_authorization_v1"
        or value["schema_version"] != 1
        or not all(_identifier(value[field]) for field in ("authorization_id", "authority", "scope"))
        or type(value["allowed_capabilities"]) is not list
        or not value["allowed_capabilities"]
        or any(not _identifier(item) for item in value["allowed_capabilities"])
        or len(set(value["allowed_capabilities"])) != len(value["allowed_capabilities"])
        or not _sha256_value(value["evidence_sha256"])
    ):
        raise ValueError("rights_authorization_receipt_invalid")
    # Canonicalization also proves that no float or unsupported host object entered the receipt.
    canonical_json_v1_bytes(value)


def _contains_sequence(parts: tuple[str, ...], sequence: tuple[str, ...]) -> bool:
    width = len(sequence)
    return any(parts[index : index + width] == sequence for index in range(len(parts) - width + 1))


def _identifier(value: object) -> bool:
    return type(value) is str and 1 <= len(value) <= 128 and all(
        character.isascii() and (character.isalnum() or character in "-._:")
        for character in value
    )


def _sha256_value(value: object) -> bool:
    return type(value) is str and len(value) == 64 and all(
        character in "0123456789ABCDEF" for character in value
    )


__all__ = ["CompetitionRightsGate", "RightsDecision", "RightsMode"]
