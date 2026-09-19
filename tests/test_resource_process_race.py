"""A process transition must not hide a live, unreadable heavy process."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ptcg_strategy_forge import resources_gate as gate


def row(pid=23, command=None):
    return dict(ProcessId=pid,ParentProcessId=1,Name='python.exe',CommandLine=command)


class ProcessTransitionTests(unittest.TestCase):
    def snapshot(self, scans, exited=False):
        def memory(pointer):
            pointer._obj.avail_phys=32*1024**3
            return 1
        def performance(pointer,size):
            pointer._obj.commit_limit=100
            pointer._obj.commit_total=25
            pointer._obj.page_size=4096
            return 1
        native=SimpleNamespace(kernel32=SimpleNamespace(GlobalMemoryStatusEx=memory),psapi=SimpleNamespace(GetPerformanceInfo=performance))
        outputs=[subprocess.CompletedProcess([],0,json.dumps(rows),'') for rows in scans]
        with patch.object(gate.os,'name','nt'),patch.object(gate.os,'getpid',return_value=999),patch.object(gate.ctypes,'windll',native,create=True),patch.object(gate.subprocess,'CREATE_NO_WINDOW',0,create=True),patch.object(gate.subprocess,'run',side_effect=outputs) as scan,patch.object(gate,'_confirmed_process_exited',return_value=exited,create=True) as exit_probe:
            result=gate.windows_snapshot()
            return result,scan.call_count,exit_probe.call_count

    def test_transient_null_command_reobserves_and_detects_heavy_process(self):
        result,scans,_=self.snapshot([[row()],[row(command='python bench.py')]])
        self.assertEqual(result['other_heavy_pids'],[23])
        self.assertEqual(scans,2)
        with self.assertRaisesRegex(ValueError,'resource_heavy_job_active'):
            gate.validate_snapshot(result)

    def test_complete_second_scan_also_captures_new_heavy_process(self):
        result,scans,_=self.snapshot([[row()],[row(24,'python train.py')]])
        self.assertEqual(result['other_heavy_pids'],[24])
        self.assertEqual(scans,2)

    def test_only_confirmed_exited_null_process_can_be_ignored(self):
        result,scans,probes=self.snapshot([[row()],[row()]],exited=True)
        self.assertEqual(result['other_heavy_pids'],[])
        self.assertEqual((scans,probes),(2,1))

    def test_unreadable_alive_or_uninspectable_process_still_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'resource_probe_unavailable'):
            self.snapshot([[row()],[row()]],exited=False)

    def test_readable_process_needs_only_one_scan(self):
        result,scans,probes=self.snapshot([[row(command='python benign.py')]])
        self.assertEqual(result['other_heavy_pids'],[])
        self.assertEqual((scans,probes),(1,0))

    def test_empty_live_command_is_unknown_not_a_benign_process(self):
        with self.assertRaisesRegex(ValueError,'resource_probe_unavailable'):
            self.snapshot([[row(command='')],[row(command='')]],exited=False)


class ExitProofTests(unittest.TestCase):
    def test_only_absent_pid_error_is_proof_when_open_fails(self):
        for error,expected in ((87,True),(5,False),(0,False)):
            kernel=MagicMock();kernel.OpenProcess.return_value=None
            with patch.object(gate.ctypes,'WinDLL',return_value=kernel,create=True),patch.object(gate.ctypes,'get_last_error',return_value=error,create=True):
                self.assertEqual(gate._confirmed_process_exited(23),expected)
            kernel.CloseHandle.assert_not_called()

    def test_signaled_handle_only_and_every_open_handle_is_closed(self):
        for status,expected in ((0,True),(0x102,False),(0xFFFFFFFF,False)):
            kernel=MagicMock();kernel.OpenProcess.return_value=123;kernel.WaitForSingleObject.return_value=status
            with patch.object(gate.ctypes,'WinDLL',return_value=kernel,create=True):
                self.assertEqual(gate._confirmed_process_exited(23),expected)
            kernel.WaitForSingleObject.assert_called_once_with(123,0)
            kernel.CloseHandle.assert_called_once_with(123)

    def test_invalid_pid_is_not_treated_as_exited(self):
        for pid in (0,-1,True,None,'23'):
            self.assertFalse(gate._confirmed_process_exited(pid))


if __name__=='__main__':unittest.main()
