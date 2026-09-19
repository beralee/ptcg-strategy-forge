import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


class RunSafetyTests(unittest.TestCase):
    def healthy(self):
        return dict(available_gib=32,commit_percent=40,other_heavy_pids=[],
                    disks=[dict(volume='D:\\',roles=['output'],free_gib=30)],
                    processes=[dict(pid=123,private_gib=0.1)],tree_private_gib=0.1,output_bytes=0)
    def test_disk_admission_and_running_thresholds(self):
        from ptcg_strategy_forge.run_safety import validate_storage
        rows=[dict(volume='D:\\', roles=['output','pagefile'], free_gib=20)]
        validate_storage(rows, admission=True)
        with self.assertRaisesRegex(ValueError,'resource_disk_low'):
            validate_storage([{**rows[0],'free_gib':19.99}],admission=True)
        validate_storage([{**rows[0],'free_gib':10}],admission=False)
        with self.assertRaisesRegex(ValueError,'resource_disk_low'):
            validate_storage([{**rows[0],'free_gib':9.99}],admission=False)
        validate_storage([dict(volume='C:\\',roles=['system','temp'],free_gib=5)],admission=True)
        for value in (None,float('nan'),True,-1):
            with self.assertRaisesRegex(ValueError,'resource_probe_unavailable'):
                validate_storage([{**rows[0],'free_gib':value}],admission=True)

    def test_private_memory_and_output_budget_fail_closed(self):
        from ptcg_strategy_forge.run_safety import validate_job
        healthy=dict(processes=[dict(pid=1,private_gib=1.0)],tree_private_gib=1.0,output_bytes=10)
        validate_job(healthy,output_limit_bytes=100)
        for change,code in [({'processes':[dict(pid=1,private_gib=8.1)]},'resource_process_private_high'),
                            ({'tree_private_gib':12.1},'resource_tree_private_high'),
                            ({'output_bytes':101},'resource_output_cap')]:
            with self.subTest(code=code),self.assertRaisesRegex(ValueError,code):
                validate_job({**healthy,**change},output_limit_bytes=100)

    def test_bench_failure_receipt_never_modifies_an_existing_run(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from tools.local_engine_bench import run
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'new-run'
            def fail(*args,**kwargs):
                output.mkdir()
                raise json.JSONDecodeError('truncated','{',1)
            with patch('tools.local_engine_bench._run',side_effect=fail):
                with self.assertRaises(json.JSONDecodeError):run('runtime','godot','plan',output)
            failure=(output/'failed-run.json').read_bytes()
            self.assertEqual(json.loads(failure)['error_code'],'bench_report_invalid')
            with patch('tools.local_engine_bench._run',side_effect=ValueError('bench_output_exists')):
                with self.assertRaises(ValueError):run('runtime','godot','plan',output)
            self.assertEqual((output/'failed-run.json').read_bytes(),failure)

    def test_atomic_json_preserves_previous_report_on_short_write(self):
        from ptcg_strategy_forge.run_safety import atomic_json
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)/'report.json';target.write_text('{"old":true}')
            with patch('ptcg_strategy_forge.run_safety.os.replace',side_effect=OSError('disk fault')):
                with self.assertRaisesRegex(ValueError,'resource_write_failed'):
                    atomic_json(target,{'clean':True})
            self.assertEqual(json.loads(target.read_text()),{'old':True})
            atomic_json(target,{'clean':False})
            self.assertEqual(json.loads(target.read_text()),{'clean':False})

    def test_monitor_stops_owned_child_before_failure_receipt(self):
        from ptcg_strategy_forge.run_safety import monitor_process
        child=Mock(pid=12345);child.poll.return_value=None
        probe=Mock(side_effect=ValueError('resource_disk_low'))
        order=[]
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'resource_disk_low'):
                monitor_process(child,Path(temp),storage_targets=[],max_seconds=10,
                                probe=probe,stop=lambda p:order.append(p.pid))
            self.assertEqual(order,[12345])
            self.assertEqual(json.loads((Path(temp)/'resource-failure.json').read_text())['error_code'],'resource_disk_low')

    def test_monitor_records_final_sample_even_for_fast_success(self):
        from ptcg_strategy_forge.run_safety import monitor_process
        child=Mock(pid=123);child.poll.return_value=0
        probe=Mock(return_value=self.healthy())
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(monitor_process(child,Path(temp),storage_targets=[],max_seconds=10,probe=probe),0)
            rows=[json.loads(l) for l in (Path(temp)/'resource-telemetry.jsonl').read_text().splitlines()]
            self.assertTrue(rows)
            self.assertEqual(rows[-1]['process_exit_code'],0)

    def test_monitor_wall_time_and_log_failure_stop_owned_child(self):
        from ptcg_strategy_forge.run_safety import monitor_process
        for fault in ('wall','log'):
            child=Mock(pid=123);child.poll.return_value=None
            stop=Mock()
            with tempfile.TemporaryDirectory() as temp:
                with patch('ptcg_strategy_forge.run_safety.time.monotonic',side_effect=[0,20,21,22,23]), \
                     patch('ptcg_strategy_forge.run_safety.append_telemetry',side_effect=OSError('disk fault') if fault=='log' else None):
                    with self.assertRaisesRegex(ValueError,'resource_wall_time_cap' if fault=='wall' else 'resource_write_failed'):
                        monitor_process(child,Path(temp),storage_targets=[],max_seconds=1 if fault=='wall' else 100,
                                        probe=lambda **kw:self.healthy(),stop=stop)
                stop.assert_called_once_with(child)

    def test_crossing_sample_is_saved_and_then_stops_the_child(self):
        from ptcg_strategy_forge.run_safety import monitor_process
        child=Mock(pid=123);child.poll.return_value=None;stop=Mock()
        for fields,error in [({'commit_percent':70},'resource_commit_high'),
                             ({'output_bytes':101},'resource_output_cap'),
                             ({'disks':[dict(volume='D:\\',roles=['output'],free_gib=9)]},'resource_disk_low')]:
            with self.subTest(error=error),tempfile.TemporaryDirectory() as temp:
                with self.assertRaisesRegex(ValueError,error):
                    monitor_process(child,Path(temp),storage_targets=[],max_seconds=30,output_limit_bytes=100,
                                    probe=lambda **kw:{**self.healthy(),**fields},stop=stop)
                self.assertTrue((Path(temp)/'resource-telemetry.jsonl').read_text().strip())


    @unittest.skipUnless(os.name=='nt','Windows child termination')
    def test_real_benign_child_is_stopped_on_injected_pressure(self):
        from ptcg_strategy_forge.run_safety import monitor_process
        with tempfile.TemporaryDirectory() as temp:
            child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                with self.assertRaisesRegex(ValueError,'resource_commit_high'):
                    monitor_process(child,Path(temp),storage_targets=[],max_seconds=10,
                                    probe=Mock(side_effect=ValueError('resource_commit_high')))
                self.assertIsNotNone(child.poll())
            finally:
                if child.poll() is None:child.kill();child.wait()


if __name__=='__main__':unittest.main()
