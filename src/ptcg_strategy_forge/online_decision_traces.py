"""Download authenticated acting-seat traces through the documented HTTP wire."""
import json
from pathlib import Path
import re
import tempfile

from .control_client import ControlError
from .control_workflow import release_detail
from .native_trace import NativeTraceStore
from .replays import atomic_json, identity


def pull_decision_traces(workspace, client, release_id, *, max_games=20, max_bytes=256*1024**2):
    if type(max_games) is not int or not 1 <= max_games <= 60 or type(max_bytes) is not int or max_bytes < 1:
        raise ValueError('decision_trace_budget_invalid')
    capabilities=client.request('/v1/developer/capabilities').get('capabilities',{})
    if capabilities.get('decision_trace') is not True:
        raise ValueError('service_decision_trace_unsupported')
    release=release_detail(client,release_id)
    profile=client.request('/v1/ladder/releases/'+release_id+'/profile?game_limit='+str(max_games))
    games=profile.get('recent_games')
    if type(games) is not list or len(games)>max_games:
        raise ValueError('decision_trace_match_list_invalid')
    root=Path(workspace)
    native=NativeTraceStore(root)
    receipts=root/'data/online-decision-traces';receipts.mkdir(parents=True,exist_ok=True)
    items=[]; total=0; seen=set()
    for game in games:
        job=game.get('job_id');seat=game.get('subject_seat')
        if type(job) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',job) or seat not in (0,1):
            raise ValueError('decision_trace_match_identity_invalid')
        if job in seen: continue
        seen.add(job)
        remaining=min(32*1024**2,max_bytes-total)
        if remaining<=0:
            items.append({'job_id':job,'status':'skipped','reason':'download_budget_exhausted'});continue
        try:
            value=client.request('/v1/developer/matches/'+job+'/decision-trace',max_bytes=remaining)
        except ControlError as error:
            if error.status not in (404,410): raise
            items.append({'job_id':job,'status':'unavailable','reason':str(error)});continue
        raw=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        total+=len(raw)
        if total>max_bytes: raise ValueError('decision_trace_download_budget_exceeded')
        if (value.get('document_type')!='forge_ladder_decision_trace_v1' or value.get('schema_version')!=1 or
            value.get('release_id')!=release_id or value.get('archive_sha256')!=release.get('archive_sha256') or
            value.get('job_id')!=job or value.get('seat')!=seat or
            value.get('manifest',{}).get('native_match_id')!=job+'-seat-'+str(seat) or
            type(value.get('records')) is not list):
            raise ValueError('decision_trace_download_binding_invalid')
        with tempfile.TemporaryDirectory(dir=receipts,prefix='.verify-') as temporary:
            source=Path(temporary)/value['manifest']['native_match_id'];source.mkdir()
            atomic_json(source/'developer_decision_trace_manifest.json',value['manifest'])
            (source/'developer_decisions.jsonl').write_text(''.join(json.dumps(record,ensure_ascii=False,
                separators=(',',':'),allow_nan=False)+'\n' for record in value['records']),encoding='utf-8')
            imported=native.import_trace(source)
        inspection=native.inspect(imported['trace_id'])
        receipt={'document_type':'forge_online_decision_trace_receipt_v1','origin':client.origin,
            'release_id':release_id,'archive_sha256':value['archive_sha256'],'job_id':job,'seat':seat,
            'trace_id':imported['trace_id'],'authenticated_download':True,'bc_eligible':False}
        atomic_json(receipts/(identity(receipt)+'.json'),receipt)
        items.append({'job_id':job,'status':'verified','trace_id':imported['trace_id'],
            'decision_count':inspection['decision_count'],
            'engine_commit_witness_count':inspection['engine_commit_witness_count']})
    result={'document_type':'forge_decision_trace_pull_v1','status':'completed','release_id':release_id,
        'downloaded':sum(row['status']=='verified' for row in items),'bytes':total,'items':items,'bc_eligible':False}
    atomic_json(receipts/'latest-pull.json',result)
    return result
