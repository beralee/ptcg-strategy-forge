"""Reproducible, serial real-trace BC experiment for a frozen local strategy."""
from pathlib import Path
import argparse, collections, hashlib, json, os, sys, subprocess
from contextlib import nullcontext
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from ptcg_strategy_forge.neural_dataset import qualify_teacher_record,admit_unique_teacher_example,teacher_seats
from ptcg_strategy_forge.run_safety import atomic_json,monitor_process,child_environment,child_creation_flags

def read(path): return json.loads(Path(path).read_bytes())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()
def write(path,value): atomic_json(path,value)

def dataset(args):
    from tools.local_engine_bench import verify_trace,engine_frame_validator,audit_game
    run=Path(args.run); runtime=Path(args.runtime); output=Path(args.output)
    if output.exists(): raise ValueError('dataset_output_exists')
    report=read(run/'report.json')
    if report.get('clean') is not True: raise ValueError('neural_dirty_teacher_run')
    entries=read(run/'runtime-files.json')
    projector=entries['scripts/ai/ptcgdap/host/godot/SemanticModelInput.gd']
    deck=read(Path(args.workspace)/'package/deck/deck_manifest.json')
    uids=[r['local_card_uid'] for r in deck['cards']]
    examples=[]; reasons=collections.Counter(); contexts=collections.Counter(); seen={}
    teacher=report['games'][0]['candidate_sha256']
    import zipfile
    teacher_path=Path(read(run/'config.json')['candidate']['path'])
    if sha(teacher_path)!=teacher:raise ValueError('neural_teacher_identity_mismatch')
    with zipfile.ZipFile(teacher_path) as archive:
        if hashlib.sha256(archive.read('deck/deck_manifest.json')).hexdigest().upper()!=sha(Path(args.workspace)/'package/deck/deck_manifest.json'):
            raise ValueError('neural_teacher_deck_mismatch')
    validator=engine_frame_validator(runtime)
    for game in report['games']:
        seats=teacher_seats(game,teacher)
        if audit_game(game,teacher,game['opponent_sha256']):
            raise ValueError('neural_teacher_identity_mismatch')
        path=run/game['trace_path']
        if not verify_trace(path,game,validator): raise ValueError('neural_trace_integrity_invalid')
        seed=int(game['seed']); split='train' if seed < args.validation_seed else 'validation'
        for line in path.open(encoding='utf-8'):
            payload=json.loads(json.loads(line)['payload'])
            if payload['seat']!=payload['decision']['frame']['seat']:raise ValueError('neural_seat_binding_invalid')
            if payload['seat'] not in seats:reasons['non_teacher_seat']+=1;continue
            example,reason=qualify_teacher_record(payload,allowed_uids=uids,projector_sha256=projector)
            reasons[reason]+=1
            if not example: continue
            identity=(seed,game['opponent_sha256'],example['seat'],example['window_id'])
            if not admit_unique_teacher_example(seen,identity,example): reasons['duplicate_seed_window']+=1; continue
            example.update(seed_group=seed,split=split,opponent_sha256=game['opponent_sha256'])
            contexts[split+':'+example['context']]+=1; examples.append(example)
    output.parent.mkdir(parents=True,exist_ok=True)
    result={'document_type':'forge_godot_bc_dataset_v1','teacher_archive_sha256':teacher,
        'runtime_sha256':report['runtime_sha256'],'trace_report_sha256':sha(run/'report.json'),
        'projector_sha256':projector,'deck_manifest_sha256':sha(Path(args.workspace)/'package/deck/deck_manifest.json'),
        'uid_vocabulary':sorted(uids),'split_by':'whole_related_seed_before_selection_or_augmentation',
        'validation_seed_minimum':args.validation_seed,'qualification_counts':dict(reasons),
        'context_counts':dict(contexts),'examples':examples,'production_ready':False}
    write(output,result); print(json.dumps({k:result[k] for k in ('qualification_counts','context_counts')}))

