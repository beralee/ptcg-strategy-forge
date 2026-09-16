"""Real HTTP integration tests; no production service authority is implied."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class ReplayCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.payload = b'{"document_type":"godot_v18_public_series_replay_v1"}'
        self.active = self.peak = self.requests = 0
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.active += 1
                owner.peak = max(owner.peak, owner.active)
                owner.requests += 1
                time.sleep(.025)
                self.send_response(200)
                self.send_header("Content-Length", str(len(owner.payload)))
                self.end_headers()
                self.wfile.write(owner.payload)
                owner.active -= 1
            def log_message(self, *args):
                pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def entries(self, count=6):
        return [{"id": str(i), "url": self.origin + f"/replay/{i}",
                 "sha256": hashlib.sha256(self.payload).hexdigest()} for i in range(count)]

    def test_controlled_download_resume_and_corruption_repair(self):
        from ptcg_strategy_forge.replays import ReplayCollection
        collection = ReplayCollection(self.root, state_root=self.root / "global")
        result = collection.sync(self.entries(), concurrency=2, requests_per_second=100)
        self.assertEqual("completed", result["status"])
        self.assertLessEqual(self.peak, 2)
        self.assertEqual(6, self.requests)
        self.assertEqual("passed", collection.verify(result["collection_id"])["status"])
        collection.sync(self.entries(), concurrency=2, requests_per_second=100, resume=True)
        self.assertEqual(6, self.requests)
        blob = next((self.root / "data/replays/blobs").glob("*.json"))
        blob.write_text("corrupt")
        self.assertEqual("failed", collection.verify(result["collection_id"])["status"])

    def test_hash_mismatch_never_commits_success(self):
        from ptcg_strategy_forge.replays import ReplayCollection
        entries = self.entries(1)
        entries[0]["sha256"] = "0" * 64
        result = ReplayCollection(self.root, state_root=self.root / "global").sync(entries)
        self.assertEqual("failed", result["status"])
        self.assertEqual("replay_digest_mismatch", result["objects"][0]["error_code"])

    def test_budget_and_unsafe_paths_fail_before_network(self):
        from ptcg_strategy_forge.replays import ReplayCollection
        collection = ReplayCollection(self.root, state_root=self.root / "global")
        with self.assertRaisesRegex(ValueError, "replay_game_budget_exceeded"):
            collection.sync(self.entries(2), max_games=1)
        entries = self.entries(1)
        entries[0]["id"] = "../escape"
        with self.assertRaisesRegex(ValueError, "replay_identity_invalid"):
            collection.sync(entries)
        self.assertEqual(0, self.requests)

    def test_oversized_stream_is_not_promoted(self):
        from ptcg_strategy_forge.replays import ReplayCollection
        result = ReplayCollection(self.root, state_root=self.root / "global").sync(self.entries(1), max_bytes=10)
        self.assertEqual("failed", result["status"])
        self.assertFalse(list((self.root / "data/replays/blobs").glob("*.json")))

    def test_frozen_identity_changes_with_query(self):
        from ptcg_strategy_forge.replays import ReplayCollection
        collection = ReplayCollection(self.root, state_root=self.root / "global")
        first = collection.sync(self.entries(1), query={"release_id": "a"})
        second = collection.sync(self.entries(1), query={"release_id": "b"})
        self.assertNotEqual(first["collection_id"], second["collection_id"])

    def test_manifest_tampering_fails_verification(self):
        from ptcg_strategy_forge.replays import ReplayCollection
        collection = ReplayCollection(self.root, state_root=self.root / "global")
        result = collection.sync(self.entries(1))
        path = collection._path(result["collection_id"])
        document = json.loads(path.read_bytes())
        document["input"]["query"] = {"changed": True}
        path.write_text(json.dumps(document), encoding="utf-8")
        self.assertEqual("failed", collection.verify(result["collection_id"])["status"])

    def test_concurrent_clients_share_stricter_origin_limit(self):
        from ptcg_strategy_forge.replays import NetworkBudget
        budget_a = NetworkBudget(self.root / "global")
        budget_b = NetworkBudget(self.root / "global")
        budget_a.register(self.origin, 1, 100)
        budget_b.register(self.origin, 4, 100)
        entered = threading.Event()
        def contender():
            with budget_b.acquire(self.origin, 4, 100):
                entered.set()
        try:
            with budget_a.acquire(self.origin, 1, 100):
                thread = threading.Thread(target=contender)
                thread.start()
                self.assertFalse(entered.wait(.1))
            thread.join(timeout=3)
            self.assertTrue(entered.is_set())
        finally:
            budget_a.unregister()
            budget_b.unregister()


if __name__ == "__main__":
    unittest.main()
