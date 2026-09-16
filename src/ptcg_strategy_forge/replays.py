"""Bounded replay collection with frozen inputs and cross-process HTTP admission."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def identity(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def atomic_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(document))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("replay_redirect_forbidden")


class NetworkBudget:
    """SQLite transactions coordinate an origin across all local Forge processes."""

    def __init__(self, root):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "network.sqlite3"
        self.client = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS leases (id TEXT PRIMARY KEY, origin TEXT, expires REAL)")
            db.execute("CREATE TABLE IF NOT EXISTS origins (origin TEXT PRIMARY KEY, next REAL)")
            db.execute("CREATE TABLE IF NOT EXISTS clients (id TEXT, origin TEXT, concurrency INTEGER, rate REAL, expires REAL, PRIMARY KEY(id,origin))")

    def register(self, origin, concurrency, rate):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO clients VALUES (?,?,?,?,?)", (self.client, origin, concurrency, rate, time.time() + 120))

    def unregister(self):
        with self.connect() as db:
            db.execute("DELETE FROM clients WHERE id=?", (self.client,))

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @contextmanager
    def acquire(self, origin, concurrency, rate, cancelled=lambda: False):
        lease = uuid.uuid4().hex
        while True:
            if cancelled():
                raise ValueError("replay_cancelled")
            now = time.time()
            with self.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("DELETE FROM leases WHERE expires < ?", (now,))
                db.execute("DELETE FROM clients WHERE expires < ?", (now,))
                db.execute("UPDATE clients SET expires=? WHERE id=?", (now + 120, self.client))
                policy = db.execute("SELECT MIN(concurrency),MIN(rate) FROM clients WHERE origin=?", (origin,)).fetchone()
                effective_concurrency = min(concurrency, 4, policy[0] or 4)
                effective_rate = min(rate, policy[1] or rate)
                count = db.execute("SELECT COUNT(*) FROM leases WHERE origin=?", (origin,)).fetchone()[0]
                row = db.execute("SELECT next FROM origins WHERE origin=?", (origin,)).fetchone()
                if count < effective_concurrency and (row is None or row[0] <= now):
                    db.execute("INSERT INTO leases VALUES (?,?,?)", (lease, origin, now + 120))
                    db.execute("INSERT OR REPLACE INTO origins VALUES (?,?)", (origin, now + 1 / effective_rate))
                    break
            time.sleep(.02)
        try:
            yield
        finally:
            with self.connect() as db:
                db.execute("DELETE FROM leases WHERE id=?", (lease,))

    def defer(self, origin, seconds):
        with self.connect() as db:
            db.execute("INSERT INTO origins VALUES (?,?) ON CONFLICT(origin) DO UPDATE SET next=MAX(next,excluded.next)",
                       (origin, time.time() + seconds))


class ReplayCollection:
    def __init__(self, workspace, *, state_root=None):
        self.root = Path(workspace) / "data/replays"
        self.blobs = self.root / "blobs"
        self.blobs.mkdir(parents=True, exist_ok=True)
        global_root = Path(state_root) if state_root else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PTCGStrategyForge"
        self.budget = NetworkBudget(global_root)

    def _path(self, collection_id):
        if not re.fullmatch(r"[a-f0-9]{64}", collection_id):
            raise ValueError("replay_collection_id_invalid")
        return self.root / "collections" / (collection_id + ".json")

    def inspect(self, collection_id):
        return json.loads(self._path(collection_id).read_text(encoding="utf-8"))

    def verify(self, collection_id):
        document = self.inspect(collection_id)
        errors = []
        if (identity(document.get("input")) != collection_id or document.get("collection_id") != collection_id
                or document.get("status") != "completed"
                or document.get("result_sha256") != identity(document.get("objects"))):
            errors.append({"code": "replay_collection_integrity_failed"})
        expected = {row["id"]: row for row in document.get("input", {}).get("entries", [])}
        if set(expected) != {row["id"] for row in document["objects"]}:
            errors.append({"code": "replay_collection_incomplete"})
        for row in document["objects"]:
            digest = row.get("sha256", "")
            if not re.fullmatch(r"[a-f0-9]{64}", digest):
                errors.append({"id": row["id"], "code": "replay_not_downloaded"})
                continue
            path = self.blobs / (digest + ".json")
            advertised = expected.get(row["id"], {}).get("sha256")
            if advertised and advertised.lower() != digest:
                errors.append({"id": row["id"], "code": "replay_digest_mismatch"})
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                errors.append({"id": row["id"], "code": "replay_cache_corrupt"})
        return {"document_type": "forge_replay_verification_v1", "status": "failed" if errors else "passed", "errors": errors,
                "collection_id": collection_id}

    def sync(self, entries, *, concurrency=4, requests_per_second=2, max_games=1000,
             max_bytes=1024**3, max_object_bytes=16*1024**2, resume=False, query=None):
        if type(concurrency) is not int or not 1 <= concurrency <= 4 or type(requests_per_second) not in {int, float} or not 0 < requests_per_second <= 100:
            raise ValueError("replay_network_budget_invalid")
        if any(type(v) is not int or v <= 0 for v in (max_games, max_bytes, max_object_bytes)):
            raise ValueError("replay_budget_invalid")
        if max_object_bytes > 16*1024**2:
            raise ValueError("replay_object_budget_invalid")
        if not isinstance(entries, list) or any(not isinstance(row, dict) or not {"id", "url"} <= set(row) or set(row) - {"id", "url", "sha256"} for row in entries):
            raise ValueError("replay_manifest_invalid")
        if len(entries) > min(max_games, 10000):
            raise ValueError("replay_game_budget_exceeded")
        seen = set()
        for row in entries:
            if not isinstance(row["id"], str) or not isinstance(row["url"], str):
                raise ValueError("replay_manifest_invalid")
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", row.get("id", "")) or row["id"] in seen or row["id"] in {".", ".."}:
                raise ValueError("replay_identity_invalid")
            seen.add(row["id"])
            url = urlsplit(row["url"])
            if url.username or url.password or url.fragment or url.query or url.scheme not in {"http", "https"} or not url.hostname:
                raise ValueError("replay_url_invalid")
            if url.scheme == "http" and url.hostname not in {"127.0.0.1", "localhost", "::1"}:
                raise ValueError("replay_https_required")
            if row.get("sha256") and not re.fullmatch(r"[A-Fa-f0-9]{64}", row["sha256"]):
                raise ValueError("replay_digest_invalid")
        frozen = {"entries": sorted(entries, key=lambda r: r["id"]), "query": query or {},
                  "max_bytes": max_bytes, "max_games": max_games, "max_object_bytes": max_object_bytes,
                  "concurrency": concurrency, "requests_per_second": requests_per_second}
        collection_id = identity(frozen)
        path = self._path(collection_id)
        if path.exists():
            if not resume:
                raise ValueError("replay_collection_exists_use_resume")
            previous = self.inspect(collection_id)
            if previous["input"] != frozen:
                raise ValueError("replay_identity_conflict")
        else:
            previous = {"objects": []}
        prior = {row["id"]: row for row in previous["objects"]}
        document = {"document_type": "forge_replay_collection_v1", "schema_version": 1,
                    "collection_id": collection_id, "input": frozen, "status": "running", "objects": [],
                    "claims": {"source_authenticated": False, "bc_eligible": False}}
        from .jobs import JobStore
        jobs = JobStore(self.budget.path.parent)
        job_id = jobs.start("replays.sync", {"workspace": str(self.root.parents[1].resolve()), **frozen})
        document["job_id"] = job_id
        atomic_json(path, document)
        lock = threading.Lock()
        transferred = 0
        stop = threading.Event()
        heartbeat_stop = threading.Event()

        def heartbeat():
            while not heartbeat_stop.wait(10):
                jobs.heartbeat(job_id)
                if jobs.cancelled(job_id):
                    stop.set()

        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()

        def download(entry):
            nonlocal transferred
            old = prior.get(entry["id"])
            if old and old.get("status") == "completed":
                blob = self.blobs / (old["sha256"] + ".json")
                if blob.is_file() and hashlib.sha256(blob.read_bytes()).hexdigest() == old["sha256"]:
                    return old
            origin = "{}://{}".format(urlsplit(entry["url"]).scheme, urlsplit(entry["url"]).netloc)
            result = {"id": entry["id"], "status": "failed", "attempts": 0}
            for attempt in range(3):
                result["attempts"] += 1
                try:
                    with self.budget.acquire(origin, concurrency, requests_per_second, stop.is_set):
                        with build_opener(NoRedirect()).open(Request(entry["url"], headers={"Accept": "application/json"}), timeout=20) as response:
                            payload = bytearray()
                            started = time.monotonic()
                            while True:
                                if stop.is_set():
                                    raise ValueError("replay_cancelled")
                                block = response.read(65536)
                                if not block:
                                    break
                                with lock:
                                    transferred += len(block)
                                    if transferred > max_bytes:
                                        raise ValueError("replay_byte_budget_exceeded")
                                if len(payload) + len(block) > max_object_bytes or time.monotonic() - started > 60:
                                    raise ValueError("replay_object_budget_exceeded")
                                payload.extend(block)
                            parsed = json.loads(payload)
                            if response.headers.get("Content-Length") is not None and int(response.headers["Content-Length"]) != len(payload):
                                raise ValueError("replay_response_truncated")
                            if not isinstance(parsed, dict) or not isinstance(parsed.get("document_type"), str):
                                raise ValueError("replay_schema_invalid")
                            sha = hashlib.sha256(payload).hexdigest()
                            if entry.get("sha256") and sha != entry["sha256"].lower():
                                raise ValueError("replay_digest_mismatch")
                            if old and old.get("sha256") and old["sha256"] != sha:
                                raise ValueError("replay_identity_conflict")
                            blob = self.blobs / (sha + ".json")
                            with lock:
                                if blob.exists() and hashlib.sha256(blob.read_bytes()).hexdigest() != sha:
                                    raise ValueError("replay_cache_corrupt")
                                if not blob.exists():
                                    fd, temporary = tempfile.mkstemp(dir=self.blobs)
                                    try:
                                        with os.fdopen(fd, "wb") as stream:
                                            stream.write(payload)
                                        os.replace(temporary, blob)
                                    finally:
                                        Path(temporary).unlink(missing_ok=True)
                            return {**result, "status": "completed", "sha256": sha, "bytes": len(payload),
                                    "document_type": parsed["document_type"], "source_digest_verified": bool(entry.get("sha256"))}
                except HTTPError as error:
                    result["error_code"] = f"replay_http_{error.code}"
                    if error.code not in {429, 502, 503, 504}:
                        break
                    delay = error.headers.get("Retry-After", "1")
                    if delay.isdigit():
                        seconds = float(delay)
                    else:
                        from email.utils import parsedate_to_datetime
                        try:
                            seconds = max(0, parsedate_to_datetime(delay).timestamp() - time.time())
                        except (TypeError, ValueError):
                            seconds = 1
                    self.budget.defer(origin, seconds)
                    if seconds > 60:
                        result["error_code"] = "replay_retry_after_exceeds_attempt_budget"
                        break
                except (URLError, TimeoutError):
                    result["error_code"] = "replay_network_unavailable"
                except (ValueError, OSError) as error:
                    code = str(error)
                    result["error_code"] = code if code.startswith("replay_") else "replay_schema_invalid"
                    break
                time.sleep(.1 * 2**attempt)
            return result

        # executor.map consumes the already bounded frozen catalog; no process pool.
        for entry in entries:
            parsed = urlsplit(entry["url"])
            self.budget.register(f"{parsed.scheme}://{parsed.netloc}", concurrency, requests_per_second)
        executor = ThreadPoolExecutor(max_workers=concurrency)
        try:
            for row in executor.map(download, frozen["entries"]):
                document["objects"].append(row)
                atomic_json(path, document)
        except KeyboardInterrupt:
            stop.set()
        except BaseException:
            stop.set()
            jobs.finish(job_id, "failed", {"code": "replay_job_interrupted"})
            raise
        finally:
            executor.shutdown(wait=True, cancel_futures=True)
            heartbeat_stop.set()
            heartbeat_thread.join()
            self.budget.unregister()
        document["status"] = "cancelled" if stop.is_set() else "completed" if all(row["status"] == "completed" for row in document["objects"]) else "failed"
        document["transferred_bytes"] = transferred
        document["result_sha256"] = identity(document["objects"])
        atomic_json(path, document)
        jobs.finish(job_id, document["status"], {"collection_id": collection_id, "transferred_bytes": transferred})
        return document