def train(args):
    from ptcg_strategy_forge.resources_gate import heavy_job
    output=Path(args.output).resolve()
    if output.exists(): raise ValueError('neural_run_exists')
    with heavy_job(output_path=output,wait_ms=getattr(args,'wait_ms',0)) as admission:
        output.mkdir(parents=True);write(output/'resource-admission.json',admission)
        env=child_environment();env['PTCG_FORGE_MONITORED_TRAIN']='1'
        with (output/'training.log').open('wb') as log:
            process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'train','--dataset',str(Path(args.dataset).resolve()),
                '--output',str(output),'--epochs',str(args.epochs),'--seed',str(args.seed),'--variant',args.variant,'--internal-worker'],
                stdout=log,stderr=subprocess.STDOUT,env=env,creationflags=child_creation_flags())
            code=monitor_process(process,output,storage_targets=admission['storage_targets'],max_seconds=1800)
        if code!=0 or not (output/'training-report.json').is_file():
            write(output/'resource-failure.json',dict(error_code='neural_worker_failed',exit_code=code,clean=False))
            raise ValueError('neural_worker_failed')
        report=read(output/'training-report.json')
        print(json.dumps({k:report[k] for k in ('best_epoch','parameter_count','validation_accuracy','actor_sha256')},ensure_ascii=False))


