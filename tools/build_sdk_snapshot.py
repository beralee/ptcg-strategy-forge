from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
PREFIXES = (
    Path("scripts/ai/ptcgdap"),
    Path("contracts/ptcgdap"),
    Path("data/ptcgdap"),
    Path("data/bundled_user"),
    Path("tools/ptcgdap"),
)

# Explicitly reviewed files whose PtcgDAP locations differ from the standalone
# Forge layout.  Refresh copies bytes only from these allow-listed sources.
REFRESH_FILES = {
	Path("scripts/ai/ptcgdap/author_strategy_package.py"): Path(
		"scripts/ai/ptcgdap/author_strategy_package.py"
	),
	Path("scripts/ai/ptcgdap/competitive_policy_v2.py"): Path(
		"scripts/ai/ptcgdap/competitive_policy_v2.py"
	),
	Path("scripts/ai/ptcgdap/public_damage_planning.py"): Path(
		"scripts/ai/ptcgdap/public_damage_planning.py"
	),
    Path("scripts/ai/ptcgdap/cabt_selection.py"): Path(
        "scripts/ai/ptcgdap/cabt_selection.py"
    ),
    Path("scripts/ai/ptcgdap/cabt_a1_contract.py"): Path(
        "scripts/ai/ptcgdap/cabt_a1_contract.py"
    ),
    Path("scripts/ai/ptcgdap/cabt_window_v2.py"): Path(
        "scripts/ai/ptcgdap/cabt_window_v2.py"
    ),
    Path("scripts/ai/ptcgdap/cabt_match_lifecycle_v2.py"): Path(
        "scripts/ai/ptcgdap/cabt_match_lifecycle_v2.py"
    ),
    Path("scripts/ai/ptcgdap/cabt_time_search_v2.py"): Path(
        "scripts/ai/ptcgdap/cabt_time_search_v2.py"
    ),
    Path("scripts/ai/ptcgdap/a1_scope.py"): Path(
        "scripts/ai/ptcgdap/a1_scope.py"
    ),
    Path("scripts/ai/ptcgdap/ucis.py"): Path(
        "scripts/ai/ptcgdap/ucis.py"
    ),
    Path("scripts/ai/ptcgdap/ucis_sdk.py"): Path(
        "scripts/ai/ptcgdap/ucis_sdk.py"
    ),
    Path("services/ptcgdap_replay/competition_bundle.py"): Path(
        "tools/ptcgdap/competition_bundle.py"
    ),
    Path("services/ptcgdap_replay/competition_rights.py"): Path(
        "tools/ptcgdap/competition_rights.py"
    ),
    Path("services/ptcgdap_replay/competition_agent_rpc.py"): Path(
        "tools/ptcgdap/competition_agent_rpc.py"
    ),
	Path("contracts/ptcgdap/competition_bundle_v2.schema.json"): Path(
        "contracts/ptcgdap/competition_bundle_v2.schema.json"
	),
	Path("contracts/ptcgdap/competitive_policy_v2.schema.json"): Path(
		"contracts/ptcgdap/competitive_policy_v2.schema.json"
	),
	Path("contracts/ptcgdap/competitive_policy_v2_profile.json"): Path(
		"contracts/ptcgdap/competitive_policy_v2_profile.json"
	),
	Path("contracts/ptcgdap/competitive_policy_v2_conformance_vectors.json"): Path(
		"contracts/ptcgdap/competitive_policy_v2_conformance_vectors.json"
	),
	Path("contracts/ptcgdap/competitive_policy_v2_bundle.json"): Path(
		"contracts/ptcgdap/competitive_policy_v2_bundle.json"
	),
	Path("contracts/ptcgdap/public_damage_capability_registry_v1.json"): Path(
		"contracts/ptcgdap/public_damage_capability_registry_v1.json"
	),
	Path("data/bundled_user/cards/CSV10C_208.json"): Path(
		"data/bundled_user/cards/CSV10C_208.json"
	),
	Path("data/bundled_user/cards/CSV1C_126.json"): Path(
		"data/bundled_user/cards/CSV1C_126.json"
	),
	Path("data/bundled_user/decks/646600.json"): Path(
		"data/bundled_user/decks/646600.json"
	),
	Path("tools/ptcgdap/build_competitive_policy_v2_contract.py"): Path(
		"tools/ptcgdap/build_competitive_policy_v2_contract.py"
	),
	Path("tools/ptcgdap/build_public_damage_capability_registry.py"): Path(
		"tools/ptcgdap/build_public_damage_capability_registry.py"
	),
    Path("contracts/ptcgdap/competition_bundle_v2_conformance_vectors.json"): Path(
        "contracts/ptcgdap/competition_bundle_v2_conformance_vectors.json"
    ),
    Path("contracts/ptcgdap/competition_bundle_v2_profile.json"): Path(
        "contracts/ptcgdap/competition_bundle_v2_profile.json"
    ),
    Path("contracts/ptcgdap/competition_runtime_lock_v2.json"): Path(
        "contracts/ptcgdap/competition_runtime_lock_v2.json"
    ),
    Path("contracts/ptcgdap/competition_agent_rpc_contract_v2.json"): Path(
        "contracts/ptcgdap/competition_agent_rpc_contract_v2.json"
    ),
    Path("contracts/ptcgdap/competition_release_qualification_profile_v2.json"): Path(
        "contracts/ptcgdap/competition_release_qualification_profile_v2.json"
    ),
    Path("contracts/ptcgdap/cabt_interface_census_v2.json"): Path(
        "contracts/ptcgdap/cabt_interface_census_v2.json"
    ),
    Path("contracts/ptcgdap/cabt_prompt_coverage_matrix_v2.json"): Path(
        "contracts/ptcgdap/cabt_prompt_coverage_matrix_v2.json"
    ),
    Path("contracts/ptcgdap/cabt_lifecycle_coverage_matrix_v2.json"): Path(
        "contracts/ptcgdap/cabt_lifecycle_coverage_matrix_v2.json"
    ),
    Path("contracts/ptcgdap/cabt_time_profile_v2.json"): Path(
        "contracts/ptcgdap/cabt_time_profile_v2.json"
    ),
    Path("contracts/ptcgdap/cabt_search_capability_v2.json"): Path(
        "contracts/ptcgdap/cabt_search_capability_v2.json"
    ),
    Path("contracts/ptcgdap/cabt_fault_taxonomy_v2.json"): Path(
        "contracts/ptcgdap/cabt_fault_taxonomy_v2.json"
    ),
    Path("evidence/ptcgdap/a1/scope_v2.json"): Path(
        "contracts/ptcgdap/cabt_a1_scope_report_v2.json"
    ),
    Path("data/ptcgdap/a3/five_deck_scope_v2.json"): Path(
        "data/ptcgdap/a3/five_deck_scope_v2.json"
    ),
    Path("contracts/ptcgdap/ucis_registry_v1.json"): Path(
        "contracts/ptcgdap/ucis_registry_v1.json"
    ),
    Path("contracts/ptcgdap/ucis_card_effect_step_schema_v1.json"): Path(
        "contracts/ptcgdap/ucis_card_effect_step_schema_v1.json"
    ),
    Path("contracts/ptcgdap/ucis_compiled_interaction_step_schema_v1.json"): Path(
        "contracts/ptcgdap/ucis_compiled_interaction_step_schema_v1.json"
    ),
    Path("contracts/ptcgdap/ucis_card_effect_spec_schema_v1.json"): Path(
        "contracts/ptcgdap/ucis_card_effect_spec_schema_v1.json"
    ),
    Path("contracts/ptcgdap/ucis_interaction_program_schema_v1.json"): Path(
        "contracts/ptcgdap/ucis_interaction_program_schema_v1.json"
    ),
    Path("contracts/ptcgdap/ucis_card_catalog_v1.json"): Path(
        "contracts/ptcgdap/ucis_card_catalog_v1.json"
    ),
    Path("contracts/ptcgdap/ucis_legacy_inventory_v1.json"): Path(
        "contracts/ptcgdap/ucis_legacy_inventory_v1.json"
    ),
    Path("contracts/ptcgdap/ucis_coverage_ledger_v1.json"): Path(
        "contracts/ptcgdap/ucis_coverage_ledger_v1.json"
    ),
    Path("contracts/ptcgdap/ucis_conformance_vectors_v1.json"): Path(
        "contracts/ptcgdap/ucis_conformance_vectors_v1.json"
    ),
    Path("contracts/ptcgdap/ucis_bundle_v1.json"): Path(
        "contracts/ptcgdap/ucis_bundle_v1.json"
    ),
    Path("contracts/ptcgdap/ucis_runtime_attestation_v1.json"): Path(
        "contracts/ptcgdap/ucis_runtime_attestation_v1.json"
    ),
    Path("evidence/ptcgdap/ucis/ucis_performance_qualification_v1.json"): Path(
        "contracts/ptcgdap/ucis_performance_qualification_v1.json"
    ),
    Path("evidence/ptcgdap/ucis/ucis_catalog_qualification_v1.json"): Path(
        "contracts/ptcgdap/ucis_catalog_qualification_v1.json"
    ),
    Path("evidence/ptcgdap/a3/corresponding_card_whole_battle_input_index_v1.json"): Path(
        "contracts/ptcgdap/corresponding_card_whole_battle_input_index_v1.json"
    ),
}


