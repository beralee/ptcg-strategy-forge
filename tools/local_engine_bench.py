"""Serial, exact-artifact local Godot bench. Uses an isolated research runtime.

prepare --game GAME --runtime NEW_DIRECTORY
run --runtime DIRECTORY --godot EXE --plan PLAN --output NEW_DIRECTORY
compare --baseline REPORT --candidate REPORT
"""
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import types
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
from ptcg_strategy_forge.resources_gate import heavy_job, check_pressure
from ptcg_strategy_forge.run_safety import (atomic_json, monitor_process, child_environment,
    child_creation_flags, sample_job, validate_sample, append_telemetry)

COUNTERS = ("policy_errors", "invalid_outputs", "same_window_fallbacks", "classic_fallbacks",
            "engine_rejections", "external_process_attempts", "developer_trace_dropped_records")
GATE = "scripts/ai/ptcgdap/host/godot/AuthorStrategyWindowsDevelopmentGate.gd"


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, data):
    atomic_json(path, data)


def wilson(wins, n):
    if not n:
        return [0, 1]
    z = 1.95996398454
    p = wins / n
    c = (p + z*z/(2*n))/(1+z*z/n)
    r = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0,c-r), min(1,c+r)]


def audit_game(row, candidate_sha, opponent_sha):
    errors=[]
    if row.get("candidate_sha256") != candidate_sha or row.get("opponent_sha256") != opponent_sha:
        errors.append("bench_archive_mismatch")
    if row.get("terminal") is not True or row.get("winner_index") not in (0,1):
        errors.append("bench_nonterminal")
    if row.get("failure_code"):
        errors.append(row["failure_code"])
    if row.get("trace_verified") is not True:
        errors.append("bench_trace_invalid")
    for owner in ("candidate_audit", "opponent_audit"):
        a=row.get(owner,{})
        if type(a.get("policy_calls")) is not int or a["policy_calls"] <= 0 or a["policy_calls"] != a.get("policy_successes"):
            errors.append(owner+":policy_accounting")
        if type(a.get("engine_commits")) is not int or a["engine_commits"] <= 0:
            errors.append(owner+":engine_commits")
        for key in COUNTERS:
            if type(a.get(key)) is not int or a[key] != 0:
                errors.append(owner+":"+key)
        if row.get(owner.replace('_audit', '_requires_model')):
            if type(a.get('model_inference_successes')) is not int or a['model_inference_successes'] < 0:
                errors.append(owner+':model_accounting')
            if type(a.get('model_fallbacks')) is not int or a['model_fallbacks'] != 0:
                errors.append(owner+':model_fallbacks')
    return errors


def audit_model_activity(games):
    errors = []
    for owner in ('candidate', 'opponent'):
        required = [g for g in games if g.get(owner + '_requires_model')]
        if required and not any(type(g.get(owner + '_audit', {}).get('model_inference_successes')) is int
                                and g[owner + '_audit']['model_inference_successes'] > 0 for g in required):
            errors.append(owner + ':model_never_called')
    return errors


