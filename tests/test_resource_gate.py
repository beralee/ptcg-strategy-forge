from pathlib import Path
import sys
import unittest
import os
import subprocess
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class ResourceGateTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows kernel mutex")
    def test_kernel_mutex_blocks_second_process_without_launching_a_pool(self):
        from ptcg_strategy_forge.resources_gate import heavy_job
        code = "from ptcg_strategy_forge.resources_gate import heavy_job\ntry:\n with heavy_job(): print('unexpected')\nexcept ValueError as error: print(str(error))"
        with patch("ptcg_strategy_forge.resources_gate.windows_snapshot", return_value=self.healthy()), heavy_job():
            child = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=20,
                                   env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
        self.assertEqual(0, child.returncode, child.stderr)
        self.assertEqual("resource_heavy_job_active", child.stdout.strip())

    def healthy(self):
        return {"available_gib": 32.0, "commit_percent": 40.0, "other_heavy_pids": []}

    def test_memory_commit_and_other_pool_are_independent_hard_gates(self):
        from ptcg_strategy_forge.resources_gate import validate_snapshot
        for fields, code in [({"available_gib": 11.99}, "resource_ram_low"),
                             ({"commit_percent": 70.0}, "resource_commit_high"),
                             ({"other_heavy_pids": [123]}, "resource_heavy_job_active")]:
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, code):
                validate_snapshot({**self.healthy(), **fields})
        self.assertIsNone(validate_snapshot(self.healthy()))

    def test_unknown_probe_values_fail_closed(self):
        from ptcg_strategy_forge.resources_gate import validate_snapshot
        for snapshot in ({}, {**self.healthy(), "available_gib": float("nan")},
                         {**self.healthy(), "commit_percent": None}):
            with self.assertRaisesRegex(ValueError, "resource_probe_unavailable"):
                validate_snapshot(snapshot)

    def test_worker_limit_cannot_be_overridden_by_environment(self):
        from ptcg_strategy_forge.resources_gate import validate_workers
        with patch.dict("os.environ", {"PTCGABC_MAX_WORKERS": "999"}):
            with self.assertRaisesRegex(ValueError, "resource_workers_invalid"):
                validate_workers(5)
        for value in (True, 0, -1):
            with self.assertRaises(ValueError):
                validate_workers(value)
        validate_workers(4)


if __name__ == "__main__":
    unittest.main()
