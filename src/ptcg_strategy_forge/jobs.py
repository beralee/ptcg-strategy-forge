"""Local job registry with exclusive attempts and preserved terminal history."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from .replays import canonical, identity


def state_root():
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PTCGStrategyForge"


class JobStore:
    def __init__(self, root=None):
        self._leases = {}
        root = Path(root) if root else state_root()
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "jobs.sqlite3"
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, document TEXT)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                db.execute("BEGIN IMMEDIATE")
                yield db
        finally:
            db.close()

    def start(self, operation, inputs):
        job_id = identity([operation, inputs])
        with self.connect() as db:
            existing = db.execute("SELECT document FROM jobs WHERE id=?", (job_id,)).fetchone()
            document = json.loads(existing[0]) if existing else {
                "document_type": "forge_job_v1", "schema_version": 1, "job_id": job_id,
                "operation": operation, "input": inputs, "attempts": []}
            if document.get("status") == "running":
                if document["heartbeat"] > time.time() - 120:
                    raise ValueError("job_already_running")
                document["attempts"].append({"status": "interrupted", "result": {"code": "job_lease_expired"}})
            token = uuid.uuid4().hex
            document.update(status="running", cancelled=False, heartbeat=time.time(), pid=os.getpid(), attempt_token=token)
            db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?)", (job_id, canonical(document).decode()))
        self._leases[job_id] = token
        return job_id

    def _update(self, job_id, fn):
        with self.connect() as db:
            row = db.execute("SELECT document FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise ValueError("job_not_found")
            document = json.loads(row[0])
            fn(document)
            db.execute("UPDATE jobs SET document=? WHERE id=?", (canonical(document).decode(), job_id))
            return document

    def heartbeat(self, job_id):
        def update(document):
            self._own(job_id, document)
            document.update(heartbeat=time.time())
        self._update(job_id, update)

    def _own(self, job_id, document):
        if self._leases.get(job_id) != document.get("attempt_token") or job_id not in self._leases:
            raise ValueError("job_attempt_superseded")

    def finish(self, job_id, status, result):
        if status not in {"completed", "failed", "cancelled", "interrupted"}:
            raise ValueError("job_terminal_state_invalid")
        def update(document):
            self._own(job_id, document)
            if document["status"] != "running":
                raise ValueError("job_attempt_not_running")
            document["status"] = status
            document["attempts"].append({"status": status, "result": result, "finished_at": time.time(), "attempt_token": document["attempt_token"]})
        return self._update(job_id, update)

    def cancel(self, job_id):
        def update(document):
            if document["status"] == "running":
                document["cancelled"] = True
        return self._update(job_id, update)

    def cancelled(self, job_id):
        document = self.status(job_id)
        self._own(job_id, document)
        return document["cancelled"]

    def status(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT document FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise ValueError("job_not_found")
            return json.loads(row[0])

    def list(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT document FROM jobs ORDER BY id")]
