import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


class ControlWorkflowTests(unittest.TestCase):
    def test_cli_account_creation_and_wait_exit_codes_without_browser(self):
        from ptcg_strategy_forge import cli
        client = self.client()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'strategy'
            with patch('sys.argv', ['forge', 'workspace', 'create', str(target), '--account', '--package-id', 'dev.fixture']), \
                    patch('ptcg_strategy_forge.control_workflow.authenticated_client', return_value=client), \
                    patch('sys.stdout', new_callable=io.StringIO) as output:
                self.assertEqual(0, cli.main())
                json.loads(output.getvalue())
            manifest = json.loads((target / 'package/strategy_package.json').read_bytes())
            self.assertEqual('developer-fixture', manifest['author']['author_id'])
        for state, expected in [('passed', 0), ('failed', 2), ('qualification_pending', 2), ('revoked', 2)]:
            client.request.return_value['qualification_status'] = state
            with patch('sys.argv', ['forge', 'releases', 'wait', '--release-id', 'release-fixture', '--timeout', '0']), \
                    patch('ptcg_strategy_forge.control_workflow.authenticated_client', return_value=client), \
                    patch('sys.stdout', new_callable=io.StringIO):
                self.assertEqual(expected, cli.main())

    def test_current_key_revocation_does_not_accept_arbitrary_key_id(self):
        from ptcg_strategy_forge.control_workflow import revoke_current_api_key
        client = self.client()
        client.capabilities.return_value = {'capabilities': {'api_key_self_revocation': True}}
        client.request.return_value = {'status': 'revoked'}
        self.assertTrue(revoke_current_api_key(client)['remote_key_revoked'])
        client.request.assert_called_once_with('/v1/developer/api-keys/current', method='DELETE')

    def client(self):
        client = Mock(origin='https://example.com')
        client.me.return_value = {'developer_id': 'developer-fixture', 'display_name': 'Fixture'}
        client.request.return_value = {'release_id': 'release-fixture', 'developer_id': 'developer-fixture',
            'archive_sha256': hashlib.sha256(b'archive').hexdigest(), 'qualification_status': 'passed'}
        return client

    def test_wait_terminal_states_and_timeout_are_distinct(self):
        from ptcg_strategy_forge.control_workflow import wait_release
        client = self.client()
        self.assertEqual('passed', wait_release(client, 'release-fixture', timeout=0)['status'])
        client.request.return_value['qualification_status'] = 'failed'
        report = wait_release(client, 'release-fixture', timeout=0)
        self.assertEqual('failed', report['status'])
        self.assertEqual('accepted', report['receipt_state'])
        client.request.return_value['qualification_status'] = 'qualification_pending'
        self.assertEqual('timeout', wait_release(client, 'release-fixture', timeout=0)['status'])

    def test_wait_polls_only_get_and_can_be_cancelled(self):
        from ptcg_strategy_forge.control_workflow import wait_release
        client = self.client()
        passed = dict(client.request.return_value)
        client.request.side_effect = [{**passed, 'qualification_status': 'qualification_pending'}, passed]
        with patch('ptcg_strategy_forge.control_workflow.time.sleep'):
            self.assertEqual('passed', wait_release(client, 'release-fixture', interval=1)['status'])
        self.assertTrue(all(call.kwargs.get('method', 'GET') == 'GET' for call in client.request.call_args_list))
        client.request.side_effect = None
        client.request.return_value['qualification_status'] = 'qualification_pending'
        with patch('ptcg_strategy_forge.control_workflow.time.sleep', side_effect=KeyboardInterrupt):
            self.assertEqual('cancelled', wait_release(client, 'release-fixture', interval=1)['status'])

    def test_foreign_or_malformed_release_rejected_before_download(self):
        from ptcg_strategy_forge.control_workflow import release_detail, download_release
        client = self.client()
        for value in ['../other', '//host', 'x?secret=1', '']:
            with self.assertRaisesRegex(ValueError, 'service_release_id_invalid'):
                release_detail(client, value)
        client.request.return_value['developer_id'] = 'other'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'release_account_binding_invalid'):
                download_release(client, 'release-fixture', Path(tmp) / 'a.ptcgai')
        client.download.assert_not_called()

    def test_list_is_owned_and_filterable(self):
        from ptcg_strategy_forge.control_workflow import list_releases
        client = self.client()
        row = dict(client.request.return_value, package_id='dev.fixture')
        client.request.return_value = {'items': [row, dict(row, package_id='dev.other')]}
        self.assertEqual([row], list_releases(client, package_id='dev.fixture')['items'])
        client.request.return_value['items'][0]['developer_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'release_account_binding_invalid'):
            list_releases(client)

    def test_participation_and_revoke_require_live_capability(self):
        from ptcg_strategy_forge.control_workflow import set_participation, revoke_signing_key
        client = self.client()
        client.capabilities.return_value = {'capabilities': {}}
        with self.assertRaisesRegex(ValueError, 'service_capability_unavailable'):
            set_participation(client, 'release-fixture', 'paused')
        with self.assertRaisesRegex(ValueError, 'service_capability_unavailable'):
            revoke_signing_key(client, 'signing-' + 'a' * 24)
        client.request.assert_not_called()
        client.capabilities.return_value['capabilities'] = {'release_participation': True, 'signing_key_revocation': True}
        client.request.return_value['participation_status'] = 'paused'
        self.assertEqual('paused', set_participation(client, 'release-fixture', 'paused')['participation_status'])
        self.assertEqual({'participation_status': 'paused'}, client.request.call_args.kwargs['value'])

    def test_ephemeral_stdin_auth_does_not_touch_vault_and_requires_origin(self):
        from ptcg_strategy_forge.control_workflow import authenticated_client
        args = SimpleNamespace(api_key_stdin=True, origin='https://example.com', profile='dojo', api_key_env=None)
        with patch('sys.stdin', io.StringIO('ptcgai_fixture_ephemeral_credential\n')), patch('ptcg_strategy_forge.control_client.AccountStore') as store:
            client = authenticated_client(args)
            self.assertEqual(args.origin, client.origin)
            store.assert_not_called()
        args.origin = None
        with self.assertRaisesRegex(ValueError, 'account_origin_required'):
            authenticated_client(args)

    def test_ephemeral_env_is_explicit_and_does_not_fallback(self):
        from ptcg_strategy_forge.control_workflow import authenticated_client
        args = SimpleNamespace(api_key_stdin=False, origin='https://example.com', profile='dojo', api_key_env='FORGE_TEST_KEY')
        with patch.dict(os.environ, {'FORGE_TEST_KEY': 'ptcgai_fixture_environment_credential'}):
            self.assertTrue(authenticated_client(args).token)
        args.api_key_env = 'FORGE_MISSING_TEST_KEY'
        with self.assertRaisesRegex(ValueError, 'account_credential_invalid'):
            authenticated_client(args)
        args.api_key_env = None
        with self.assertRaisesRegex(ValueError, 'account_auth_source_required'):
            authenticated_client(args)

    def test_binary_download_is_verified_non_overwriting_and_redirect_safe(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        from ptcg_strategy_forge.control_client import ControlClient
        body = b'archive'
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.path)
                self.send_response(302 if self.path.endswith('redirect') else 200)
                self.send_header('Content-Type', 'application/vnd.ptcgdap.ptcgai')
                self.send_header('Location', '/v1/sink')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = ControlClient('http://127.0.0.1:' + str(server.server_port), 'ptcgai_fixture_download_credential')
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp) / 'a.ptcgai'
                digest = hashlib.sha256(body).hexdigest()
                client.download('/v1/package', target, digest)
                self.assertEqual(body, target.read_bytes())
                with self.assertRaisesRegex(ValueError, 'release_download_exists'):
                    client.download('/v1/package', target, digest)
                for route, expected, limit, error in [('/v1/package', '0'*64, 99, 'release_download_hash_mismatch'),
                        ('/v1/package', digest, 2, 'service_response_budget_exceeded'),
                        ('/v1/redirect', digest, 99, 'service_redirect_forbidden')]:
                    other = Path(tmp) / 'bad.ptcgai'
                    with self.assertRaisesRegex(ValueError, error):
                        client.download(route, other, expected, max_bytes=limit)
                    self.assertFalse(other.exists())
                self.assertNotIn('/v1/sink', seen)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
