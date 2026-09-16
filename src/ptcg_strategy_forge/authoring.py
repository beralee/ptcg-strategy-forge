"""Named author helpers that compile to the pinned restricted adapter IR."""
import copy
import hashlib
import json

from .resources import resource_root
from .ucis_runtime import SELECT_TYPE_NAMES, CONTEXT_NAMES, OPTION_TYPE_NAMES, REGISTRY_SHA256


def _enum(value, names):
    if value is None:
        return None
    if type(value) is not str or value not in names:
        raise ValueError("authoring_enum_unknown")
    return names.index(value)


def macro_rule(rule_id, *, stage, option_type=None, select_type=None, context=None,
               option_uid=None, hand_uid=None, active_uid=None, player_index=None, priority=0):
    return {"rule_id": rule_id, "operator": "macro_proposal", "goal_stage": stage,
            "priority": priority, "reason_code": "public_macro_proposal",
            "predicate": {"option_type_raw": _enum(option_type, OPTION_TYPE_NAMES),
                          "select_type_raw": _enum(select_type, SELECT_TYPE_NAMES),
                          "select_context_raw": _enum(context, CONTEXT_NAMES),
                          "option_card_id": option_uid, "acting_hand_card_id": hand_uid,
                          "acting_active_card_id": active_uid, "option_player_index": player_index}}


def compile_rules(adapter_id, rules, *, allowed_uids, deck_sha256):
    from scripts.ai.ptcgdap.public_deck_adapter import PublicDeckAdapterCompiler
    document = {"schema_version": 1, "adapter_id": adapter_id, "adapter_version": 1, "rules": copy.deepcopy(rules)}
    result = PublicDeckAdapterCompiler.compile_local_uid(document, allowed_card_uids=set(allowed_uids),
                                                        deck_manifest_sha256=deck_sha256)
    if not result.accepted:
        raise ValueError(result.error_code)
    return document


def authoring_metadata():
    from scripts.ai.ptcgdap.public_deck_adapter import GOAL_STAGES
    uid = {"type": ["string", "null"]}
    schema = {"type": "object", "additionalProperties": False, "required": ["rule_id", "stage"],
              "properties": {"rule_id": {"type": "string"}, "stage": {"enum": sorted(GOAL_STAGES)},
                 "option_type": {"enum": [None, *OPTION_TYPE_NAMES]}, "select_type": {"enum": [None, *SELECT_TYPE_NAMES]},
                 "context": {"enum": [None, *CONTEXT_NAMES]}, "option_uid": uid, "hand_uid": uid, "active_uid": uid,
                 "player_index": {"enum": [None, 0, 1]}, "priority": {"type": "integer"}}}
    return {"document_type": "forge_authoring_metadata_v1", "status": "available",
            "macro_rule_schema": schema,
            "registry_sha256": REGISTRY_SHA256,
            "select_types": list(SELECT_TYPE_NAMES), "contexts": list(CONTEXT_NAMES), "option_types": list(OPTION_TYPE_NAMES),
            "output_ir": "restricted_adapter_v1", "arbitrary_policy_graph": False, "runtime_authority": "base_graph"}


def compile_named_rules(document, *, allowed_uids, deck_sha256):
    import jsonschema
    if (type(document) is not dict or set(document) != {"document_type", "schema_version", "adapter_id", "rules"}
            or document["document_type"] != "forge_named_rules_v1" or document["schema_version"] != 1
            or type(document["rules"]) is not list):
        raise ValueError("authoring_document_invalid")
    rules = []
    for rule in document["rules"]:
        try:
            jsonschema.validate(rule, authoring_metadata()["macro_rule_schema"])
            rules.append(macro_rule(**rule))
        except (jsonschema.ValidationError, TypeError) as error:
            raise ValueError("authoring_rule_invalid") from error
    return compile_rules(document["adapter_id"], rules, allowed_uids=allowed_uids, deck_sha256=deck_sha256)


def workspace_rules(workspace, *, source=None, output=None):
    from pathlib import Path
    from .replays import atomic_json
    deck_bytes = (workspace.root / "package/deck/deck_manifest.json").read_bytes()
    allowed = {row["local_card_uid"] for row in json.loads(deck_bytes)["cards"]}
    deck_sha = hashlib.sha256(deck_bytes).hexdigest().upper()
    if source is not None:
        source = Path(source)
        if source.stat().st_size > 1024**2 or output is None:
            raise ValueError("authoring_input_invalid")
        document = compile_named_rules(json.loads(source.read_bytes()), allowed_uids=allowed, deck_sha256=deck_sha)
        target = Path(output)
        if target.exists():
            raise ValueError("authoring_output_exists")
        atomic_json(target, document)
        return {"document_type": "forge_rules_compile_v1", "status": "passed", "path": str(target), "runtime_authority": "base_graph"}
    document = json.loads((workspace.root / "package/policy/adapter.json").read_bytes())
    if document.get("schema_version") == 2:
        from scripts.ai.ptcgdap.competitive_policy_v2 import CompetitivePolicyV2Compiler
        result = CompetitivePolicyV2Compiler.compile_local_uid(document, allowed_card_uids=allowed)
        if not result.accepted:
            raise ValueError(result.error_code)
    else:
        from scripts.ai.ptcgdap.public_deck_adapter import PublicDeckAdapterCompiler
        result = PublicDeckAdapterCompiler.compile_local_uid(document, allowed_card_uids=allowed, deck_manifest_sha256=deck_sha)
        if not result.accepted:
            raise ValueError(result.error_code)
    return {"document_type": "forge_rules_lint_v1", "status": "passed", "full_acceptance": False}


def search_cards(query, *, exact=False):
    root = resource_root()
    catalog = json.loads((root / "data/developer/supported-cards-v1.json").read_bytes())
    rows = []
    for entry in catalog["cards"]:
        if exact and entry["card_uid"] != query:
            continue
        path = root / entry["source_path"]
        card = {}
        if path.is_file():
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest().upper() != entry["source_sha256"]:
                raise ValueError("card_source_hash_mismatch")
            card = json.loads(raw)
        names = {key: card[key] for key in ("name", "name_en", "name_zh") if type(card.get(key)) is str and card[key]}
        if exact or any(query.casefold() in text.casefold() for text in [entry["card_uid"], *names.values()]):
            rows.append({**entry, "display_names": names, "display_names_authoritative_identity": False})
    return {"document_type": "forge_cards_query_v1", "status": "completed", "cards": rows,
            "identity_domain": catalog["identity_domain"], "official_card_id_equivalence": False}
