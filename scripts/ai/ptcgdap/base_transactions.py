"""Bounded Base-side semantic goals; proposals never carry window authority.

Definitions are reviewed data. Only identities and goal phase persist. Every
predicate and every option binding is reevaluated against BaseInput each call.
This research controller is not an extension of the installed package schema.
"""
import copy
from .base_input import BaseInput, canonical, digest

GOAL_KEYS = {'goal_id','priority','target_entity','continue_when','success_when','abort_when','methods'}
METHOD_KEYS = {'method_id','when','steps'}
STEP_KEYS = {'step_id','when','option','checkpoint'}
OPTION_KEYS = {'kind','card_uid','source_uid','target_uid','source_entity_serial',
               'target_entity_serial','attack_index','ability_index'}


def _conditions(rows):
    if type(rows) is not list or len(rows)>64:
        raise ValueError('transaction_conditions_invalid')
    for row in rows:
        if (type(row) is not dict or set(row)!={'path','op','value'}
                or row['op'] not in ('eq','ne','gt','gte','lt','lte','contains')
                or type(row['path']) is not str
                or not row['path'].startswith(('public_state/','target/'))
                or any(s in row['path'].lower() for s in ('hidden','private','opponent/hand/','deck/','prize/'))
                or type(row['value']) not in (int,bool,str,type(None))):
            raise ValueError('transaction_conditions_invalid')


def validate(definitions):
    if type(definitions) is not list or not 1<=len(definitions)<=32:
        raise ValueError('transaction_definitions_invalid')
    ids=set()
    for goal in definitions:
        if (type(goal) is not dict or set(goal)!=GOAL_KEYS or type(goal['goal_id']) is not str
                or not goal['goal_id'] or goal['goal_id'] in ids or type(goal['priority']) is not int
                or type(goal['target_entity']) not in (int,type(None))
                or type(goal['methods']) is not list or not 1<=len(goal['methods'])<=16):
            raise ValueError('transaction_definitions_invalid')
        ids.add(goal['goal_id'])
        for key in ('continue_when','success_when','abort_when'):_conditions(goal[key])
        mids=set()
        for method in goal['methods']:
            if (type(method) is not dict or set(method)!=METHOD_KEYS or type(method['method_id']) is not str
                    or method['method_id'] in mids or type(method['steps']) is not list or not 1<=len(method['steps'])<=32):
                raise ValueError('transaction_method_invalid')
            mids.add(method['method_id']);_conditions(method['when'])
            sids=set()
            for step in method['steps']:
                if (type(step) is not dict or set(step)!=STEP_KEYS or type(step['step_id']) is not str
                        or step['step_id'] in sids or type(step['checkpoint']) is not bool
                        or type(step['option']) is not dict or not step['option'] or set(step['option'])-OPTION_KEYS
                        or any(type(v) not in (str,int,bool,type(None)) for v in step['option'].values())):
                    raise ValueError('transaction_step_invalid')
                sids.add(step['step_id']);_conditions(step['when'])


def _target(frame, serial):
    if serial is None:return {}
    for side in ('self','opponent'):
        for zone in ('active','bench'):
            for slot in frame['public_state'][side][zone]:
                if slot.get('entity_serial')==serial:
                    extra=next((e for e in frame['public_state'].get('decision',{}).get('entities',[])
                                if e['entity_serial']==serial),{})
                    return {**slot,**extra}
    return None


def _matches(rows, frame, target):
    from .competitive_policy_v2 import _compare
    for row in rows:
        value={'public_state':frame['public_state'],'target':target}
        for part in row['path'].split('/'):
            if not isinstance(value,dict) or part not in value:return False
            value=value[part]
        # Unknown is never evidence for a negative guard.
        if value is None or not _compare(value,row['op'],row['value']):return False
    return True


class GoalJournal:
    def __init__(self, definitions, *, seat, package_identity, match_id):
        validate(definitions)
        if seat not in (0,1) or not package_identity or not match_id:
            raise ValueError('transaction_scope_invalid')
        self._definitions=copy.deepcopy(definitions)
        self.definitions_sha256=digest(definitions)
        self.seat=seat;self.package_identity=package_identity;self.match_id=match_id
        self._state={};self._sequence=-1;self._window=None

    def snapshot(self):return copy.deepcopy(self._state)

    def propose(self, frame, admitted_indexes):
        value=BaseInput.capture(frame);frame=value.frame()
        if frame['seat']!=self.seat:raise ValueError('transaction_scope_mismatch')
        if frame['sequence']<=self._sequence or frame['source']['window_id']==self._window:
            raise ValueError('transaction_stale_window')
        if (type(admitted_indexes) is not list or len(set(admitted_indexes))!=len(admitted_indexes)
                or any(type(i) is not int or not 0<=i<len(frame['options']) for i in admitted_indexes)):
            raise ValueError('transaction_frontier_invalid')
        self._sequence=frame['sequence'];self._window=frame['source']['window_id']
        turn=frame['public_state']['turn_number'];previous=self._state.get('goal_id')
        viable=[]
        for goal in self._definitions:
            target=_target(frame,goal['target_entity'])
            if target is None:continue
            if not _matches(goal['continue_when'],frame,target):continue
            if goal['abort_when'] and _matches(goal['abort_when'],frame,target):continue
            if goal['success_when'] and _matches(goal['success_when'],frame,target):continue
            viable.append(goal)
        active=next((g for g in viable if g['goal_id']==previous),None)
        if self._state.get('turn')!=turn:active=None
        if active is None and viable:active=min(viable,key=lambda g:(-g['priority'],g['goal_id']))
        if active is None:
            self._state={}
            return dict(goal_id=None,event='retired',indexes=[],checkpoint=False)
        event='continued' if previous==active['goal_id'] else 'replanned' if previous else 'started'
        self._state=dict(goal_id=active['goal_id'],target_entity=active['target_entity'],turn=turn,phase='active')
        target=_target(frame,active['target_entity'])
        for method in active['methods']:
            if not _matches(method['when'],frame,target):continue
            for step in method['steps']:
                if not _matches(step['when'],frame,target):continue
                indexes=[i for i in admitted_indexes if all(frame['options'][i].get(k)==v
                         for k,v in step['option'].items())]
                if indexes:
                    self._state.update(method_id=method['method_id'],phase=step['step_id'])
                    return dict(goal_id=active['goal_id'],method_id=method['method_id'],step_id=step['step_id'],
                        event=event,indexes=indexes,checkpoint=step['checkpoint'])
        return dict(goal_id=active['goal_id'],event='no_current_step',indexes=[],checkpoint=False)
