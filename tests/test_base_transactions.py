import copy
import unittest
from tools.ptcgdap.public_decision_contract import decision_fixture
from tools.ptcgdap.build_competitive_policy_v2_contract import _frame, _option


def goals():
    return [dict(goal_id='attack', priority=10, target_entity=10,
        continue_when=[dict(path='target/remaining_hp', op='gt', value=0)],
        success_when=[], abort_when=[],
        methods=[dict(method_id='prepare', when=[], steps=[
            dict(step_id='switch', when=[], option={'kind':'switch','target_entity_serial':10}, checkpoint=True)])]),
        dict(goal_id='preserve',priority=1,target_entity=11,continue_when=[],success_when=[],abort_when=[],
             methods=[dict(method_id='backup',when=[],steps=[
                 dict(step_id='switch-backup',when=[],option={'kind':'switch','target_entity_serial':11},checkpoint=False)])])]


class TransactionTests(unittest.TestCase):
    def test_rebind_continue_and_target_loss_changes_goal(self):
        from scripts.ai.ptcgdap.base_transactions import GoalJournal
        frame=decision_fixture(_option,_frame)
        journal=GoalJournal(goals(),seat=0,package_identity='test',match_id='m')
        first=journal.propose(frame,[0,1])
        self.assertEqual(first['indexes'],[0])
        frame['sequence']+=1;frame['source']['window_id']='D'*64
        frame['options'].reverse()
        for i,o in enumerate(frame['options']):o['index']=i
        self.assertEqual(journal.propose(frame,[0,1])['indexes'],[1])
        self.assertNotIn('indexes',journal.snapshot())
        frame['sequence']+=1;frame['source']['window_id']='C'*64
        frame['public_state']['self']['active']=[]
        frame['public_state']['decision']['entities']=frame['public_state']['decision']['entities'][1:]
        result=journal.propose(frame,[0,1])
        self.assertEqual(result['goal_id'],'preserve')
        self.assertEqual(result['event'],'replanned')

    def test_no_current_step_is_unknown_not_automatic_goal_failure(self):
        from scripts.ai.ptcgdap.base_transactions import GoalJournal
        frame=decision_fixture(_option,_frame)
        journal=GoalJournal(goals(),seat=0,package_identity='test',match_id='m')
        journal.propose(frame,[0,1])
        frame['sequence']+=1;frame['source']['window_id']='D'*64
        result=journal.propose(frame,[])
        self.assertEqual(result['goal_id'],'attack')
        self.assertEqual(result['indexes'],[])
        self.assertEqual(result['event'],'no_current_step')

    def test_quota_change_replans_and_stale_replay_rejected(self):
        from scripts.ai.ptcgdap.base_transactions import GoalJournal
        definitions=goals()
        definitions[0]['continue_when']=[dict(path='public_state/self/deck_count',op='gt',value=0)]
        frame=decision_fixture(_option,_frame)
        journal=GoalJournal(definitions,seat=0,package_identity='test',match_id='m')
        journal.propose(frame,[0,1])
        with self.assertRaisesRegex(ValueError,'transaction_stale_window'):
            journal.propose(frame,[0,1])
        frame['sequence']+=1;frame['source']['window_id']='C'*64
        frame['public_state']['self']['deck_count']=0
        self.assertEqual(journal.propose(frame,[0,1])['goal_id'],'preserve')

    def test_private_goal_fields_fail_closed(self):
        from scripts.ai.ptcgdap.base_transactions import GoalJournal
        definitions=goals();definitions[0]['private_rng']=1
        with self.assertRaises(ValueError):GoalJournal(definitions,seat=0,package_identity='test',match_id='m')

    def test_base_proposal_respects_forced_tiers_and_veto(self):
        from scripts.ai.ptcgdap.base_transactions import GoalJournal
        from scripts.ai.ptcgdap.competitive_policy_v2 import CompetitivePolicyV2Compiler as C, CompetitivePolicyV2Runtime as R
        from tools.ptcgdap.public_decision_contract import decision_cases
        from tools.ptcgdap.build_competitive_policy_v2_contract import _sample_policy
        case=decision_cases(_sample_policy,_option,_frame)[0]
        policy=C.compile_local_uid(case['policy'],allowed_card_uids=set(case['allowed_card_uids'])).policy
        for authority in ({}, {'mandatory_indexes':[1]}, {'terminal_indexes':[1]},
                          {'base_vetoed_indexes':[0]}, {'base_hard_tiers':[{'index':0,'tier':[1]},{'index':1,'tier':[0]}]}):
            journal=GoalJournal(goals(),seat=0,package_identity=policy._policy_hash,match_id='m')
            result=R.decide(policy,case['frame'],goal_journal=journal,**authority)
            self.assertTrue(result.accepted,result.error_code)
            self.assertEqual(result.selected_indexes,[1] if authority else [0])


if __name__=='__main__':unittest.main()
