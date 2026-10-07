"""Collection plans use synthetic generations; never access Steam storage or auth."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import steam_library_toolkit.cli.collections as sync
from steam_library_toolkit.storage.runs import publish_run, manifest_path, resolve_artifact
from support import ACCOUNT, run_bundle

ROOT = Path(__file__).resolve().parents[1]


def tree(root):
    return {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None
            for p in root.rglob('*')}


class CollectionPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'library.json'
        publish_run(self.source, *run_bundle('fixture'))
        self.pointer = manifest_path(self.source)
        self.directory = resolve_artifact(self.source).parent
        self.output = self.root / 'export' / 'plan.json'

    def mutate(self, name, change):
        """Refresh hash too, to exercise semantic guards beyond file integrity."""
        path = self.directory / name
        data = json.loads(path.read_bytes())
        change(data)
        path.write_text(json.dumps(data), encoding='utf-8')
        manifest = json.loads(self.pointer.read_bytes())
        manifest['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.pointer.write_text(json.dumps(manifest), encoding='utf-8')

    def cli(self, *flags):
        return subprocess.run([sys.executable, '-B', '-X', 'utf8',
            str(ROOT / 'steam_sync_collections.py'), '--input', str(self.source),
            '--account', ACCOUNT, '--output', str(self.output), *flags],
            cwd=self.root, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
            capture_output=True, text=True, encoding='utf-8', timeout=30)

    def test_legacy_loaders_distinguish_empty_unknown_and_subset(self):
        result = self.root / 'result.json'
        result.write_text('{"group": [1, 2]}', encoding='utf-8')
        classified = self.directory / 'steam_library_classified.json'
        with patch.object(sync, 'RESULT_JSON', result), patch.object(sync, 'CLASSIFIED_FILE', classified):
            for loader in (sync.load_collections_from_result_json, sync.load_classified_and_build_collections):
                self.assertEqual(loader([]), {})
                self.assertEqual({a for ids in loader(None).values() for a in ids}, {1, 2})
                self.assertEqual({a for ids in loader([2]).values() for a in ids}, {2})

    def test_invalid_ids_and_trimmed_name_collisions_are_rejected(self):
        for invalid in (True, 0, -1, 1.0, '01', 'x', 0x100000000):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'APPID_INVALID'):
                sync.filter_collections({'group': [invalid]}, [])
        with self.assertRaisesRegex(ValueError, 'NAME_COLLISION'):
            sync.filter_collections({'group': [], ' group ': [1]})

    def test_api_unavailable_is_not_a_confirmed_empty_library(self):
        for payload, expected in (({'response': {}}, None),
                                  ({'response': {'game_count': 0}}, []),
                                  ({'response': {'games': [{'appid': 1}]}}, [1])):
            response = Mock(status_code=200)
            response.json.return_value = payload
            with patch('steam_library_toolkit.cli.collect.get_response', return_value=response):
                self.assertEqual(sync.get_owned_appids_from_api('fixture', ACCOUNT), expected)

    def test_confirmed_empty_run_never_falls_back_to_legacy_members(self):
        empty = self.root / 'empty.json'
        publish_run(empty, *run_bundle('empty', ()))
        with (patch.object(sync, 'get_owned_appids_from_api', side_effect=AssertionError('API fallback')),
              patch.object(sync, 'load_collections_from_result_json', side_effect=AssertionError('flat fallback'))):
            plan, *_ = sync.build_plan(empty, ACCOUNT)
        self.assertEqual(plan['collections'], {})
        self.assertEqual(plan['eligible_appids'], [])
        self.assertEqual(plan['membership_count'], 0)

    def test_preview_and_dry_run_leave_existing_and_missing_outputs_untouched(self):
        for exists in (False, True):
            if exists:
                self.output.parent.mkdir()
                self.output.write_bytes(b'existing output sentinel')
            before = tree(self.root)
            for flags in ((), ('--dry-run',), ('--dry-run', '--export-only'),
                          ('--dry-run', '--write', '--export-only')):
                with self.subTest(exists=exists, flags=flags):
                    result = self.cli(*flags)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(tree(self.root), before)

    def test_old_write_and_unbound_sources_fail_without_creating_anything(self):
        before = tree(self.root)
        for flags, code in ((('--write',), 'WRITE_DISABLED'),
                            (('--write', '--export-only'), 'WRITE_DISABLED'),
                            (('--from-result', '--export-only'), 'LEGACY_SOURCE_DISABLED'),
                            (('--use-api', '--export-only'), 'LEGACY_SOURCE_DISABLED')):
            with self.subTest(flags=flags):
                result = self.cli(*flags)
                self.assertEqual(result.returncode, 1)
                self.assertIn(code, result.stderr)
                self.assertEqual(tree(self.root), before)

    def test_explicit_export_binds_account_run_and_game_only_members(self):
        rows, audit = run_bundle('mixed')
        rows[1]['app_type'] = 'application'
        mixed = self.root / 'mixed.json'
        publish_run(mixed, rows, audit)
        plan, pointer, before, directory = sync.build_plan(mixed, ACCOUNT)
        original = tree(self.root)
        self.source = mixed
        result = self.cli('--export-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads(self.output.read_bytes())
        self.assertEqual(saved['steam_id'], ACCOUNT)
        self.assertEqual(saved['run_id'], 'mixed')
        self.assertEqual(saved['membership_count'], 2)
        self.assertEqual(saved['eligible_appids'], [1])
        self.assertEqual({a for ids in saved['collections'].values() for a in ids}, {1})
        self.assertEqual(saved['source_manifest_sha256'], hashlib.sha256(before).hexdigest())
        self.assertFalse(saved['ownership_revalidated'])
        self.assertFalse(saved['write_supported'])
        self.assertTrue(saved['membership_observed_at'])
        self.assertTrue(all(tree(self.root)[key] == value for key, value in original.items()))

    def test_account_mismatch_or_plain_flat_input_rejected(self):
        with self.assertRaisesRegex(ValueError, 'ACCOUNT_MISMATCH'):
            sync.build_plan(self.source, '76561198000000002')
        flat = self.root / 'flat.json'
        flat.write_text('[]', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'VERIFIED_RUN_REQUIRED'):
            sync.build_plan(flat, ACCOUNT)
        for account in ('', '1', '76561197960265728', '99999999999999999'):
            with self.assertRaisesRegex(ValueError, 'ACCOUNT_INVALID'):
                sync.build_plan(self.source, account)

    def test_unverified_membership_and_suspicious_status_rejected(self):
        original = (self.directory / 'steam_library.audit.json').read_bytes()
        mutations = [lambda a: a.update(membership='candidate'),
                     lambda a: a.update(status='suspicious_change'),
                     lambda a: a['sources']['client_library'].update(status='error'),
                     lambda a: a['sources']['client_library'].update(state='partial'),
                     lambda a: a['sources']['client_library'].update(completeness={'verified': False})]
        for change in mutations:
            with self.subTest(change=change):
                self.mutate('steam_library.audit.json', lambda a: (a.clear(), a.update(json.loads(original)), change(a)))
                with self.assertRaises(ValueError):
                    sync.build_plan(self.source, ACCOUNT)

    def test_corruption_in_any_manifest_artifact_is_rejected(self):
        manifest = json.loads(self.pointer.read_bytes())
        for name in manifest['files']:
            path = self.directory / name
            original = path.read_bytes()
            path.write_bytes(original + b'\n')
            with self.subTest(name=name), self.assertRaises(ValueError):
                sync.build_plan(self.source, ACCOUNT)
            path.write_bytes(original)

    def test_classified_run_and_missing_or_foreign_members_rejected_even_with_valid_hash(self):
        name = 'steam_library_classified.json'
        original = json.loads((self.directory / name).read_bytes())
        mutations = [(lambda g: g[0].update(run_id='other'), 'RUN_MISMATCH'),
                     (lambda g: g.pop(), 'MEMBERSHIP_MISMATCH'),
                     (lambda g: g[0].update(appid='999'), 'MEMBERSHIP_MISMATCH')]
        for change, code in mutations:
            with self.subTest(code=code):
                self.mutate(name, lambda g: (g.clear(), g.extend(json.loads(json.dumps(original))), change(g)))
                with self.assertRaisesRegex(ValueError, code):
                    sync.build_plan(self.source, ACCOUNT)

    def test_changed_pointer_prevents_export(self):
        plan, pointer, before, directory = sync.build_plan(self.source, ACCOUNT)
        publish_run(self.source, *run_bundle('next', (3,)))
        with self.assertRaisesRegex(ValueError, 'GENERATION_CHANGED'):
            sync.export_plan(self.output, plan, pointer, before, directory)
        self.assertFalse(self.output.parent.exists())

    def test_export_refuses_input_generation_unrelated_file_or_other_account_plan(self):
        plan, pointer, before, directory = sync.build_plan(self.source, ACCOUNT)
        sentinel = self.root / 'sentinel.json'
        sentinel.write_text('{}', encoding='utf-8')
        other = self.root / 'other.json'
        other.write_text(json.dumps({**plan, 'steam_id': '76561198000000002'}), encoding='utf-8')
        previous = tree(self.root)
        for output in (self.source, pointer, directory / 'steam_library.json', sentinel, other):
            with self.subTest(output=output), self.assertRaisesRegex(ValueError, 'OUTPUT_CONFLICT'):
                sync.export_plan(output, plan, pointer, before, directory)
        self.assertEqual(tree(self.root), previous)

    def test_atomic_replace_failure_retains_existing_plan_and_removes_temporary(self):
        plan, pointer, before, directory = sync.build_plan(self.source, ACCOUNT)
        sync.export_plan(self.output, plan, pointer, before, directory)
        previous = tree(self.root)
        with patch('steam_library_toolkit.sources.reconcile.os.replace', side_effect=OSError('injected')):
            with self.assertRaises(OSError):
                sync.export_plan(self.output, {**plan, 'collections': {}}, pointer, before, directory)
        self.assertEqual(tree(self.root), previous)


if __name__ == '__main__':
    unittest.main()
