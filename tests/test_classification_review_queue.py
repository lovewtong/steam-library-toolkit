import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import steam_review_classification as review
from steam_runs import manifest_path, publish_run, resolve_artifact
from test_phase_two import run_bundle

ROOT = Path(__file__).resolve().parents[1]


class ClassificationReviewQueueTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'library.json'
        rows, audit = run_bundle('review-fixture', tuple(range(1001, 1007)))
        for row, name, genres in zip(rows, ['BioShock', 'Unfamiliar', 'Reviewed', 'Fixture', 'BioShock', 'Tool'],
                                     [['Action'], [], ['Action'], ['RPG'], ['Shooter'], []]):
            row.update(name=name, genres=genres)
        rows[-1]['app_type'] = 'application'
        self.rules = {'1003': {'main_category': '动作/冒险', 'reason': 'Synthetic reviewed primary'}}
        with patch('classification_overrides.load_overrides', return_value=self.rules):
            publish_run(self.source, rows, audit)
        self.pointer = manifest_path(self.source)
        self.directory = resolve_artifact(self.source).parent

    def mutate(self, name, change):
        path = self.directory / name
        data = json.loads(path.read_bytes())
        change(data)
        path.write_text(json.dumps(data), encoding='utf-8')
        manifest = json.loads(self.pointer.read_bytes())
        manifest['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.pointer.write_text(json.dumps(manifest), encoding='utf-8')

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_priorities_overlap_and_saved_values_without_reclassification(self):
        before = self.snapshot()
        with patch('classification_overrides.load_overrides', side_effect=AssertionError('Current rules forbidden')), \
             patch('classify_steam_games.classify_one', side_effect=AssertionError('Reclassification forbidden')):
            report, *_ = review.build_review(self.source)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(report['summary']['games'], 5)
        self.assertEqual(report['summary']['queued'], 4)
        self.assertEqual([i['appid'] for i in report['items']], [1001, 1002, 1005, 1004])
        self.assertEqual([i['priority'] for i in report['items']], [1, 1, 2, 3])
        self.assertEqual(report['summary']['reason_counts'], {
            'primary_disagreement': 1, 'primary_unreviewed': 4, 'name_heuristic': 2, 'primary_unknown': 1})
        item = report['items'][0]
        self.assertEqual(item['table']['mapped_primary'], '动作/冒险')
        self.assertEqual(item['picker']['analysis']['primary'], '射击 (FPS/TPS)')
        self.assertEqual(report['source_manifest_sha256'], hashlib.sha256(self.pointer.read_bytes()).hexdigest())
        self.assertNotIn('steam_id', report)
        self.assertNotIn('suggested_override', item)

    def test_missing_legacy_evidence_is_queued_without_claiming_review(self):
        self.mutate('steam_library_classified.json', lambda games: games[2].pop('classification_evidence'))
        report, *_ = review.build_review(self.pointer)
        item = next(i for i in report['items'] if i['appid'] == 1003)
        self.assertIn('evidence_missing', item['reasons'])
        self.assertEqual(item['priority'], 1)
        self.assertEqual(item['applied_override'], self.rules['1003'])
        self.assertEqual(item['picker']['evidence'], {'fields': {}})

    def test_manual_correction_rebuild_clears_resolved_item_and_keeps_old_run(self):
        from steam_reclassify import reclassify
        before = self.snapshot()
        corrected = self.root / 'corrected.json'
        rules = {**self.rules, '1001': {'main_category': '射击', 'reason': 'Synthetic manual review'}}
        with patch('classification_overrides.load_overrides', return_value=rules):
            reclassify(self.source, corrected)
        report, *_ = review.build_review(corrected)
        self.assertNotIn(1001, {item['appid'] for item in report['items']})
        old, *_ = review.build_review(self.source)
        self.assertIn(1001, {item['appid'] for item in old['items']})
        self.assertTrue(all(self.snapshot()[k] == v for k, v in before.items()))

    def test_corruption_and_semantic_cross_run_or_member_changes_rejected(self):
        name = 'classified.json'
        original = (self.directory / name).read_bytes()
        manifest = self.pointer.read_bytes()
        for mutate in (lambda rows: rows[0].update(run_id='wrong'), lambda rows: rows.pop(),
                       lambda rows: rows[0].update(appid=999), lambda rows: rows.append(rows[0])):
            (self.directory / name).write_bytes(original)
            self.pointer.write_bytes(manifest)
            self.mutate(name, mutate)
            with self.assertRaisesRegex(ValueError, 'REVIEW_'):
                review.build_review(self.source)
        (self.directory / name).write_bytes(original + b' ')
        self.pointer.write_bytes(manifest)
        with self.assertRaisesRegex(ValueError, 'GENERATION_INVALID'):
            review.build_review(self.source)

    def test_wrong_account_and_unverified_membership_rejected(self):
        name = 'steam_library.audit.json'
        original = (self.directory / name).read_bytes()
        manifest = self.pointer.read_bytes()
        for change in (lambda audit: audit.update(steam_id='76561198000000002'),
                       lambda audit: audit.update(membership='candidate'),
                       lambda audit: audit.update(status='suspicious_change'),
                       lambda audit: audit['sources']['client_library'].update(state='partial')):
            (self.directory / name).write_bytes(original)
            self.pointer.write_bytes(manifest)
            self.mutate(name, change)
            with self.assertRaises(ValueError):
                review.build_review(self.source)

    def test_empty_verified_library_and_plain_file(self):
        empty = self.root / 'empty.json'
        publish_run(empty, *run_bundle('empty', ()))
        report, *_ = review.build_review(empty)
        self.assertEqual(report['summary'], {'games': 0, 'queued': 0, 'not_queued': 0, 'reason_counts': {}})
        flat = self.root / 'flat.json'
        flat.write_text('[]', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'VERIFIED_RUN_REQUIRED'):
            review.build_review(flat)

    def test_pointer_switch_during_read_and_before_export_rejected(self):
        original_resolver = review.resolve_artifact
        def switch(pointer):
            result = original_resolver(pointer)
            publish_run(self.source, *run_bundle('next', (1001,)))
            return result
        with patch.object(review, 'resolve_artifact', side_effect=switch):
            with self.assertRaisesRegex(ValueError, 'GENERATION_CHANGED'):
                review.build_review(self.source)
        args = review.build_review(self.source)
        publish_run(self.source, *run_bundle('last', (1001,)))
        output = self.root / 'export' / 'review.json'
        with self.assertRaisesRegex(ValueError, 'GENERATION_CHANGED'):
            review.export_review(output, *args)
        self.assertFalse(output.parent.exists())

    def test_export_conflicts_and_atomic_failure_do_not_damage_files(self):
        args = review.build_review(self.source)
        output = self.root / 'review.json'
        review.export_review(output, *args)
        before = self.snapshot()
        for path in (self.source, self.pointer, output, self.directory / 'extra.json',
                     self.root / 'new.current.json', ROOT / 'classification_overrides.local.json'):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'OUTPUT_CONFLICT'):
                review.export_review(path, *args)
        with patch('steam_review_classification.os.link', side_effect=OSError('injected')):
            with self.assertRaises(OSError):
                review.export_review(self.root / 'failed.json', *args)
        self.assertEqual(self.snapshot(), before)

    def test_missing_compatibility_library_is_still_a_reserved_output(self):
        args = review.build_review(self.pointer)
        # A valid generation can exist even when its convenience copy was not written.
        self.source.unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'OUTPUT_CONFLICT'):
            review.export_review(self.source, *args)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(review.build_review(self.pointer)[0]['summary']['games'], 5)

    def test_file_created_after_precheck_is_never_overwritten(self):
        args = review.build_review(self.source)
        output = self.root / 'competing.json'
        original_fsync = os.fsync
        def create_competing_file(fd):
            original_fsync(fd)
            output.write_bytes(b'unrelated concurrent data')
        with patch('os.fsync', side_effect=create_competing_file):
            with self.assertRaises(FileExistsError):
                review.export_review(output, *args)
        self.assertEqual(output.read_bytes(), b'unrelated concurrent data')
        self.assertFalse(list(self.root.glob('competing.json.*.tmp')))

    def test_concurrent_exports_have_exactly_one_winner(self):
        args = review.build_review(self.source)
        output = self.root / 'concurrent.json'
        ready = threading.Barrier(2)
        original_fsync = os.fsync
        def wait_until_both_prechecks_passed(fd):
            original_fsync(fd)
            ready.wait(timeout=5)
        def export(index):
            try:
                review.export_review(output, {**args[0], 'test_writer': index}, *args[1:])
                return index
            except FileExistsError:
                return None
        with patch('os.fsync', side_effect=wait_until_both_prechecks_passed):
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(export, (1, 2)))
        winners = [value for value in outcomes if value is not None]
        self.assertEqual(len(winners), 1)
        self.assertEqual(json.loads(output.read_bytes())['test_writer'], winners[0])
        self.assertFalse(list(self.root.glob('concurrent.json.*.tmp')))

    def test_cli_preview_is_read_only_and_limit_does_not_truncate_export(self):
        command = [sys.executable, '-B', '-X', 'utf8', str(ROOT / 'steam_review_classification.py'),
                   '--input', str(self.source), '--limit', '0']
        before = self.snapshot()
        result = subprocess.run(command, cwd=self.root, capture_output=True, text=True, encoding='utf-8', timeout=20,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('4/5', result.stdout)
        self.assertNotIn('P1 AppID', result.stdout)
        self.assertEqual(self.snapshot(), before)
        output = self.root / 'queue.json'
        result = subprocess.run(command + ['-o', str(output)], cwd=self.root, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(output.read_bytes())['items']), 4)
        self.assertTrue(all(self.snapshot()[k] == v for k, v in before.items()))


if __name__ == '__main__':
    unittest.main()
