"""Filesystem containment at the tensorization entrypoint (no training)."""

import ctypes
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from tests.test_competitive_forge_v2 import _frame, GRIMMSNARL, MORGREM, DARK_ENERGY
from ptcg_strategy_forge.sdk import StrategyWorkspace, WorkspaceError, WorkspaceModel


class WorkspaceTensorizePathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name).resolve()
        self.root = self.parent / 'long workspace directory'
        (self.root / 'package/deck').mkdir(parents=True)
        (self.root / 'package/deck/deck_manifest.json').write_text(json.dumps({
            'cards': [{'local_card_uid': uid} for uid in (GRIMMSNARL, MORGREM, DARK_ENERGY)]
        }), encoding='utf-8')
        self.scenario = self.root / 'frame.json'
        self.scenario.write_text(json.dumps(_frame()), encoding='utf-8')
        self.model = WorkspaceModel(StrategyWorkspace(self.root))

    def assert_rejected(self, scenario):
        with self.assertRaises(WorkspaceError) as caught:
            self.model.tensorize(scenario)
        self.assertEqual(caught.exception.code, 'workspace_scenario_invalid')
        self.assertFalse((self.root / 'build').exists())

    def test_relative_root_resolves_to_same_workspace(self):
        # Keep the relative-root fixture on the cwd volume (CI can use two drives).
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            absolute = Path(directory) / 'workspace'
            shutil.copytree(self.root, absolute)
            root = absolute.relative_to(Path.cwd())
            model = WorkspaceModel(StrategyWorkspace(root))
            report = model.tensorize('frame.json')
            self.assertEqual(report['status'], 'written')
            self.assertEqual(Path(report['output']), absolute.resolve() / 'build/frame-tensors.json')

    def test_absolute_scenario_inside_workspace(self):
        self.assertEqual(self.model.tensorize(self.scenario)['status'], 'written')

    @unittest.skipUnless(os.name == 'nt', 'Windows 8.3 path alias')
    def test_windows_short_root_resolves_to_same_workspace(self):
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetShortPathNameW(str(self.root), buffer, len(buffer))
        if not length or length >= len(buffer) or buffer.value.casefold() == str(self.root).casefold():
            self.skipTest('8.3 short names unavailable on this volume')
        model = WorkspaceModel(StrategyWorkspace(Path(buffer.value)))
        self.assertEqual(model.tensorize('frame.json')['status'], 'written')

    def test_parent_traversal_and_absolute_sibling_are_rejected(self):
        sibling = self.parent / (self.root.name + '-outside')
        sibling.mkdir()
        outside = sibling / 'frame.json'
        outside.write_bytes(self.scenario.read_bytes())
        for scenario in (outside, Path('..') / sibling.name / 'frame.json'):
            with self.subTest(scenario=scenario):
                self.assert_rejected(scenario)

    def test_missing_and_malformed_paths_are_rejected(self):
        for scenario in ('missing.json', 'bad\x00path.json'):
            with self.subTest(scenario=scenario):
                self.assert_rejected(scenario)

    def test_symlink_escape_is_rejected(self):
        outside = self.parent / 'outside.json'
        outside.write_bytes(self.scenario.read_bytes())
        link = self.root / 'escape.json'
        try:
            link.symlink_to(outside)
        except OSError as error:
            self.skipTest(f'symlinks unavailable: {error}')
        self.assert_rejected(link)

    def test_symlinked_parent_escape_is_rejected(self):
        outside = self.parent / 'outside'
        outside.mkdir()
        (outside / 'frame.json').write_bytes(self.scenario.read_bytes())
        link = self.root / 'escape'
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f'symlinks unavailable: {error}')
        self.assert_rejected(link / 'frame.json')

    @unittest.skipUnless(os.name == 'nt', 'Windows junction')
    def test_junction_escape_is_rejected(self):
        import _winapi
        outside = self.parent / 'outside'
        outside.mkdir()
        (outside / 'frame.json').write_bytes(self.scenario.read_bytes())
        link = self.root / 'junction'
        _winapi.CreateJunction(str(outside), str(link))
        self.assert_rejected(link / 'frame.json')
