"""Account-bound remote release operations, shared by CLI and SDK users."""
import os
from pathlib import Path
import re
import sys
import time


def add_auth_arguments(parser, *, profile=True):
    if profile:
        parser.add_argument('--profile', default='dojo')
    parser.add_argument('--origin', help='Required with an ephemeral API key; never overrides a saved profile.')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--api-key-stdin', action='store_true', help='Read API key without saving it.')
    source.add_argument('--api-key-env', metavar='NAME', help='Read the named environment variable without saving it.')


def authenticated_client(args):
    from .control_client import AccountStore, ControlClient
    stdin = getattr(args, 'api_key_stdin', False)
    env = getattr(args, 'api_key_env', None)
    origin = getattr(args, 'origin', None)
    if stdin or env:
        if not origin:
            raise ValueError('account_origin_required')
        # Validate origin before consuming a one-shot secret.
        from .control_client import normalize_origin
        normalize_origin(origin)
        token = sys.stdin.readline(1024).strip() if stdin else os.environ.get(env, '')
        return ControlClient(origin, token)
    if origin:
        raise ValueError('account_auth_source_required')
    return AccountStore().client(args.profile)


def _release_id(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}', value):
        raise ValueError('service_release_id_invalid')
    return value


def _owned(value, author, release_id=None):
    if type(value) is not dict or value.get('developer_id') != author:
        raise ValueError('release_account_binding_invalid')
    _release_id(value.get('release_id'))
    if release_id and value['release_id'] != release_id:
        raise ValueError('release_receipt_binding_invalid')
    return value


def list_releases(client, *, package_id=None):
    author = client.me()['developer_id']
    result = client.request('/v1/developer/releases')
    if type(result.get('items')) is not list:
        raise ValueError('service_response_invalid')
    rows = [_owned(row, author) for row in result['items']]
    return {'document_type': 'forge_remote_releases_v1', 'status': 'completed', 'origin': client.origin,
            'developer_id': author, 'items': [row for row in rows if package_id is None or row.get('package_id') == package_id]}


def release_detail(client, release_id):
    release_id = _release_id(release_id)
    author = client.me()['developer_id']
    return _owned(client.request('/v1/developer/releases/' + release_id), author, release_id)


def wait_release(client, release_id, *, timeout=300, interval=5):
    _release_id(release_id)
    if type(timeout) not in (int, float) or not 0 <= timeout <= 86400 or type(interval) not in (int, float) or not 1 <= interval <= 60:
        raise ValueError('release_wait_budget_invalid')
    deadline = time.monotonic() + timeout
    detail = None
    try:
        while True:
            detail = release_detail(client, release_id)
            state = detail.get('qualification_status')
            status = {'passed': 'passed', 'failed': 'failed', 'revoked': 'revoked'}.get(state)
            if status:
                break
            if state not in {'static_validated', 'qualification_pending'}:
                raise ValueError('release_qualification_state_unknown')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                status = 'timeout'
                break
            time.sleep(min(interval, remaining))
    except KeyboardInterrupt:
        status = 'cancelled'
    return {'document_type': 'forge_release_wait_v1', 'status': status, 'release_id': release_id,
            'receipt_state': 'accepted' if detail is not None else 'unknown',
            'release': detail, 'production_authority': False}


def download_release(client, release_id, output):
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('release_download_exists')
    detail = release_detail(client, release_id)
    return {**client.download('/v1/developer/releases/' + release_id + '/package', output,
                              detail.get('archive_sha256')), 'release_id': release_id}


def _require(client, capability):
    if client.capabilities()['capabilities'].get(capability) is not True:
        raise ValueError('service_capability_unavailable')


def set_participation(client, release_id, status):
    _release_id(release_id)
    if status not in {'eligible', 'paused'}:
        raise ValueError('release_participation_invalid')
    _require(client, 'release_participation')
    author = client.me()['developer_id']
    result = _owned(client.request('/v1/developer/releases/' + release_id + '/participation',
        method='POST', value={'participation_status': status}), author, release_id)
    if result.get('participation_status') != status:
        raise ValueError('release_participation_unknown')
    return result


def revoke_signing_key(client, key_id):
    if type(key_id) is not str or not re.fullmatch(r'signing-[a-f0-9]{24}', key_id):
        raise ValueError('release_signing_key_invalid')
    _require(client, 'signing_key_revocation')
    result = client.request('/v1/developer/signing-keys/' + key_id, method='DELETE')
    if result.get('status') != 'revoked':
        raise ValueError('release_signing_key_revocation_unknown')
    return {'status': 'revoked', 'key_id': key_id, 'existing_releases_deleted': False}


def revoke_current_api_key(client):
    _require(client, 'api_key_self_revocation')
    result = client.request('/v1/developer/api-keys/current', method='DELETE')
    if result.get('status') != 'revoked':
        raise ValueError('account_key_revocation_unknown')
    return {'status': 'revoked', 'remote_key_revoked': True}
