import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


class ControlClientTests(unittest.TestCase):
    def test_authenticated_redirect_never_forwards_credentials(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        from ptcg_strategy_forge.control_client import ControlClient, ControlError
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.path)
                self.send_response(302)
                self.send_header('Location', '/v1/credential-sink')
                self.send_header('Content-Length', '0')
                self.end_headers()
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = ControlClient('http://127.0.0.1:' + str(server.server_port), 'ptcgai_fixture_credential_redirect')
            with self.assertRaises(ControlError): client.me()
            self.assertEqual(['/v1/developer/me'], seen)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_submit_signs_only_current_accepted_payload_and_uses_exact_receipt(self):
        from ptcg_strategy_forge import StrategyWorkspace
        from ptcg_strategy_forge.control_release import submit_release
        from ptcg_strategy_forge.release_signing import generate_release_key
        from tools.ptcgdap.author_strategy_developer import build_development_package
        from unittest.mock import patch
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = StrategyWorkspace.create(root / 'deck', author_id='dev.example')
            def check(source, *, output):
                build_development_package(source / 'package', output)
                return {'status': 'passed', 'artifact': {'path': str(output)}}
            with patch('ptcg_strategy_forge.application.check_workspace', side_effect=check): workspace.build()
            key_report = generate_release_key(root / 'private.key', root / 'public.json')
            public = json.loads((root / 'public.json').read_bytes())
            import base64
            client = Mock()
            client.origin = 'https://example.com'
            client.me.return_value = {'developer_id': 'dev.example'}
            client.capabilities.return_value = {'capabilities': {'release_idempotency': 'archive_sha256_v1', 'release_reconciliation': 'archive_sha256_v1', 'max_upload_bytes': 16777216}}
            calls = []
            def request(path, **kwargs):
                if path.endswith('/signing-keys'):
                    return {'items': [{'key_id': public['key_id'], 'public_key_hex': base64.b64decode(public['public_key_base64']).hex(),
                        'fingerprint_sha256': public['fingerprint_sha256'], 'status': 'active'}]}
                calls.append(kwargs['body'])
                digest = hashlib.sha256(kwargs['body']).hexdigest()
                return {'release_id': 'release-' + digest[:40], 'archive_sha256': digest}
            client.request.side_effect = request
            from ptcg_strategy_forge.control_client import ControlError
            def receipt(digest):
                if not calls: raise ControlError('ladder_release_not_found', 404)
                return {'release_id': 'release-' + digest[:40], 'archive_sha256': digest, 'qualification_state': 'pending', 'receipt_state': 'accepted'}
            client.receipt.side_effect = receipt
            from ptcg_strategy_forge.control_release import prepare_authenticated_release
            prepared = prepare_authenticated_release(workspace, client, root / 'public.json')
            self.assertTrue(prepared['registration_verified'])
            self.assertEqual('authenticated_control_http', prepared['account_identity_source'])
            first = submit_release(workspace, client, root / 'private.key')
            second = submit_release(workspace, client, root / 'private.key')
            self.assertEqual('accepted', first['receipt_state'])
            self.assertEqual(first['release_id'], second['release_id'])
            self.assertEqual(1, len(calls))
            self.assertEqual('pending', second['qualification_state'])
            from ptcg_strategy_forge.control_release import refresh_release
            self.assertEqual('accepted', refresh_release(workspace, client, second['submission_id'])['receipt_state'])
            self.assertEqual(1, len(calls))
            client.origin = 'https://elsewhere.example'
            with self.assertRaisesRegex(ValueError, 'release_account_binding_invalid'):
                refresh_release(workspace, client, second['submission_id'])
            client.origin = 'https://example.com'
            client.me.return_value = {'developer_id': 'wrong.author'}
            with self.assertRaisesRegex(ValueError, 'release_author_identity_mismatch'):
                submit_release(workspace, client, root / 'private.key')
            self.assertEqual(1, len(calls))

    def test_origin_and_credentials_fail_before_network(self):
        from ptcg_strategy_forge.control_client import ControlClient
        for origin in ['http://example.com', 'https://user:pass@example.com', 'https://example.com/path', 'https://example.com?q=secret']:
            with self.assertRaisesRegex(ValueError, 'service_origin_invalid'):
                ControlClient(origin)
        with self.assertRaisesRegex(ValueError, 'account_credential_invalid'):
            ControlClient('https://example.com', token='ptcgai_bad\r\nInjected: 1')

    def test_profile_is_origin_bound_and_logout_erases_only_its_credential(self):
        from ptcg_strategy_forge.control_client import AccountStore
        secrets = {}
        class Vault:
            def put(self, key, value): secrets[key] = value
            def get(self, key): return secrets[key]
            def delete(self, key): secrets.pop(key, None)
        with tempfile.TemporaryDirectory() as temp:
            store = AccountStore(Path(temp), vault=Vault())
            client = Mock()
            client.origin = 'https://example.com'
            client.token = 'ptcgai_fixture_secret_never_in_metadata'
            client.me.return_value = {'developer_id': 'dev.example', 'display_name': 'Example', 'status': 'active'}
            store.login('dojo', client)
            contents = ''.join(p.read_text() for p in Path(temp).rglob('*.json'))
            self.assertNotIn(client.token, contents)
            self.assertEqual('https://example.com', store.client('dojo').origin)
            self.assertEqual(client.token, store.client('dojo').token)
            profile = Path(temp) / 'profiles/dojo.json'
            document = json.loads(profile.read_text())
            document['origin'] = 'https://elsewhere.example'
            profile.write_text(json.dumps(document))
            with self.assertRaises(ValueError): store.client('dojo')
            store.logout('dojo')
            self.assertFalse(secrets)
            self.assertFalse(profile.exists())

    @unittest.skipUnless(sys.platform == 'win32', 'Windows credential manager')
    def test_windows_vault_roundtrip_and_delete(self):
        from ptcg_strategy_forge.control_client import WindowsCredentialVault
        import uuid
        vault = WindowsCredentialVault()
        key = 'test-' + str(uuid.uuid4())
        try:
            vault.put(key, 'ptcgai_fixture_credential_roundtrip')
            self.assertEqual('ptcgai_fixture_credential_roundtrip', vault.get(key))
        finally:
            vault.delete(key)
        with self.assertRaisesRegex(ValueError, 'account_not_logged_in'):
            vault.get(key)