def train_worker(args):
    if os.environ.get('PTCG_FORGE_MONITORED_TRAIN')!='1':raise ValueError('neural_supervisor_required')
    from ptcg_strategy_forge.resources_gate import heavy_job,check_pressure
    from ptcg_strategy_forge.neural_actor import FeatureSpec,NeuralRanker,fit,export_onnx,positive_labels,listwise_loss_gradient
    from ptcg_strategy_forge.ptcgai_ort import import_onnx_to_ort,OrtActor
    from scripts.ai.ptcgdap.ptcgai_model_actor import PublicActorTensors
    import numpy as np
    output=Path(args.output)
    if not (output/'resource-admission.json').is_file():raise ValueError('neural_supervisor_required')
    with nullcontext():
        data=read(args.dataset); examples=data['examples']
        train_rows=[e for e in examples if e['split']=='train']; valid=[e for e in examples if e['split']=='validation']
        if set(e['seed_group'] for e in train_rows)&set(e['seed_group'] for e in valid): raise ValueError('neural_split_leakage')
        # Fixed categories derive from the published profile/sealed deck, not labels.
        from scripts.ai.ptcgdap.semantic_model_profile import KINDS,PROFILE_ID
        uid_codes=list(range(len(data['uid_vocabulary'])+1))
        fc={19:list(range(49)),20:list(range(11)),24:uid_codes,25:uid_codes,26:uid_codes,31:list(range(1,len(KINDS)+1))}
        oc={0:list(range(1,len(KINDS)+1)),1:uid_codes,2:uid_codes,3:uid_codes,4:list(range(12)),6:list(range(8)),7:list(range(8)),21:list(range(8)),22:list(range(10)),29:list(range(17))}
        fn={i:1.0 for i in range(128) if i not in fc}; on={i:1.0 for i in range(32) if i not in oc}
        for i in (0,3,4,5,6): fn[i]=0.05
        for i in (9,10): fn[i]=0.01
        for i in (13,14,29,30): fn[i]=0.1
        for i in range(32,128): fn[i]=0.25
        for i in (8,13): on[i]=0.01
        for i in (9,11,25,26): on[i]=0.1
        spec=FeatureSpec(128,32,fn,on,fc,oc,relations='public_resource_relations_v1' if args.variant=='relations' else '')
        model=NeuralRanker(spec,hidden=96,bottleneck=48,seed=args.seed)
        def progress(row):
            if row['epoch']%10==0: check_pressure(); print(json.dumps(row),flush=True)
        result=fit(model,train_rows,valid,epochs=args.epochs,learning_rate=0.001,batch_size=32,seed=args.seed,progress=progress,multi_positive=args.variant!='exact')
        model.save(output/'checkpoint.npz'); export_onnx(model,output/'actor.onnx')
        imported=import_onnx_to_ort(output/'actor.onnx',output/'actor.ort'); actor=OrtActor(output/'actor.ort',timeout_ms=25)
        # Check all held-out windows with full padded deployment shapes.
        parity=[]; context={};by_action={};shared_losses=[];semantic_correct=0;exact_correct=0
        for e in valid:
            n=len(e['options']); zeros=(0,)*32
            tensors=PublicActorTensors(PROFILE_ID,tuple(e['frame']),tuple(e['frame_presence']),tuple(map(tuple,e['options']))+(zeros,)*(1024-n),
                tuple(map(tuple,e['option_presence']))+(zeros,)*(1024-n),(1,)*n+(0,)*(1024-n),tuple(e['semantic_keys']),tuple(e['current_indexes']),{},1,1)
            scores,count,latency=actor.run(tensors)
            reference=(np.clip(model.scores(e),-100000,100000)*10000).astype(np.int32)
            delta=int(np.max(np.abs(np.array(scores[:n],np.int64)-reference)))
            if delta>2 or count!=[1] or any(s!=-2000000000 for s in scores[n:]): raise ValueError('neural_export_parity_failed')
            prediction=min(range(n),key=lambda i:(-scores[i],e['semantic_keys'][i],e['current_indexes'][i]))
            positives=positive_labels(e,n)
            shared_losses.append(listwise_loss_gradient(model.scores(e),positives)[0])
            exact=int(prediction==e['label']);equivalent=int(prediction in positives)
            exact_correct+=exact;semantic_correct+=equivalent
            kind=KINDS[e['options'][e['label']][0]-1]
            for group,key in ((context,e['context']),(by_action,kind)):
                row=group.setdefault(key,{'count':0,'correct':0,'equivalent_correct':0})
                row['count']+=1;row['correct']+=exact;row['equivalent_correct']+=equivalent
            parity.append({'max_integer_delta':delta,'latency_ms':latency})
        result.update(dataset_sha256=sha(args.dataset),training_examples=len(train_rows),validation_examples=len(valid),
            actor_sha256=sha(output/'actor.ort'),actor_bytes=(output/'actor.ort').stat().st_size,import_report=imported,
            context_validation=context,action_validation=by_action,shared_validation_nll=float(np.mean(shared_losses)),
            exact_validation_accuracy=exact_correct/len(valid),equivalent_validation_accuracy=semantic_correct/len(valid),
            variant=args.variant,relations=spec.relations,ort_parity=parity,seed=args.seed,epochs=args.epochs,production_ready=False)
        result['implementation_sha256']={str(p.relative_to(ROOT)):sha(p) for p in (
            Path(__file__),ROOT/'src/ptcg_strategy_forge/neural_actor.py',ROOT/'src/ptcg_strategy_forge/neural_relations.py',
            ROOT/'src/ptcg_strategy_forge/neural_dataset.py',ROOT/'src/ptcg_strategy_forge/ptcgai_ort.py',
            ROOT/'scripts/ai/ptcgdap/semantic_model_profile.py')}
        write(output/'training-report.json',result); print(json.dumps({k:v for k,v in result.items() if k not in ('history','ort_parity','import_report')}),flush=True)

def main():
    p=argparse.ArgumentParser(); s=p.add_subparsers(dest='command',required=True)
    d=s.add_parser('dataset'); d.add_argument('--run',required=True); d.add_argument('--runtime',required=True); d.add_argument('--workspace',required=True); d.add_argument('--validation-seed',type=int,required=True);d.add_argument('--output',required=True)
    t=s.add_parser('train');t.add_argument('--dataset',required=True);t.add_argument('--output',required=True);t.add_argument('--epochs',type=int,default=100);t.add_argument('--seed',type=int,default=260919)
    t.add_argument('--variant',choices=('exact','equivalent','relations'),default='exact')
    t.add_argument('--internal-worker',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args(); (dataset if args.command=='dataset' else train_worker if args.internal_worker else train)(args)

if __name__=='__main__': main()