def refresh(source_root: Path) -> None:
    source = source_root.resolve(strict=True)
    if source.is_symlink() or not (source / "AGENTS.md").is_file():
        raise SystemExit("reviewed PtcgDAP source invalid")
    for source_relative, target_relative in REFRESH_FILES.items():
        source_path = source / source_relative
        target_path = ROOT / target_relative
        if not source_path.is_file() or source_path.is_symlink():
            raise SystemExit(f"reviewed source missing: {source_relative.as_posix()}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def build() -> dict[str, object]:
    files: list[dict[str, object]] = []
    for prefix in PREFIXES:
        for path in sorted((ROOT / prefix).rglob("*"), key=lambda value: value.as_posix().encode("utf-8")):
            if not path.is_file() or path.is_symlink() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(ROOT).as_posix()
            files.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha(path)})
    return {
        "document_type": "ptcg_strategy_forge_sdk_snapshot_v1",
        "schema_version": 1,
        "source": {
            "repository": "https://github.com/beralee/PtcgDeckAgent",
            "worktree": "PtcgDAP",
            "base_commit": "3534d22b28d2895d5de5bf12cd35836d686714aa",
            "captured_on": "2026-08-23",
            "scope": "author-strategy development, validation, simulation, and publishing",
            "note": "Snapshot captured from the reviewed local PtcgDAP worktree; each distributed byte is pinned below.",
        },
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--refresh-from", type=Path)
    args = parser.parse_args()
    if args.refresh_from is not None:
        if args.check:
            raise SystemExit("--check and --refresh-from are mutually exclusive")
        refresh(args.refresh_from)
    path = ROOT / "vendor/ptcgdap-sdk-manifest.json"
    expected = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.check:
        if not path.is_file() or path.read_bytes() != expected:
            raise SystemExit("sdk snapshot manifest drift")
        print("sdk snapshot manifest ok")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(expected)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
