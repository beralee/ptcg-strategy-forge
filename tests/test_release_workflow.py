from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class ReleaseWorkflowTests(unittest.TestCase):
    def test_expired_sender_cannot_overwrite_replacement_receipt(self):
        from ptcg_strategy_forge.release_workflow import ReleaseLedger
        from ptcg_strategy_forge.jobs import JobStore
        from ptcg_strategy_forge.replays import identity
        with tempfile.TemporaryDirectory() as temp:
            ledger = ReleaseLedger(temp)
            scope = {"service": "test-service", "author_id": "developer-test", "archive_sha256": "a"*64}
            submission_id = identity(scope)
            inputs = {"ledger": str(ledger.root.resolve()), "submission_id": submission_id}
            def expired(_):
                jobs = JobStore()
                job_id = identity(["release.submit", inputs])
                jobs._update(job_id, lambda d: d.update(heartbeat=0))
                jobs.start("release.submit", inputs)
                jobs.finish(job_id, "completed", {})
                return {"release_id": "release-old", "archive_sha256": "a"*64}
            with self.assertRaisesRegex(ValueError, "job_attempt_superseded"):
                ledger.submit(scope, send=expired)
            self.assertEqual("unknown", ledger.status(submission_id)["receipt_state"])

    def test_preflight_rejects_wrong_account_and_verifies_public_key_identity(self):
        from ptcg_strategy_forge import StrategyWorkspace
        from ptcg_strategy_forge.release_signing import generate_release_key
        from ptcg_strategy_forge.release_workflow import prepare_release
        from tools.ptcgdap.author_strategy_developer import build_development_package
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = StrategyWorkspace.create(root / "deck", author_id="developer-test")
            def check(source, *, output):
                build_development_package(source / "package", output)
                return {"status": "passed", "artifact": {"path": str(output)}}
            with patch("ptcg_strategy_forge.application.check_workspace", side_effect=check):
                workspace.build()
            public = root / "public.json"
            generate_release_key(root / "private.key", public)
            with self.assertRaisesRegex(ValueError, "release_author_identity_mismatch"):
                prepare_release(workspace, "developer-wrong", public)
            result = prepare_release(workspace, "developer-test", public)
            self.assertEqual("ready_for_local_signing", result["status"])
            self.assertFalse(result["registration_verified"])

    def test_acceptance_survives_failed_refresh_and_is_not_resubmitted(self):
        from ptcg_strategy_forge.release_workflow import ReleaseLedger
        with tempfile.TemporaryDirectory() as temp:
            ledger = ReleaseLedger(temp)
            scope = {"service": "test-service", "author_id": "developer-test", "archive_sha256": "a"*64}
            send = Mock(return_value={"release_id": "release-1", "archive_sha256": "a"*64})
            refresh = Mock(side_effect=OSError("unavailable"))
            first = ledger.submit(scope, send=send, refresh=refresh)
            second = ledger.submit(scope, send=send, refresh=refresh)
            self.assertEqual("accepted", first["receipt_state"])
            self.assertEqual("unknown", first["qualification_state"])
            self.assertEqual(first["release_id"], second["release_id"])
            self.assertEqual(1, send.call_count)

    def test_unknown_receipt_never_automatically_reposts(self):
        from ptcg_strategy_forge.release_workflow import ReleaseLedger
        with tempfile.TemporaryDirectory() as temp:
            ledger = ReleaseLedger(temp)
            scope = {"service": "test-service", "author_id": "developer-test", "archive_sha256": "a"*64}
            send = Mock(side_effect=OSError("disconnected after write"))
            first = ledger.submit(scope, send=send)
            self.assertEqual("unknown", first["receipt_state"])
            ledger.submit(scope, send=send)
            self.assertEqual(1, send.call_count)
            reconciled = ledger.submit(scope, send=send, reconcile=lambda _: {"release_id": "release-1", "archive_sha256": "a"*64})
            self.assertEqual("accepted", reconciled["receipt_state"])
            self.assertEqual(1, send.call_count)