def compare_runs(baseline, candidate):
    if baseline.get("runtime_sha256") != candidate.get("runtime_sha256"):
        raise ValueError("bench_runtime_mismatch")
    def keyed(report):
        if report.get('clean') is not True or report.get('errors') or audit_model_activity(report['games']):
            raise ValueError('bench_dirty_run')
        result={}
        archives={row['candidate_sha256'] for row in report['games']}
        if len(archives)!=1:
            raise ValueError('bench_archive_mismatch')
        for row in report["games"]:
            if audit_game(row,row["candidate_sha256"],row["opponent_sha256"]):
                raise ValueError("bench_dirty_run")
            key=(row["opponent_sha256"],row["seed"],row["candidate_seat"])
            if key in result:
                raise ValueError("bench_pairing_mismatch")
            result[key]=row
        return result
    b,c=keyed(baseline),keyed(candidate)
    if not b or b.keys()!=c.keys():
        raise ValueError("bench_pairing_mismatch")
    improved=regressed=bwins=cwins=0
    matchups={}; seed_deltas={}
    for key in sorted(b):
        bw=b[key]["winner_index"]==b[key]["candidate_seat"]
        cw=c[key]["winner_index"]==c[key]["candidate_seat"]
        bwins+=bw;cwins+=cw;improved+=cw and not bw;regressed+=bw and not cw
        seed_deltas[key[1]]=seed_deltas.get(key[1],0)+int(cw)-int(bw)
        m=matchups.setdefault(b[key].get("opponent_id",key[0]),dict(games=0,baseline_wins=0,candidate_wins=0))
        m["games"]+=1;m["baseline_wins"]+=bw;m["candidate_wins"]+=cw
    for m in matchups.values():
        m["baseline_wilson_95"]=wilson(m["baseline_wins"],m["games"])
        m["candidate_wilson_95"]=wilson(m["candidate_wins"],m["games"])
    n=improved+regressed
    p=min(1,2*sum(math.comb(n,k) for k in range(min(improved,regressed)+1))/2**n) if n else 1
    # Keep all related opponents and both seats within a seed together.
    distribution={0:1}
    for delta in seed_deltas.values():
        next_distribution={}
        for total,count in distribution.items():
            for signed in (delta,-delta):next_distribution[total+signed]=next_distribution.get(total+signed,0)+count
        distribution=next_distribution
    observed=abs(sum(seed_deltas.values()))
    cluster_p=sum(count for total,count in distribution.items() if abs(total)>=observed)/2**len(seed_deltas)
    return dict(games=len(b),baseline_wins=bwins,candidate_wins=cwins,improved=improved,regressed=regressed,
                paired_exact_p=p,paired_exact_p_assumes_independent_rows=True,
                seed_cluster_count=len(seed_deltas),seed_cluster_sign_flip_p=cluster_p,
                matchups=matchups,scope="local_Godot_paired_games_not_ladder_rank")


def copy_model_runtime(game, runtime):
    """Freeze the native extension loader and binaries, including ORT itself."""
    game, runtime = Path(game), Path(runtime)
    loader = game / '.godot/extension_list.cfg'
    if loader.is_file():
        (runtime / '.godot').mkdir(parents=True, exist_ok=True)
        shutil.copyfile(loader, runtime / '.godot/extension_list.cfg')
    if (game / 'bin/ptcgai_ort').is_dir():
        shutil.copytree(game / 'bin/ptcgai_ort', runtime / 'bin/ptcgai_ort')


def copy_native_runtime(game, runtime):
    """Native loaders and source receipts must not drift with another task."""
    source=Path(game)/'native'
    if source.is_dir():
        shutil.copytree(source,Path(runtime)/'native',ignore=shutil.ignore_patterns('build','.git','__pycache__'))


