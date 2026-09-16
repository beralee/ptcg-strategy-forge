"""Public HTTP control contract and OS-owned CLI credentials."""
import ctypes
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener

from .jobs import state_root
from .replays import NoRedirect, NetworkBudget, atomic_json


def normalize_origin(origin):
    try:
        parsed = urlsplit(origin)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in {'', '/'} or parsed.query or parsed.fragment
                or (parsed.scheme == 'http' and parsed.hostname not in {'localhost', '127.0.0.1', '::1'})):
            raise ValueError()
        port = parsed.port
    except (ValueError, TypeError):
        raise ValueError('service_origin_invalid') from None
    host = '[' + parsed.hostname + ']' if ':' in parsed.hostname else parsed.hostname
    return parsed.scheme + '://' + host + (':' + str(port) if port and port != {'http': 80, 'https': 443}[parsed.scheme] else '')


class ControlError(ValueError):
    def __init__(self, code, status=0):
        super().__init__(code)
        self.status = status


class ControlClient:
    def __init__(self, origin, token=None):
        self.origin = normalize_origin(origin)
        if token is not None and (type(token) is not str or not re.fullmatch(r'ptcgai_[A-Za-z0-9_-]{16,256}', token)):
            raise ValueError('account_credential_invalid')
        self.token = token

    def request(self, path, *, method='GET', value=None, body=None, headers=None, response_headers=False,
                binary=False, max_bytes=4 * 1024**2):
        if not path.startswith('/v1/') or path.startswith('//') or '\\' in path:
            raise ValueError('service_path_invalid')
        request_headers = {'Accept': 'application/json', **(headers or {})}
        if self.token:
            request_headers['Authorization'] = 'Bearer ' + self.token
        if value is not None:
            body = json.dumps(value).encode('utf-8')
            request_headers['Content-Type'] = 'application/json'
        request = Request(self.origin + path, data=body, method=method, headers=request_headers)
        budget = NetworkBudget(state_root())
        budget.register(self.origin, 4, 2)
        try:
            with budget.acquire(self.origin, 4, 2):
                try:
                    response = build_opener(NoRedirect()).open(request, timeout=45)
                except HTTPError as error:
                    response = error
                except ValueError:
                    raise ControlError('service_redirect_forbidden') from None
                with response:
                    data = response.read(max_bytes + 1)
                    if len(data) > max_bytes:
                        raise ControlError('service_response_budget_exceeded')
                    if response.status >= 400 or 300 <= response.status < 400:
                        try:
                            code = json.loads(data).get('error_code', '')
                        except (ValueError, AttributeError):
                            code = ''
                        if type(code) is not str or not re.fullmatch(r'(developer|release|ladder|api_key|signing_key|csrf|authentication|package)_[a-z_]{1,70}', code):
                            code = 'service_request_failed'
                        raise ControlError(code, response.status)
                    if binary:
                        if response.headers.get_content_type() != 'application/vnd.ptcgdap.ptcgai':
                            raise ControlError('release_download_content_type_invalid')
                        return data
                    try:
                        document = json.loads(data) if data else {}
                    except ValueError:
                        raise ControlError('service_response_invalid') from None
                    if type(document) is not dict:
                        raise ControlError('service_response_invalid')
                    return (document, dict(response.headers)) if response_headers else document
        except (OSError, URLError, TimeoutError):
            raise ControlError('service_connection_unknown') from None
        finally:
            budget.unregister()

    def download(self, path, output, digest, *, max_bytes=16 * 1024**2):
        """Verify the owner archive before atomically creating a non-overwriting file."""
        import os
        import tempfile
        output = Path(output)
        if output.exists() or output.is_symlink():
            raise ValueError('release_download_exists')
        if type(digest) is not str or not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
            raise ValueError('release_archive_identity_invalid')
        if type(max_bytes) is not int or not 1 <= max_bytes <= 16 * 1024**2:
            raise ValueError('release_download_budget_invalid')
        data = self.request(path, binary=True, max_bytes=max_bytes,
                            headers={'Accept': 'application/vnd.ptcgdap.ptcgai'})
        if hashlib.sha256(data).hexdigest() != digest.lower():
            raise ValueError('release_download_hash_mismatch')
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, output)
            except FileExistsError:
                raise ValueError('release_download_exists') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return {'status': 'downloaded', 'archive_sha256': digest.upper(),
                'bytes': len(data), 'output': str(output.resolve()), 'production_authority': False}

    def me(self):
        value = self.request('/v1/developer/me')
        if (type(value.get('developer_id')) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', value['developer_id'])
                or value.get('status') != 'active'):
            raise ValueError('account_identity_invalid')
        return {key: value[key] for key in ('developer_id', 'display_name', 'status') if key in value}

    def capabilities(self):
        value = self.request('/v1/developer/capabilities')
        if value.get('document_type') != 'forge_service_capabilities_v1' or value.get('schema_version') != 1 or type(value.get('capabilities')) is not dict:
            raise ValueError('service_capabilities_invalid')
        return {**value, 'origin': self.origin, 'verification': 'live_http_contract'}

    def receipt(self, digest):
        if not re.fullmatch(r'[0-9a-fA-F]{64}', digest):
            raise ValueError('release_archive_identity_invalid')
        value = self.request('/v1/developer/releases/by-archive/' + digest.lower())
        if value.get('archive_sha256', '').lower() != digest.lower() or value.get('receipt_state') != 'accepted':
            raise ValueError('release_receipt_binding_invalid')
        return value

    def login_password(self, login, password, *, username=False):
        if self.token:
            raise ValueError('account_login_mode_invalid')
        session, headers = self.request('/v1/auth/sessions', method='POST',
            value={'username' if username else 'email': login, 'password': password}, response_headers=True)
        cookie = next((v.split(';', 1)[0] for k, v in headers.items() if k.lower() == 'set-cookie'), '')
        if not re.fullmatch(r'ptcgdap_session=session_[A-Za-z0-9_-]+', cookie):
            raise ValueError('account_session_invalid')
        auth = {'Cookie': cookie, 'X-CSRF-Token': session.get('csrf_token', '')}
        try:
            key = self.request('/v1/developer/api-keys', method='POST', value={'label': 'Forge CLI'}, headers=auth)
            client = ControlClient(self.origin, key.get('secret'))
            if not client.token:
                raise ValueError('account_credential_invalid')
            return client
        finally:
            # The short-lived bootstrap browser session is never retained locally.
            try:
                self.request('/v1/auth/sessions/current', method='DELETE', headers=auth)
            except ValueError:
                pass


