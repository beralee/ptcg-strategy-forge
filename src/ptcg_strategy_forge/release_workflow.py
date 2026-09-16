"""Durable receipt state machine, independent of service authentication adapters."""
import json
from pathlib import Path
import re
import time
import base64
import hashlib

from .replays import identity, atomic_json
from .jobs import JobStore


def prepare_release(workspace, author_id, public_key_path):
    from .lineage import acceptance
    from scripts.ai.ptcgdap.author_strategy_package import AuthorStrategyPackageLoader
    artifact = workspace.default_artifact
    current = acceptance(workspace.root, artifact, workspace.default_report)
    if current["status"] != "current":
        raise ValueError("release_acceptance_stale")
    package = AuthorStrategyPackageLoader().load_path(artifact)
    manifest = json.loads(package.payload_bytes("strategy_package.json"))
    if manifest["author"]["author_id"] != author_id:
        raise ValueError("release_author_identity_mismatch")
    document = json.loads(Path(public_key_path).read_bytes())
    try:
        raw = base64.b64decode(document["public_key_base64"], validate=True)
        fingerprint = hashlib.sha256(raw).hexdigest().upper()
        key_id = "signing-" + fingerprint[:24].lower()
        if (len(raw) != 32 or document.get("algorithm") != "ed25519"
                or document.get("fingerprint_sha256") != fingerprint or document.get("key_id") != key_id):
            raise ValueError("release_public_key_invalid")
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("release_public_key_invalid") from error
    report = {"document_type": "forge_release_preparation_v1", "status": "ready_for_local_signing",
              "author_id": author_id, "package_id": manifest["package_id"], "package_version": manifest["package_version"],
              "archive_sha256": package.archive_sha256, "acceptance_record_id": current["record_id"],
              "signing_key_id": key_id, "signing_key_fingerprint_sha256": fingerprint,
              "registration_verified": False, "account_identity_source": "explicit_developer_input",
              "production_authority": False}
    preparation_id = identity(report)
    path = workspace.root / "releases/preparations" / (preparation_id + ".json")
    if path.exists() and json.loads(path.read_bytes()) != report:
        raise ValueError("release_preparation_conflict")
    if not path.exists():
        atomic_json(path, report)
    return {**report, "preparation_id": preparation_id}


class ReleaseLedger:
    def __init__(self, workspace):
        self.root = Path(workspace) / "releases/submissions"

    def _save(self, path, document):
        atomic_json(path, {**document, "sha256": identity(document)})

    def status(self, submission_id):
        if not re.fullmatch(r"[a-f0-9]{64}", submission_id):
            raise ValueError("release_submission_id_invalid")
        document = json.loads((self.root / (submission_id + ".json")).read_bytes())
        seal = document.pop("sha256", None)
        if identity(document) != seal or identity(document["scope"]) != submission_id:
            raise ValueError("release_receipt_integrity_failed")
        return document

    def submit(self, scope, *, send, refresh=None, reconcile=None):
        # The adapter supplies reviewed authentication/response handling. No credentials
        # are accepted in the scope or persisted by this state machine.
        if (type(scope) is not dict or set(scope) != {"service", "author_id", "archive_sha256"}
                or any(type(v) is not str for v in scope.values())
                or not re.fullmatch(r"[a-f0-9]{64}", scope["archive_sha256"])
                or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", scope["service"])
                or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", scope["author_id"])):
            raise ValueError("release_scope_invalid")
        submission_id = identity(scope)
        path = self.root / (submission_id + ".json")
        jobs = JobStore()
        job_id = jobs.start("release.submit", {"ledger": str(self.root.resolve()), "submission_id": submission_id})
        def persist(document):
            jobs.heartbeat(job_id)
            self._save(path, document)
        try:
            existed = path.exists()
            document = self.status(submission_id) if existed else {
                "document_type": "forge_release_receipt_v1", "submission_id": submission_id, "scope": scope,
                "receipt_state": "unknown", "qualification_state": "unknown", "release_id": None,
                "created_at": time.time(), "code": "release_receipt_unknown", "production_authority": False}
            if document["receipt_state"] != "accepted":
                # Persist unknown BEFORE sending: process termination must never cause
                # an implicit retry of an upload whose outcome could be accepted.
                persist(document)
                try:
                    receipt = reconcile(submission_id) if existed and reconcile is not None else None if existed else send(submission_id)
                except (OSError, ValueError):
                    receipt = None
                if receipt is not None:
                    if (type(receipt) is not dict or receipt.get("archive_sha256", "").lower() != scope["archive_sha256"]
                            or type(receipt.get("release_id")) is not str
                            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", receipt["release_id"])):
                        raise ValueError("release_receipt_binding_invalid")
                    document.update(receipt_state="accepted", release_id=receipt["release_id"], code=None, accepted_at=time.time())
                    persist(document)
            if document["receipt_state"] == "accepted" and refresh is not None:
                try:
                    observed = refresh(document["release_id"])
                    if (type(observed) is not dict or observed.get("release_id") != document["release_id"]
                            or observed.get("qualification_state") not in {"pending", "running", "passed", "failed"}):
                        raise ValueError("release_qualification_schema_invalid")
                    document.update(qualification_state=observed["qualification_state"], observed_at=time.time(), code=None)
                    document["last_successful_observation"] = {"qualification_state": observed["qualification_state"], "observed_at": document["observed_at"]}
                except (OSError, ValueError):
                    document.update(qualification_state="unknown", code="release_qualification_unavailable")
                persist(document)
            jobs.finish(job_id, "completed", {"submission_id": submission_id, "receipt_state": document["receipt_state"]})
            return document
        except BaseException:
            try:
                jobs.finish(job_id, "failed", {"code": "release_submission_interrupted"})
            except ValueError:
                pass
            raise
