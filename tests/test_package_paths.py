"""Protect user data and personal overrides across the src migration."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from steam_library_toolkit.cli.node_runtime import prepare
from steam_library_toolkit.classification.overrides import load_overrides
from steam_library_toolkit.paths import SOURCE_ROOT


class PackagePathsTests(unittest.TestCase):
    def test_personal_rules_keep_the_old_filename(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            rules = {'schema_version': 1, 'apps': {'550': {'main_category': 'RPG', 'reason': 'Local preference'}}}
            (root / 'classification_overrides.local.json').write_text(json.dumps(rules), encoding='utf-8')
            with patch('steam_library_toolkit.classification.overrides.ROOT', root):
                result = load_overrides()
            self.assertEqual(result['550'], rules['apps']['550'])

    def test_node_setup_rejects_unmanaged_directory_without_changing_it(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            existing = root / 'package.json'
            existing.write_text('existing project', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'not managed'):
                prepare(root)
            self.assertEqual(existing.read_text(encoding='utf-8'), 'existing project')
            self.assertEqual(list(root.iterdir()), [existing])

    def test_managed_node_setup_uses_pinned_lock_and_can_repeat(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            prepare(root)
            before = {p.name: p.read_bytes() for p in root.iterdir()}
            prepare(root)
            self.assertEqual(before, {p.name: p.read_bytes() for p in root.iterdir()})
            self.assertNotIn('scripts', json.loads((root / 'package.json').read_bytes()))
            self.assertIn('steam-user', json.loads((root / 'package.json').read_bytes())['dependencies'])

    def test_source_node_setup_preserves_root_manifests(self):
        if SOURCE_ROOT is None:
            self.skipTest('source checkout only')
        before = (SOURCE_ROOT / 'package.json').read_bytes()
        self.assertEqual(prepare(SOURCE_ROOT), SOURCE_ROOT)
        self.assertEqual((SOURCE_ROOT / 'package.json').read_bytes(), before)
