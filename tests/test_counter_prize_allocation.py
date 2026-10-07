"""Current-window arithmetic, not a prediction of prevented effects."""
import copy
import itertools
import unittest
from scripts.ai.ptcgdap.public_decision_facts import decision_fact

FACT = 'decision.option.counter_prize_plan'


def counter_frame(hps, prizes, budget=6, pending=None):
    pending = pending or [0]*len(hps)
    options = [dict(index=i, target_entity_serial=100+i, target_uid='M2_001',
                    target_remaining_hp=hp, target_prize_value=prizes[i],
                    target_pending_damage_counters=pending[i], remaining_damage_counters=budget)
               for i, hp in enumerate(hps)]
    return dict(select_semantics=dict(select_type_raw=1, select_context_raw=13), options=options,
                public_state=dict(opponent=dict(active=[], bench=[dict(entity_serial=100+i,
                    local_card_uid='M2_001', remaining_hp=hp, prize_value=prizes[i]) for i,hp in enumerate(hps)])))


class CounterPrizeAllocationTests(unittest.TestCase):
    def values(self, frame):
        return [decision_fact(frame, o, FACT) for o in frame['options']]

    def test_three_single_prizes_beat_one_double(self):
        f = counter_frame([20,20,20,60], [1,1,1,2])
        self.assertEqual(self.values(f), [2,2,2,0])

    def test_reobserve_ignores_already_lethal(self):
        f = counter_frame([20,20,20,60], [1,1,1,2], 4, [2,0,0,0])
        self.assertEqual(self.values(f), [0,2,2,0])
        f['options'].reverse()
        for i,o in enumerate(f['options']): o['index']=i
        self.assertEqual(self.values(f), [0,2,2,0])

    def test_budget_flip_and_non_multiple_hp(self):
        self.assertEqual(self.values(counter_frame([21,30], [1,2], 3)), [0,3])
        self.assertEqual(self.values(counter_frame([21,30], [1,2], 2)), [2,0])

    def test_spare_damage_concentrates_without_overkill(self):
        self.assertEqual(self.values(counter_frame([20,70], [1,1], 6)), [2,4])
        self.assertEqual(self.values(counter_frame([20,70], [1,1], 4, [2,0])), [0,4])

    def test_missing_wrong_scope_and_identity_fail_closed(self):
        f=counter_frame([20,70],[1,1])
        for change in ('budget','context','identity','duplicate','hp','cap','too_many','non_opponent','prize'):
            g=copy.deepcopy(f)
            if change=='budget': del g['options'][0]['remaining_damage_counters']
            elif change=='context': g['select_semantics']['select_context_raw']=25
            elif change=='identity': g['options'][0]['target_uid']='M2_999'
            elif change=='duplicate': g['options'].append(copy.deepcopy(g['options'][0]))
            elif change=='cap': g['public_state']['decision']={'selection':{'max_assignments_per_target':1}}
            elif change=='too_many':
                for o in g['options']:o['remaining_damage_counters']=7
            elif change=='non_opponent': g['public_state']['opponent']['bench'].pop(0)
            elif change=='prize':g['options'][0]['target_prize_value']=2
            else: g['options'][0]['target_remaining_hp']=10
            self.assertTrue(all(v is None for v in self.values(g)),change)

    def test_small_exhaustive_prize_optimality(self):
        # Independent complete enumeration checks the primary objective.
        for hps in itertools.product([10,20,40], repeat=3):
            for prizes in itertools.product([1,2], repeat=3):
                for budget in range(1,7):
                    allocation=self.values(counter_frame(hps,prizes,budget))
                    self.assertTrue(all(type(x) is int and x>=0 for x in allocation))
                    self.assertEqual(sum(allocation),budget)
                    got=sum(p for hp,p,n in zip(hps,prizes,allocation) if n*10>=hp)
                    best=max(sum(p for hp,p,n in zip(hps,prizes,a) if n*10>=hp)
                        for a in itertools.product(range(budget+1),repeat=3) if sum(a)==budget)
                    self.assertEqual(got,best,(hps,prizes,budget,allocation))

    def test_six_reobserved_windows_all_target_orders(self):
        for order in itertools.permutations(range(4)):
            f=counter_frame([20,20,20,60],[1,1,1,2])
            f['options']=[f['options'][i] for i in order]
            for budget in range(6,0,-1):
                before=copy.deepcopy(f)
                values=self.values(f)
                # Mirrors the strategy's highest positive planned allocation.
                choice=max(range(4),key=lambda i:values[i])
                self.assertEqual(f,before)
                for i,o in enumerate(f['options']):
                    o['remaining_damage_counters']=budget-1
                    if i==choice:o['target_pending_damage_counters']+=1
            assignments={o['target_entity_serial']:o['target_pending_damage_counters'] for o in f['options']}
            self.assertEqual(assignments,{100:2,101:2,102:2,103:0})


if __name__=='__main__': unittest.main()
