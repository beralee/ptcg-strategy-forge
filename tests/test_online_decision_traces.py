import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ptcg_strategy_forge.online_decision_traces import pull_decision_traces
from ptcg_strategy_forge.control_client import ControlError
from scripts.ai.ptcgdap.cabt_tree_hash import jcs_canonical_json_bytes


def trace():
    envelope={'document_type':'developer_decision_trace_record_v1','schema_version':1,
        'native_match_id':'job-seat-0','record_index':0,'previous_record_sha256':None,
        'payload':{'document_type':'owner_step_witness_v1','decision_ids':[],
                   'engine_commit_delta':0,'engine_rejection_delta':0}}
    sha=hashlib.sha256(b'PTCGDAP_REPLAY_DIAGNOSTIC\0ptcgdap_developer_decision_record_canonical_json_v1\0'+jcs_canonical_json_bytes(envelope)).hexdigest().upper()
    return {'document_type':'forge_ladder_decision_trace_v1','schema_version':1,'job_id':'job','seat':0,
        'release_id':'release-a','archive_sha256':'A'*64,'records':[{**envelope,'record_sha256':sha}],
        'manifest':{'document_type':'developer_decision_trace_manifest_v1','schema_version':1,
            'native_match_id':'job-seat-0','complete':True,'record_count':1,'decision_count':0,'owner_step_count':1,
            'chain_root_sha256':sha,'dropped_record_count':0,'private_replay_used':False,
            'visibility':'acting_policy_public_view_allow_list_v1'}}


class Client:
    origin='https://example.test'
    def __init__(self): self.value=trace(); self.error=None
    def me(self): return {'developer_id':'author-a'}
    def request(self,path,**kwargs):
        if path.endswith('/capabilities'): return {'capabilities':{'decision_trace':True}}
        if path.endswith('/releases/release-a'): return {'developer_id':'author-a','release_id':'release-a','archive_sha256':'A'*64}
        if '/profile?' in path: return {'recent_games':[{'job_id':'job','subject_seat':0}]}
        if self.error: raise self.error
        return self.value


class OnlineDecisionTraceTests(unittest.TestCase):
    def test_download_verify_and_idempotent_import(self):
        with tempfile.TemporaryDirectory() as root:
            a=pull_decision_traces(root,Client(),'release-a')
            b=pull_decision_traces(root,Client(),'release-a')
            self.assertEqual(1,a['downloaded'])
            self.assertEqual(a['items'][0]['trace_id'],b['items'][0]['trace_id'])
            self.assertFalse(a['bc_eligible'])

    def test_expired_is_reported_without_minting_native_trace(self):
        client=Client(); client.error=ControlError('ladder_replay_expired',410)
        with tempfile.TemporaryDirectory() as root:
            result=pull_decision_traces(root,client,'release-a')
            self.assertEqual(0,result['downloaded'])
            self.assertEqual('ladder_replay_expired',result['items'][0]['reason'])

    def test_wrong_release_seat_and_mutated_hash_fail_closed(self):
        for kind in ['release','seat','hash']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as root:
                client=Client()
                if kind=='release': client.value['release_id']='foreign'
                if kind=='seat': client.value['seat']=1
                if kind=='hash': client.value['records'][0]['record_sha256']='0'*64
                with self.assertRaises(ValueError): pull_decision_traces(root,client,'release-a')
