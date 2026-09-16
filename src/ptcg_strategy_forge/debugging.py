"""Current-window debugging through existing Host simulation owners."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import os

from .replays import atomic_json, identity
from .scenarios import is_competitive_scenario, simulate_competitive_public_frame


def counterfactual_scenario(source, pointer, value, expected):
    prefixes = ("/frame/public_state/", "/raw_observation/current/", "/local_uid_bindings/")
    if (type(pointer) is not str or not pointer.startswith(prefixes) or type(value) not in {str, int, bool, type(None)}
            or type(expected) is not list or any(type(i) is not int for i in expected) or len(set(expected)) != len(expected)):
        raise ValueError("scenario_counterfactual_field_invalid")
    result = copy.deepcopy(source)
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]
    container = result
    try:
        for part in parts[:-1]:
            container = container[int(part)] if type(container) is list else container[part]
        key = int(parts[-1]) if type(container) is list else parts[-1]
        original = container[key]
        if type(original) in {dict, list} or original == value:
            raise ValueError("scenario_counterfactual_field_invalid")
        container[key] = value
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ValueError("scenario_counterfactual_field_invalid") from error
    result["expected_selected_indexes"] = list(expected)
    result["scenario_id"] = "counterfactual-" + identity(result)[:24]
    if is_competitive_scenario(result):
        from scripts.ai.ptcgdap.cabt_tree_hash import public_observation_hash
        frame = result["frame"]
        frame["source"]["public_observation_hash"] = public_observation_hash({key: frame[key] for key in ("schema_version", "sequence", "seat", "prompt_kind", "public_state")})
        frame["source"]["window_id"] = public_observation_hash({"public_observation_hash": frame["source"]["public_observation_hash"],
            "select_semantics": frame["select_semantics"], "options": frame["options"]})
    else:
        result["prompt"]["prompt_id"] = result["scenario_id"]
        result["prompt"]["prompt_generation"] += 1
    return result


def reorder_scenario(source, permutation):
    result = copy.deepcopy(source)
    competitive = is_competitive_scenario(result)
    options = result["frame"]["options"] if competitive else result["raw_observation"]["select"]["option"]
    if (type(permutation) is not list or any(type(i) is not int for i in permutation)
            or sorted(permutation) != list(range(len(options)))):
        raise ValueError("scenario_permutation_invalid")
    mapping = {old: new for new, old in enumerate(permutation)}
    reordered = [options[i] for i in permutation]
    if competitive:
        from scripts.ai.ptcgdap.cabt_tree_hash import public_observation_hash
        for index, option in enumerate(reordered):
            option["index"] = index
        frame = result["frame"]
        frame["options"] = reordered
        frame["source"]["window_id"] = public_observation_hash({
            "public_observation_hash": frame["source"]["public_observation_hash"],
            "select_semantics": frame["select_semantics"], "options": reordered})
        authority = result["base_authority"]
    else:
        # Raw option.index is a card/slot location, NOT the current option position.
        result["raw_observation"]["select"]["option"] = reordered
        for binding in result["local_uid_bindings"]["options"]:
            binding["index"] = mapping[binding["index"]]
        result["local_uid_bindings"]["options"].sort(key=lambda row: row["index"])
        authority = result["prompt"]
    for key in ("mandatory_indexes", "terminal_indexes", "base_vetoed_indexes"):
        authority[key] = [mapping[i] for i in authority[key]]
    tiers = authority["base_hard_tiers"]
    if isinstance(tiers, list):
        for row in tiers:
            row["index"] = mapping[row["index"]]
        tiers.sort(key=lambda row: row["index"])
    elif isinstance(tiers, dict):
        authority["base_hard_tiers"] = {str(mapping[int(i)]): value for i, value in tiers.items()}
    result["expected_selected_indexes"] = [mapping[i] for i in result["expected_selected_indexes"]]
    result["scenario_id"] = "reorder-" + identity(result)[:24]
    if not competitive:
        result["prompt"]["prompt_id"] = result["scenario_id"]
        result["prompt"]["prompt_generation"] += 1
    return result


class DebuggingService:
    def __init__(self, workspace):
        self.root = Path(workspace).resolve()

    def _source(self, scenario):
        path = (self.root / scenario).resolve()
        if not path.is_relative_to(self.root) or not path.is_file() or path.is_symlink():
            raise ValueError("workspace_scenario_invalid")
        return path

    def test(self, *, cases=None, changed=False):
        from .application import run_suite
        from tools.ptcgdap.author_strategy_developer import build_development_package
        suite = json.loads((self.root / "scenario-suite.json").read_bytes())
        known = {row["id"] for row in suite["cases"]}
        if cases is not None and (not cases or not set(cases) <= known):
            raise ValueError("scenario_case_unknown")
        selected = [row for row in suite["cases"] if cases is None or row["id"] in cases]
        cache_path = self.root / ".forge/quick-tests.json"
        cache = json.loads(cache_path.read_bytes()) if cache_path.exists() else {}
        code_hash = identity({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob("*.py")})
        with tempfile.TemporaryDirectory(prefix="forge-quick-") as temp:
            artifact = Path(temp) / "current.ptcgai"
            build_development_package(self.root / "package", artifact)
            package_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
            keys = {case["id"]: identity([case, hashlib.sha256(self._source(case["path"]).read_bytes()).hexdigest(), package_hash, code_hash]) for case in selected}
            pending = [case for case in selected if not changed or cache.get(case["id"]) != keys[case["id"]]]
            results = []
            if pending:
                fd, name = tempfile.mkstemp(dir=self.root, prefix=".forge-quick-", suffix=".json")
                os.close(fd)
                temporary = Path(name)
                try:
                    atomic_json(temporary, {**suite, "cases": pending})
                    report = run_suite(artifact, temporary)
                    results = report["cases"]
                    for row in results:
                        if row["accepted"]:
                            cache[row["id"]] = keys[row["id"]]
                        else:
                            cache.pop(row["id"], None)
                finally:
                    temporary.unlink(missing_ok=True)
        atomic_json(cache_path, cache)
        return {"document_type": "forge_quick_test_report_v1", "status": "passed" if all(r["accepted"] for r in results) else "failed",
                "executed_count": len(pending), "cached_count": len(selected)-len(pending), "cases": results,
                "package_sha256": package_hash, "full_acceptance": False, "engine_execution": False}

    def watch(self, *, cases=None, interval=.5, stop=None):
        from .lineage import source_identity
        if interval < .1:
            raise ValueError("scenario_watch_interval_invalid")
        previous = None
        while stop is None or not stop.is_set():
            current = source_identity(self.root)
            if current != previous:
                time.sleep(interval)
                stable = source_identity(self.root)
                if current != stable:
                    continue
                yield self.test(cases=cases, changed=True)
                previous = current
            if stop is not None:
                stop.wait(interval)
            else:
                time.sleep(interval)

    def compare(self, scenario, baseline):
        candidate = self.explain(scenario)
        before = self.explain(scenario, artifact=baseline)
        return {"document_type": "forge_window_comparison_v1", "status": "completed", "candidate": candidate,
                "baseline": before, "selection_changed": candidate["simulation"]["decision"]["selected_indexes"] != before["simulation"]["decision"]["selected_indexes"],
                "engine_execution": False}

    def explain(self, scenario, *, artifact=None):
        from .application import simulate_public_window, assert_public_report
        from tools.ptcgdap.author_strategy_developer import build_development_package
        path = self._source(scenario)
        document = json.loads(path.read_bytes())
        simulate = simulate_competitive_public_frame if is_competitive_scenario(document) else simulate_public_window
        with tempfile.TemporaryDirectory(prefix="forge-explain-") as temp:
            package = Path(artifact) if artifact is not None else Path(temp) / "current.ptcgai"
            if artifact is None:
                build_development_package(self.root / "package", package)
            from scripts.ai.ptcgdap.author_strategy_package import AuthorStrategyPackageLoader
            adapter = json.loads(AuthorStrategyPackageLoader().load_path(package).payload_bytes("policy/adapter.json"))
            from .diagnostics import capture_predicates
            with capture_predicates(adapter) as evaluations:
                simulation = simulate(package, path)
            package_sha = hashlib.sha256(package.read_bytes()).hexdigest()
        matched = {row["rule_id"] for row in simulation["adapter"]["matched_rules"]}
        pointers = [{"rule_id": rule.get("rule_id"), "source": "package/policy/adapter.json",
                     "json_pointer": f"/rules/{i}", "matched": rule.get("rule_id") in matched}
                    for i, rule in enumerate(adapter.get("rules", []))]
        report = {"document_type": "forge_decision_explanation_v1", "status": simulation["status"],
                  "scenario_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "package_sha256": package_sha,
                  "simulation": simulation, "rule_sources": pointers,
                  "predicate_evaluations": evaluations,
                  "source_binding": "package_archive",
                  "claims": {"public_only": True, "engine_execution": False, "production_authority": False}}
        assert_public_report(report)
        return report

    def generate(self, scenario, *, permutation):
        source = json.loads(self._source(scenario).read_bytes())
        document = reorder_scenario(source, permutation)
        target = self.root / "scenarios/generated" / (document["scenario_id"] + ".json")
        if target.exists() and json.loads(target.read_bytes()) != document:
            raise ValueError("scenario_generation_conflict")
        if not target.exists():
            atomic_json(target, document)
        return {"document_type": "forge_generated_scenario_v1", "status": "completed",
                "path": target.relative_to(self.root).as_posix(), "scenario_id": document["scenario_id"],
                "suite_registered": False, "engine_execution": False}

    def counterfactual(self, scenario, *, pointer, value, expected):
        source_path = self._source(scenario)
        source = json.loads(source_path.read_bytes())
        document = counterfactual_scenario(source, pointer, value, expected)
        target = self.root / "scenarios/generated" / (document["scenario_id"] + ".json")
        if target.exists() and json.loads(target.read_bytes()) != document:
            raise ValueError("scenario_generation_conflict")
        if not target.exists():
            atomic_json(target, document)
        return {"document_type": "forge_counterfactual_pair_v1", "status": "completed",
                "source": source_path.relative_to(self.root).as_posix(), "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                "path": target.relative_to(self.root).as_posix(), "changed_field": pointer,
                "teacher_selected_indexes": source["expected_selected_indexes"], "developer_expected_indexes": expected,
                "validated": False, "suite_registered": False, "engine_execution": False}

    def from_replay(self, trace_id, decision_id, *, base_authority):
        from .native_trace import NativeTraceStore
        from .scenarios import BASE_AUTHORITY_KEYS, COMPETITIVE_SCENARIO_DOCUMENT_TYPE
        if type(base_authority) is not dict or set(base_authority) != BASE_AUTHORITY_KEYS:
            raise ValueError("scenario_base_authority_required")
        trace = NativeTraceStore(self.root).load(trace_id)
        choices = [d for d in trace["decisions"] if d["decision_id"] == decision_id]
        if len(choices) != 1:
            raise ValueError("scenario_decision_not_found")
        decision = choices[0]
        scenario_id = "trace-" + identity([trace_id, decision_id, base_authority])[:24]
        document = {"document_type": COMPETITIVE_SCENARIO_DOCUMENT_TYPE, "schema_version": 2,
                    "scenario_id": scenario_id, "frame": decision["frame"], "base_authority": base_authority,
                    "expected_selected_indexes": decision["host"]["accepted_indexes"]}
        target = self.root / "scenarios/imported" / (scenario_id + ".json")
        if target.exists() and json.loads(target.read_bytes()) != document:
            raise ValueError("scenario_generation_conflict")
        if not target.exists():
            atomic_json(target, document)
        return {"document_type": "forge_imported_scenario_v1", "status": "completed",
                "path": target.relative_to(self.root).as_posix(), "trace_id": trace_id, "decision_id": decision_id,
                "base_authority_source": "explicit_developer_simulation_input", "suite_registered": False,
                "engine_execution": False}
