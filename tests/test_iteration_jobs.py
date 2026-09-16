from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class JobTests(unittest.TestCase):
    def test_expired_attempt_cannot_mutate_replacement(self):
        from ptcg_strategy_forge.jobs import JobStore
        with tempfile.TemporaryDirectory() as temp:
            old = JobStore(temp)
            new = JobStore(temp)
            job = old.start("test", {})
            old._update(job, lambda d: d.update(heartbeat=0))
            new.start("test", {})
            for action in (lambda: old.heartbeat(job), lambda: old.finish(job, "completed", {}), lambda: old.cancelled(job)):
                with self.assertRaisesRegex(ValueError, "job_attempt_superseded"):
                    action()
            new.finish(job, "completed", {})
            self.assertEqual(["interrupted", "completed"], [a["status"] for a in new.status(job)["attempts"]])

    def test_exclusive_attempt_cancellation_and_history(self):
        from ptcg_strategy_forge.jobs import JobStore
        with tempfile.TemporaryDirectory() as temp:
            jobs = JobStore(Path(temp))
            job = jobs.start("replays.sync", {"workspace": temp, "entries": []})
            with self.assertRaisesRegex(ValueError, "job_already_running"):
                jobs.start("replays.sync", {"workspace": temp, "entries": []})
            jobs.cancel(job)
            self.assertTrue(jobs.cancelled(job))
            jobs.finish(job, "cancelled", {"downloaded": 0})
            repeated = jobs.start("replays.sync", {"workspace": temp, "entries": []})
            self.assertEqual(job, repeated)
            jobs.finish(job, "completed", {"downloaded": 1})
            state = jobs.status(job)
            self.assertEqual(["cancelled", "completed"], [attempt["status"] for attempt in state["attempts"]])
            self.assertEqual(1, len(jobs.list()))


if __name__ == "__main__":
    unittest.main()