class WindowsCredentialVault:
    def _api(self):
        if sys.platform != 'win32':
            raise ValueError('account_credential_store_unavailable')
        from ctypes import wintypes as w
        class Credential(ctypes.Structure):
            _fields_ = [('Flags', w.DWORD), ('Type', w.DWORD), ('TargetName', w.LPWSTR),
                ('Comment', w.LPWSTR), ('LastWritten', w.FILETIME), ('CredentialBlobSize', w.DWORD),
                ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)), ('Persist', w.DWORD),
                ('AttributeCount', w.DWORD), ('Attributes', ctypes.c_void_p), ('TargetAlias', w.LPWSTR), ('UserName', w.LPWSTR)]
        api = ctypes.WinDLL('Advapi32.dll', use_last_error=True)
        api.CredWriteW.argtypes = [ctypes.POINTER(Credential), w.DWORD]
        api.CredReadW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.POINTER(ctypes.POINTER(Credential))]
        api.CredDeleteW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD]
        api.CredFree.argtypes = [ctypes.c_void_p]
        return api, Credential

    def put(self, key, value):
        api, Credential = self._api()
        raw = value.encode('utf-8')
        if len(raw) > 2400:
            raise ValueError('account_credential_invalid')
        blob = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
        credential = Credential(Type=1, TargetName='ptcg-forge-v1:' + key, CredentialBlobSize=len(raw),
                                CredentialBlob=blob, Persist=2, UserName='Forge CLI')
        if not api.CredWriteW(ctypes.byref(credential), 0):
            raise ValueError('account_credential_store_unavailable')

    def get(self, key):
        api, Credential = self._api()
        pointer = ctypes.POINTER(Credential)()
        if not api.CredReadW('ptcg-forge-v1:' + key, 1, 0, ctypes.byref(pointer)):
            raise ValueError('account_not_logged_in')
        try:
            return ctypes.string_at(pointer.contents.CredentialBlob, pointer.contents.CredentialBlobSize).decode('utf-8')
        finally:
            api.CredFree(pointer)

    def delete(self, key):
        api, _ = self._api()
        if not api.CredDeleteW('ptcg-forge-v1:' + key, 1, 0) and ctypes.get_last_error() != 1168:
            raise ValueError('account_credential_store_unavailable')


