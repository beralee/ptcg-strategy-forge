from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock,patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parents[1])]


class ResourceQueueTests(unittest.TestCase):
    def test_bounded_wait_still_checks_pressure_before_admission_and_releases(self):
        from ptcg_strategy_forge.resources_gate import heavy_job
        kernel=MagicMock();kernel.CreateMutexW.return_value=17;kernel.WaitForSingleObject.return_value=0
        state=dict(available_gib=11.,commit_percent=20.,other_heavy_pids=[])
        with patch('ptcg_strategy_forge.resources_gate.os.name','nt'),patch('ptcg_strategy_forge.resources_gate.ctypes.WinDLL',return_value=kernel,create=True),patch('ptcg_strategy_forge.resources_gate.windows_snapshot',return_value=state):
            with self.assertRaisesRegex(ValueError,'resource_ram_low'):
                with heavy_job(wait_ms=1000):self.fail('pressure bypassed')
        kernel.WaitForSingleObject.assert_called_once_with(17,1000)
        kernel.ReleaseMutex.assert_called_once_with(17);kernel.CloseHandle.assert_called_once_with(17)

    def test_timeout_never_releases_unowned_lock_or_scans_for_admission(self):
        from ptcg_strategy_forge.resources_gate import heavy_job
        kernel=MagicMock();kernel.CreateMutexW.return_value=17;kernel.WaitForSingleObject.return_value=0x102
        with patch('ptcg_strategy_forge.resources_gate.os.name','nt'),patch('ptcg_strategy_forge.resources_gate.ctypes.WinDLL',return_value=kernel,create=True),patch('ptcg_strategy_forge.resources_gate.windows_snapshot') as probe:
            with self.assertRaisesRegex(ValueError,'resource_heavy_job_active'):
                with heavy_job(wait_ms=60000):self.fail('timeout admitted')
        probe.assert_not_called();kernel.ReleaseMutex.assert_not_called();kernel.CloseHandle.assert_called_once_with(17)

    def test_wait_budget_rejects_unbounded_or_malformed_values(self):
        from ptcg_strategy_forge.resources_gate import heavy_job
        for value in (-1,60001,True,1.5):
            with self.assertRaisesRegex(ValueError,'resource_wait_budget_invalid'):
                with heavy_job(wait_ms=value):self.fail('invalid wait admitted')

    def test_failed_wait_is_not_misreported_as_a_busy_machine(self):
        from ptcg_strategy_forge.resources_gate import heavy_job
        kernel=MagicMock();kernel.CreateMutexW.return_value=17;kernel.WaitForSingleObject.return_value=0xFFFFFFFF
        with patch('ptcg_strategy_forge.resources_gate.os.name','nt'),patch('ptcg_strategy_forge.resources_gate.ctypes.WinDLL',return_value=kernel,create=True):
            with self.assertRaisesRegex(ValueError,'resource_mutex_unavailable'):
                with heavy_job(wait_ms=0):self.fail('failed mutex admitted')
        kernel.ReleaseMutex.assert_not_called();kernel.CloseHandle.assert_called_once_with(17)


if __name__=='__main__':unittest.main()
