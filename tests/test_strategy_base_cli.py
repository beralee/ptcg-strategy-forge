import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_strategy_base import _adapter, StrategyBase, BasePlanError, make_plan
from ptcg_strategy_forge import StrategyWorkspace
from tools.strategy_base import main, inputs, write_new


class StrategyBaseCliTests(unittest.TestCase):
    def test_init_audit_compile_and_immutable_source_lock(self):
        with tempfile.TemporaryDirectory() as temp, contextlib.redirect_stdout(io.StringIO()):
            root=Path(temp)/'workspace'
            StrategyWorkspace.create(root,author_id='local-test',deck_id=646600)
            adapter,plan=make_plan()
            (root/'package/policy/adapter.json').write_text(json.dumps(adapter),encoding='utf-8')
            self.assertEqual(main(['init','--workspace',str(root)]),0)
            self.assertEqual(main(['audit','--workspace',str(root)]),2)
            (root/'base/plan.json').write_text(json.dumps(plan),encoding='utf-8')
            target=root/'candidate'
            self.assertEqual(main(['compile','--workspace',str(root),'--output',str(target)]),0)
            self.assertEqual(len(json.loads((target/'adapter.json').read_bytes())['route_candidates']),2)
            self.assertEqual(json.loads((root/'package/policy/adapter.json').read_bytes()),adapter)
            with self.assertRaises(FileExistsError):
                main(['compile','--workspace',str(root),'--output',str(target)])
            path=root/'package/deck/deck_manifest.json'
            path.write_bytes(path.read_bytes()+b'\n')
            with self.assertRaisesRegex(BasePlanError,'base_source_lock_changed'):
                inputs(root)

    def test_new_outputs_do_not_overwrite_existing_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'report.json';write_new(path,{'original':True})
            with self.assertRaises(FileExistsError):write_new(path,{'original':False})
            self.assertEqual(json.loads(path.read_bytes()),{'original':True})


if __name__=='__main__':unittest.main()
