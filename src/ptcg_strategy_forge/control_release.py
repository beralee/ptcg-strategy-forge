"""Account-bound signing and submission over the public control HTTP contract."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

from .control_client import ControlError
from .lineage import acceptance
from .release_signing import _public_identity
from .release_workflow import ReleaseLedger
from tools.ptcgdap.build_author_strategy_package import _read_private_key, build_package_bytes
from scripts.ai.ptcgdap.author_strategy_package import AuthorStrategyPackageLoader


def refresh_release(workspace, client, submission_id):
    ledger = ReleaseLedger(workspace.root)
    previous = ledger.status(submission_id)
    scope = previous['scope']
    expected_service = 'dojo-' + hashlib.sha256(client.origin.encode()).hexdigest()
    if scope['service'] != expected_service or scope['author_id'] != client.me()['developer_id']:
        raise ValueError('release_account_binding_invalid')
    def lookup(_):
        value = client.receipt(scope['archive_sha256'])
        if value.get('developer_id', scope['author_id']) != scope['author_id']:
            raise ValueError('release_receipt_binding_invalid')
        return value
    return ledger.submit(scope, send=lambda _: None, reconcile=lookup, refresh=lookup)


def prepare_authenticated_release(workspace, client, public_key_path):
    from .release_workflow import prepare_release
    from .replays import atomic_json, identity
    me = client.me()
    report = prepare_release(workspace, me['developer_id'], public_key_path)
    keys = client.request('/v1/developer/signing-keys').get('items', [])
    matches = [key for key in keys if key.get('key_id') == report['signing_key_id']
               and key.get('status') == 'active' and key.get('fingerprint_sha256') == report['signing_key_fingerprint_sha256']]
    if len(matches) != 1:
        raise ValueError('release_signing_key_not_registered')
    local_preparation_id = report.pop('preparation_id')
    report = {**report, 'document_type': 'forge_authenticated_release_preparation_v1',
        'local_preparation_id': local_preparation_id, 'origin': client.origin,
        'registration_verified': True, 'account_identity_source': 'authenticated_control_http'}
    preparation_id = identity(report)
    atomic_json(workspace.root / 'releases/preparations' / (preparation_id + '.json'), report)
    return {**report, 'preparation_id': preparation_id}


def submit_release(workspace, client, private_key_path, *, retry_unaccepted=False):
    caps = client.capabilities()['capabilities']
    if (caps.get('release_idempotency') != 'archive_sha256_v1'
            or caps.get('release_reconciliation') != 'archive_sha256_v1'):
        raise ValueError('release_service_contract_unavailable')
    current = acceptance(workspace.root, workspace.default_artifact, workspace.default_report)
    if current['status'] != 'current':
        raise ValueError('release_acceptance_stale')
    account = client.me()
    original = workspace.default_artifact.read_bytes()
    package = AuthorStrategyPackageLoader().load_bytes(original)
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        payloads = {name: archive.read(name) for name in archive.namelist()
                    if name not in {'files.sha256.json', 'signature.json'}}
    manifest = json.loads(payloads['strategy_package.json'])
    if manifest['author']['author_id'] != account['developer_id']:
        raise ValueError('release_author_identity_mismatch')
    private = _read_private_key(Path(private_key_path))
    public, fingerprint, key_id = _public_identity(private)
    keys = client.request('/v1/developer/signing-keys').get('items', [])
    registered = [k for k in keys if k.get('key_id') == key_id and k.get('status') == 'active'
                  and k.get('public_key_hex') == public.hex()]
    if len(registered) != 1:
        raise ValueError('release_signing_key_not_registered')
    body = build_package_bytes(payloads, private, key_id=key_id)
    del private
    if len(body) > caps.get('max_upload_bytes', 16 * 1024**2):
        raise ValueError('release_upload_budget_exceeded')
    if acceptance(workspace.root, workspace.default_artifact, workspace.default_report) != current:
        raise ValueError('release_acceptance_stale')
    digest = hashlib.sha256(body).hexdigest()
    path = workspace.root / 'releases/archives' / (digest + '.ptcgai')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as stream:
            stream.write(body)
    except FileExistsError:
        if path.read_bytes() != body:
            raise ValueError('release_archive_collision')
    service = 'dojo-' + hashlib.sha256(client.origin.encode()).hexdigest()
    scope = {'service': service, 'author_id': account['developer_id'], 'archive_sha256': digest}
    failures = []

    def lookup():
        receipt = client.receipt(digest)
        if receipt.get('developer_id', account['developer_id']) != account['developer_id']:
            raise ValueError('release_receipt_binding_invalid')
        return receipt

    def upload():
        try:
            return client.request('/v1/developer/releases', method='POST', body=body,
                headers={'Content-Type': 'application/vnd.ptcgdap.ptcgai', 'Idempotency-Key': 'sha256:' + digest})
        except ControlError as error:
            failures.append({'code': str(error), 'http_status': error.status})
            raise

    def reconcile(_id, *, first=False):
        try:
            return lookup()
        except ControlError as error:
            if error.status == 404 and (first or retry_unaccepted):
                return upload()
            failures.append({'code': str(error), 'http_status': error.status})
            raise

    result = ReleaseLedger(workspace.root).submit(scope,
        send=lambda sid: reconcile(sid, first=True), reconcile=reconcile,
        refresh=lambda _rid: lookup())
    return {**result, 'status': 'completed' if result['receipt_state'] == 'accepted' else 'failed',
            'origin': client.origin, 'archive_path': str(path), 'signing_key_id': key_id,
            'source_archive_sha256': package.archive_sha256, 'transport_errors': failures}