def prepare(game, runtime):
    game=Path(game).resolve(); runtime=Path(runtime).resolve()
    if runtime.exists():
        raise ValueError("bench_runtime_exists")
    runtime.mkdir(parents=True)
    # Freeze all rule-bearing inputs. Only presentation assets remain shared.
    for name in ("scripts", "contracts", "data"):
        shutil.copytree(game/name,runtime/name,ignore=shutil.ignore_patterns("__pycache__"))
    copy_native_runtime(game,runtime)
    for name in ("assets","scenes","addons","web"):
        if (game/name).exists():
            subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",
                            f"New-Item -ItemType Junction -Path '{str(runtime/name).replace(chr(39),chr(39)*2)}' -Target '{str(game/name).replace(chr(39),chr(39)*2)}' | Out-Null"],check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
    (runtime/".godot").mkdir()
    copy_model_runtime(game, runtime)
    for name in ("global_script_class_cache.cfg","uid_cache.bin"):
        if (game/".godot"/name).exists():shutil.copy2(game/".godot"/name,runtime/".godot"/name)
    # No editor/import process is run; runtime may read the source project's imported art.
    if (game/".godot/imported").exists():
        subprocess.run(["powershell.exe","-NoProfile","-NonInteractive","-Command",
                        f"New-Item -ItemType Junction -Path '{runtime}/.godot/imported' -Target '{game}/.godot/imported' | Out-Null"],check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    project=(game/"project.godot").read_text(encoding="utf-8")
    user_name='ForgeLocalBench_'+digest(str(runtime).encode())[:16]
    user_path=Path(os.environ['APPDATA'])/user_name
    if user_path.exists():raise ValueError('bench_user_directory_exists')
    user_path.mkdir()
    for name in ('cards','decks'):
        shutil.copytree(runtime/'data/bundled_user'/name,user_path/name)
    project=re.sub(r'^config/(?:name|use_custom_user_dir|custom_user_dir)=.*\n','',project,flags=re.MULTILINE)
    project=project.replace('[application]','[application]\nconfig/name="ForgeLocalBench"\nconfig/use_custom_user_dir=true\nconfig/custom_user_dir="'+user_name+'"',1)
    (runtime/"project.godot").write_text(project,encoding="utf-8")
    shutil.copy2(ROOT/"tools/local_engine_bench.gd",runtime/"bench.gd")
    shutil.copy2(ROOT/"tools/research_io.gd",runtime/"research_io.gd")
    (runtime/"bench.tscn").write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://bench.gd" id="1"]\n[node name="LocalBench" type="Node"]\nscript = ExtResource("1")\n',encoding="utf-8")
    original=game/'development-gate-original.txt'
    if original.is_file():(runtime/GATE).write_bytes(original.read_bytes())
    (runtime/"development-gate-original.txt").write_bytes((runtime/GATE).read_bytes())
    source=read(game/'source.json') if original.is_file() else dict(game=str(game),game_commit=subprocess.check_output(["git","-C",str(game),"rev-parse","HEAD"],text=True).strip())
    write(runtime/"source.json",source)
    write(runtime/'sealed-inputs.json',dict(version=2,user_path=str(user_path),source=source))


def package_spec(path, expected=None):
    path=Path(path).resolve(); raw=path.read_bytes(); sha=digest(raw)
    if expected and sha != expected.upper():raise ValueError("bench_archive_mismatch")
    with zipfile.ZipFile(path) as z:
        m=json.loads(z.read("strategy_package.json"));d=json.loads(z.read("deck/deck_manifest.json"))
        sig=json.loads(z.read("signature.json"));a=json.loads(z.read("policy/adapter.json"))
    fixture=sig["key_id"]=="ptcgdap-as-wp1-test-fixture-ed25519-v1"
    spec=dict(path=str(path),sha256=sha,id=m["package_id"]+"-"+m["package_version"],requires_model=m['policy'].get('policy_mode')=='rules_with_model',
              mode="development_exact_fixture" if fixture else "control_distributed_player")
    gate=None
    if fixture and a.get('schema_version')==2:
        gate=dict(package_id=m["package_id"],package_version=m["package_version"],archive_sha256=sha,
                  install_source="built_in",source_deck_id=d["source_deck_id"],unique_printing_count=d["unique_card_count"],
                  adapter_rule_count=len(a["rules"]),strategy_id=m["package_id"]+".local-bench",
                  frame_profile_id="ptcgdap-competitive-public-frame-v2",runtime_kind="reviewed_competitive_policy_v2")
    return spec,gate


def native_runtime_files(root):
    # Build caches are neither loaded code nor runtime resources. The frozen
    # native/ORT binaries in bin/ are separately covered in full below.
    for directory, children, files in os.walk(root):
        children[:] = sorted(c for c in children if c not in {'build', '.git', '__pycache__'})
        for name in sorted(files):
            yield Path(directory)/name


def runtime_hash(runtime, godot):
    entries={}
    for top in ("scripts","contracts"):
        for path in sorted((runtime/top).rglob("*")):
            rel=path.relative_to(runtime).as_posix()
            if path.is_file() and rel != GATE and path.suffix in (".gd",".json",".py", ".gdextension"):
                entries[rel]=digest(path.read_bytes())
    for rel in ("bench.gd","project.godot","development-gate-original.txt"):
        entries[rel]=digest((runtime/rel).read_bytes())
    if (runtime/'research_io.gd').is_file():
        entries['research_io.gd']=digest((runtime/'research_io.gd').read_bytes())
    entries["godot_executable"]=digest(Path(godot).read_bytes())
    loader = runtime / '.godot/extension_list.cfg'
    if loader.is_file(): entries['.godot/extension_list.cfg'] = digest(loader.read_bytes())
    for path in sorted((runtime / 'bin/ptcgai_ort').rglob('*')):
        if path.is_file(): entries[path.relative_to(runtime).as_posix()] = digest(path.read_bytes())
    if (runtime/'sealed-inputs.json').is_file():
        seal=read(runtime/'sealed-inputs.json')
        binary=Path(godot)
        if binary.name.endswith('_console.exe'):
            binary=binary.with_name(binary.name.replace('_console.exe','.exe'))
        entries['godot_engine_binary']=digest(binary.read_bytes())
        entries['bench.tscn']=digest((runtime/'bench.tscn').read_bytes())
        for top in ('data','native'):
            paths = native_runtime_files(runtime/top) if top == 'native' else sorted((runtime/top).rglob('*'))
            for path in paths:
                if path.is_file():entries[path.relative_to(runtime).as_posix()]=digest(path.read_bytes())
        user=Path(seal['user_path'])
        for top in ('cards','decks','ai_decks'):
            for path in sorted((user/top).rglob('*.json')):
                entries['effective-user/'+path.relative_to(user).as_posix()]=digest(path.read_bytes())
    return digest(json.dumps(entries,sort_keys=True).encode()),entries


def stop_process_tree(process):
    """The Windows console launcher has a child engine; stop this owned tree."""
    if process.poll() is not None:return
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                       check=False,creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        process.terminate()
    process.wait(timeout=30)


def engine_frame_validator(runtime):
    # Validate diagnostics against the same reviewed engine snapshot that wrote them.
    # The bundled Forge native importer remains generation-locked and untouched.
    namespace="_forge_bench_engine_"+digest(str(runtime).encode())[:12]
    if namespace not in sys.modules:
        module=types.ModuleType(namespace)
        module.__path__=[str(Path(runtime)/"scripts/ai/ptcgdap")]
        sys.modules[namespace]=module
    return importlib.import_module(namespace+".competitive_policy_v2")._frame_error


def verify_window(record, validator):
    import copy
    from scripts.ai.ptcgdap.cabt_tree_hash import public_observation_hash
    f=copy.deepcopy(record["frame"]);host=record["host"];fingerprints=[]
    for option in f["options"]:
        fingerprint=option.pop("option_fingerprint")
        expected=public_observation_hash(dict(profile_id="ptcgdap-scoped-option-fingerprint-v1",public_observation_hash=f["source"]["public_observation_hash"],window_id=f["source"]["window_id"],index=option["index"],option=option))
        if fingerprint!=expected:raise ValueError("bench_option_binding_invalid")
        fingerprints.append(fingerprint)
    if validator(f):raise ValueError("bench_public_frame_invalid")
    observation={key:f[key] for key in ("schema_version","sequence","seat","prompt_kind","public_state")}
    if public_observation_hash(observation)!=f["source"]["public_observation_hash"]:raise ValueError("bench_observation_binding_invalid")
    window=dict(public_observation_hash=f["source"]["public_observation_hash"],select_semantics=f["select_semantics"],options=f["options"])
    if public_observation_hash(window)!=f["source"]["window_id"]:raise ValueError("bench_window_binding_invalid")
    indexes=host["accepted_indexes"]
    if (not isinstance(indexes,list) or any(type(i) is not int or not 0<=i<len(fingerprints) for i in indexes)
            or len(indexes)!=len(set(indexes)) or [fingerprints[i] for i in indexes]!=host["accepted_option_fingerprints"]):
        raise ValueError("bench_accepted_binding_invalid")
    return dict(decision_id=record["decision_id"],frame=f,host=host)


def npc_frame_error(frame, standard_validator):
    """Audit the NPC's anonymous prize-card wire shape without inventing UIDs.

    Only a validation copy gets ordinal NUMBER shapes. Hashes and accepted
    fingerprints continue to bind the untouched original frame in verify_window.
    """
    error=standard_validator(frame)
    if frame.get('prompt_kind')!='take_prize':return error
    error=error or 'npc_masked_prize_frame_invalid'
    import copy
    semantics=frame.get('select_semantics',{});options=frame.get('options',[])
    if (frame.get('prompt_kind')!='take_prize' or semantics.get('select_type_raw')!=1
            or semantics.get('select_context_raw')!=7 or not 1<=len(options)<=6
            or frame.get('public_state',{}).get('self',{}).get('prizes_remaining')!=len(options)):
        return error
    null_fields=('card_uid','card_serial','source_uid','source_serial','source_entity_serial',
                 'target_uid','target_serial','target_entity_serial','target_remaining_hp','target_prize_value',
                 'target_attached_energy_count','target_attached_energy_uids','target_minimum_attack_energy_count',
                 'target_attack_ready','target_energy_debt','projected_damage','attack_index','option_number',
                 'ability_index','energy_type_raw','energy_count','special_condition_type')
    for option in options:
        if (option.get('kind')!='take_prize' or option.get('option_type_raw')!=3
                or type(option.get('option_player_index')) is not int or option['option_player_index']!=frame['seat']
                or any(option.get(key) is not None for key in null_fields)
                or option.get('pending_assignment_count')!=0 or option.get('tags')!=[]
                or option.get('projected_knockout') is not False or option.get('requires_interaction') is not False):
            return error
    projected=copy.deepcopy(frame)
    for option in projected['options']:
        option['option_type_raw']=0;option['option_number']=option['index']
    return standard_validator(projected)


def verify_trace(path,row,validator=None):
    if digest(path.read_bytes())!=row["trace_file_sha256"]:return False
    if validator is None:
        from scripts.ai.ptcgdap.competitive_policy_v2 import _frame_error
        validator=_frame_error
    chain="0"*64;count=0;seat_counts={0:0,1:0};seen=set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            envelope=json.loads(line);payload=envelope["payload"]
            chain=digest((chain+"\n"+payload).encode())
            if chain != envelope["chain_sha256"]:return False
            record=json.loads(payload)
            decision=record["decision"]
            frame_validator=validator
            if row.get('opponent_id','').startswith('builtin-v18-') and record['seat']!=row['candidate_seat']:
                if decision.get('policy',{}).get('selection_source')!='platform_npc_rule_public_v1':return False
                frame_validator=lambda frame:npc_frame_error(frame,validator)
            verified=verify_window(decision,frame_validator)
            if record["seat"]!=verified["frame"]["seat"] or (record["seat"],verified["decision_id"]) in seen:return False
            host=verified["host"]
            if host.get("status")!="accepted" or host.get("fallback_used") or host.get("error_code"):return False
            seen.add((record["seat"],verified["decision_id"]));seat_counts[record["seat"]]+=1
            count+=1
    seat=row["candidate_seat"]
    return (count==row["trace_count"] and count>0 and chain==row["trace_root_sha256"]
            and seat_counts[seat]==row["candidate_audit"]["policy_calls"]
            and seat_counts[1-seat]==row["opponent_audit"]["policy_calls"])


def run(runtime,godot,plan_path,output,*,wait_ms=0):
    target=Path(output)
    existed=target.exists()
    try:
        return _run(runtime,godot,plan_path,output,wait_ms=wait_ms)
    except BaseException as error:
        if not existed and target.is_dir():
            code=('bench_report_invalid' if isinstance(error,json.JSONDecodeError) else
                  str(error) if isinstance(error,ValueError) else 'bench_interrupted_or_failed')
            try:write(target/'failed-run.json',dict(clean=False,error_code=code,exception_type=type(error).__name__))
            except (OSError,ValueError):pass
        raise


def build_match_schedule(runtime,plan):
    candidate,gate=package_spec(plan['candidate'],plan.get('candidate_sha256'))
    # Only a private runtime copy gets an exact hash fixture declaration; product gates remain intact.
    original=(runtime/"development-gate-original.txt").read_text(encoding="utf-8")
    gates={gate['archive_sha256']:gate} if gate else {}
    games=[]
    for entry in plan["opponents"]:
        if "path" in entry:
            opponent,opponent_gate=package_spec(entry["path"],entry["sha256"])
            if opponent_gate:gates[opponent_gate['archive_sha256']]=opponent_gate
        else:
            path=runtime/"scripts/ai/v18_cpg/profiles/generated_semantic_manifests"/(str(entry["npc"])+".json")
            opponent=dict(npc=str(entry["npc"]),id="builtin-v18-"+str(entry["npc"]),sha256=digest(path.read_bytes()))
        for seed in plan["seeds"]:
            for seat in (0,1):games.append(dict(seed=seed,seat=seat,opponent=opponent))
    if gates:
        if original.count('const CANDIDATES := [')!=1:raise ValueError('bench_development_gate_shape')
        original=original.replace('const CANDIDATES := [','const CANDIDATES := [\n'+',\n'.join(json.dumps(g) for _,g in sorted(gates.items()))+',',1)
    return candidate,games,original


def _run(runtime,godot,plan_path,output,*,wait_ms=0):
    runtime=Path(runtime).resolve();output=Path(output).resolve();godot=Path(godot).resolve()
    if output.exists():raise ValueError("bench_output_exists")
    plan=read(plan_path);candidate,games,original=build_match_schedule(runtime,plan)
    with heavy_job(workers=1, output_path=output, wait_ms=wait_ms) as resource:
        (runtime/GATE).write_text(original,encoding="utf-8")
        output.mkdir(parents=True)
        identity,entries=runtime_hash(runtime,godot)
        config=dict(candidate=candidate,games=games,output=str(output),max_steps=plan.get("max_steps",1200))
        write(output/"config.json",config);write(output/"runtime-files.json",entries)
        write(output/"resource-admission.json",resource)
        with (output/"godot.log").open("wb") as log:
            process=subprocess.Popen([str(godot),"--headless","--path",str(runtime),"res://bench.tscn","--",str(output/"config.json")],stdout=log,stderr=subprocess.STDOUT,
                                     creationflags=child_creation_flags(),env=child_environment())
            code=monitor_process(process,output,storage_targets=resource['storage_targets'],
                                 max_seconds=plan.get('max_seconds',min(5400,max(300,len(games)*180))),
                                 output_limit_bytes=plan.get('max_output_bytes',2*1024**3),stop=stop_process_tree)
        if not (output/"engine-summary.json").exists():raise ValueError("bench_engine_no_report")
        write(output/'execution-receipt.json',dict(engine_exit_code=code,runtime_sha256=identity,planned_games=len(games),candidate_sha256=candidate['sha256']))
        report=read(output/"engine-summary.json");errors=[]
        if len(report["games"])!=len(games):errors.append("bench_game_count")
        for row,spec in zip(report["games"],games):
            sample=sample_job(root_pid=os.getpid(),output=output,storage_targets=resource['storage_targets'])
            append_telemetry(output/'resource-telemetry.jsonl',dict(phase='trace_verification',**sample))
            validate_sample(sample,output_limit_bytes=plan.get('max_output_bytes',2*1024**3))
            row["trace_verified"]=verify_trace(output/row["trace_path"],row,engine_frame_validator(runtime)) if "trace_path" in row else False
            row["errors"]=audit_game(row,candidate["sha256"],spec["opponent"]["sha256"])
            if (row["seed"],row["candidate_seat"])!=(spec["seed"],spec["seat"]):row["errors"].append("bench_schedule_mismatch")
            errors.extend(row["errors"])
        errors.extend(audit_model_activity(report['games']))
        if runtime_hash(runtime,godot)[0]!=identity:errors.append("bench_runtime_changed")
        report.update(runtime_sha256=identity,admission_sha256=digest((runtime/GATE).read_bytes()),
                      errors=errors,clean=not errors and code==0,scope="local_Godot_engine_only",production_ready=False)
        write(output/"report.json",report)
        print(json.dumps(dict(clean=report["clean"],games=len(report["games"]),wins=sum(r.get("winner_index")==r["candidate_seat"] for r in report["games"]),errors=errors)))
        if not report["clean"]:raise ValueError("bench_dirty_run")


def main():
    parser=argparse.ArgumentParser(description=__doc__);subs=parser.add_subparsers(dest="command",required=True)
    p=subs.add_parser("prepare");p.add_argument("--game",required=True);p.add_argument("--runtime",required=True)
    p=subs.add_parser("run");p.add_argument("--runtime",required=True);p.add_argument("--godot",required=True);p.add_argument("--plan",required=True);p.add_argument("--output",required=True)
    p=subs.add_parser("compare");p.add_argument("--baseline",required=True);p.add_argument("--candidate",required=True)
    args=parser.parse_args()
    if args.command=="prepare":prepare(args.game,args.runtime)
    elif args.command=="run":run(args.runtime,args.godot,args.plan,args.output)
    else:print(json.dumps(compare_runs(read(args.baseline),read(args.candidate)),ensure_ascii=False,indent=2))


if __name__=="__main__":main()