def register_public_key(client, path, label):
    import base64
    try:
        document = json.loads(Path(path).read_bytes())
        # This endpoint accepts the public-only document emitted by release-key.
        if set(document) - {'document_type', 'schema_version', 'algorithm', 'key_id', 'fingerprint_sha256', 'public_key_base64'}:
            raise ValueError()
        raw = base64.b64decode(document['public_key_base64'], validate=True)
        digest = hashlib.sha256(raw).hexdigest().upper()
        if (len(raw) != 32 or document.get('algorithm') != 'ed25519'
                or document.get('key_id') != 'signing-' + digest[:24].lower()
                or document.get('fingerprint_sha256') != digest):
            raise ValueError()
    except (OSError, KeyError, TypeError, ValueError):
        raise ValueError('release_public_key_invalid') from None
    existing = client.request('/v1/developer/signing-keys').get('items', [])
    for key in existing:
        if key.get('key_id') == document['key_id']:
            if key.get('status') != 'active' or key.get('public_key_hex') != raw.hex():
                raise ValueError('release_signing_key_conflict')
            return {'status': 'registered', 'key_id': document['key_id'], 'fingerprint_sha256': digest}
    result = client.request('/v1/developer/signing-keys', method='POST',
        value={'label': label, 'public_key_base64': document['public_key_base64']})
    if result.get('key_id') != document['key_id'] or result.get('status') != 'active':
        raise ValueError('release_signing_key_registration_unknown')
    return {'status': 'registered', 'key_id': document['key_id'], 'fingerprint_sha256': digest}


class AccountStore:
    def __init__(self, root=None, *, vault=None):
        self.root = Path(root) if root is not None else state_root()
        self.vault = vault or WindowsCredentialVault()

    def _path(self, profile):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,48}', profile):
            raise ValueError('account_profile_invalid')
        return self.root / 'profiles' / (profile + '.json')

    def _key(self, profile):
        self._path(profile)
        return hashlib.sha256((str(self.root.resolve()) + '/' + profile).encode()).hexdigest()

    def login(self, profile, client):
        path = self._path(profile)
        me = client.me()
        metadata = {'document_type': 'forge_account_profile_v1', 'profile': profile,
                    'origin': client.origin, 'developer_id': me['developer_id']}
        secret = json.dumps({**metadata, 'token': client.token})
        key = self._key(profile)
        try:
            previous = self.vault.get(key)
        except (ValueError, KeyError):
            previous = None
        self.vault.put(key, secret)
        try:
            atomic_json(path, metadata)
        except BaseException:
            self.vault.put(key, previous) if previous is not None else self.vault.delete(key)
            raise
        return {**metadata, 'status': 'authenticated', 'credential_storage': 'os_vault'}

    def client(self, profile='dojo'):
        try:
            metadata = json.loads(self._path(profile).read_bytes())
            secret = json.loads(self.vault.get(self._key(profile)))
        except (OSError, KeyError, ValueError):
            raise ValueError('account_not_logged_in') from None
        if {k: v for k, v in secret.items() if k != 'token'} != metadata:
            raise ValueError('account_profile_binding_invalid')
        return ControlClient(metadata['origin'], secret['token'])

    def logout(self, profile='dojo'):
        path = self._path(profile)
        self.vault.delete(self._key(profile))
        path.unlink(missing_ok=True)
        return {'status': 'logged_out', 'profile': profile, 'remote_key_revoked': False}
