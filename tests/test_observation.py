import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from steam_observation import attach_first_seen, first_seen_fields, matches_first_seen
from steam_runs import publish_run, manifest_path, load_library, resolve_artifact
from steam_sources import AccountMismatchError
from steam_picker_server import PickerLibrary
from steam_sync_collections import build_plan
from steam_reclassify import reclassify
from steam_enrich import enrich
from steam_metadata import parse_fields
from support import run_bundle, ACCOUNT


def bundle(run, ids, at):
    rows, audit = run_bundle(run, ids)
    audit['sources']['client_library']['fetched_at'] = at
    return rows, audit


class ObservationTests(unittest.TestCase):
    def test_repeated_removed_and_reappearing_apps_keep_first_date(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'library.json'
            for run, ids, at in [('one', (1,), '2026-01-01T00:00:00Z'),
                                  ('two', (1, 2), '2026-02-01T00:00:00Z'),
                                  ('three', (2,), '2026-03-01T00:00:00Z'),
                                  ('four', (1, 2), '2026-04-01T00:00:00Z')]:
                rows, audit = bundle(run, ids, at)
                attach_first_seen(output, rows, audit)
                publish_run(output, rows, audit)
            rows = load_library(output)
            self.assertEqual([r['first_seen_at'][:7] for r in rows], ['2026-01', '2026-02'])
            self.assertEqual(rows[0]['first_seen_evidence']['run_id'], 'one')

    def test_same_account_saved_snapshot_seeds_history_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d) / 'old.json', Path(d) / 'new.json'
            publish_run(source, *bundle('old', (1,), '2025-12-31T23:30:00-01:00'))
            before = manifest_path(source).read_bytes()
            rows, audit = bundle('new', (1, 2), '2026-02-01T00:00:00Z')
            attach_first_seen(target, rows, audit, history_from=source)
            self.assertEqual(rows[0]['first_seen_at'], '2026-01-01T00:30:00+00:00')
            self.assertEqual(rows[0]['first_seen_evidence']['state'], 'historical')
            self.assertEqual(rows[1]['first_seen_evidence']['state'], 'observed')
            self.assertEqual(manifest_path(source).read_bytes(), before)
            audit['steam_id'] = '76561198000000002'
            with self.assertRaises(AccountMismatchError):
                attach_first_seen(target, rows, audit, history_from=source)

    def test_candidate_and_missing_time_do_not_invent_observations(self):
        with tempfile.TemporaryDirectory() as d:
            rows, audit = bundle('candidate', (1,), '2026-01-01T00:00:00Z')
            audit['membership'] = 'candidate_union'
            attach_first_seen(Path(d) / 'x.json', rows, audit)
            self.assertIsNone(rows[0]['first_seen_at'])
            self.assertEqual(first_seen_fields(rows[0])['first_seen_status'], 'unknown')
            audit['membership'] = 'client_snapshot'
            audit['sources']['client_library']['fetched_at'] = '2026-01-01'
            attach_first_seen(Path(d) / 'x.json', rows, audit)
            self.assertIsNone(rows[0]['first_seen_at'])
            self.assertIsNone(first_seen_fields({'first_seen_at': '2026-01-01T00:00:00Z'})['first_seen_at'])

    def test_rebuild_enrich_tables_picker_and_plans_preserve_dates(self):
        with tempfile.TemporaryDirectory() as d:
            source, rebuilt, enriched = [Path(d) / name for name in ('source.json', 'rebuilt.json', 'enriched.json')]
            rows, audit = bundle('initial', (1, 2), '2026-01-01T00:00:00Z')
            attach_first_seen(source, rows, audit)
            publish_run(source, rows, audit)
            original = copy.deepcopy(rows)
            reclassify(source, rebuilt)
            def store(aid, directory, refresh, stats, **kwargs):
                stats['success'] = 1
                kwargs['observation'].update(source='store_api')
                return parse_fields({})
            with patch('steam_enrich.cached_store_details', side_effect=store):
                enrich(rebuilt, enriched)
            for row, before in zip(load_library(enriched), original):
                self.assertEqual(row['first_seen_at'], before['first_seen_at'])
                self.assertEqual(row['first_seen_evidence'], before['first_seen_evidence'])
            games = PickerLibrary(enriched).read()['games']
            table = json.loads(resolve_artifact(enriched, 'classified.json').read_bytes())
            self.assertEqual([g['first_seen_at'] for g in games], [r['first_seen_at'] for r in table])
            plan, *_ = build_plan(enriched, ACCOUNT, group_by=('first_seen_month',), first_seen_year='2026', first_seen_month='01')
            self.assertEqual(plan['collections'], {'首次观察年月-2026-01': [1, 2]})
            empty, *_ = build_plan(enriched, ACCOUNT, first_seen_month='02')
            self.assertEqual(empty['selected_appids'], [])
            self.assertEqual(empty['collections'], {})
            self.assertIn('first_seen_at', resolve_artifact(enriched, 'classified.csv').read_text(encoding='utf-8-sig'))

    def test_failed_publication_does_not_commit_new_history(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'library.json'
            rows, audit = bundle('one', (1,), '2026-01-01T00:00:00Z')
            attach_first_seen(output, rows, audit)
            publish_run(output, rows, audit)
            before = manifest_path(output).read_bytes()
            rows, audit = bundle('two', (1, 2), '2026-02-01T00:00:00Z')
            attach_first_seen(output, rows, audit)
            with patch('os.fsync', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    publish_run(output, rows, audit)
            self.assertEqual(manifest_path(output).read_bytes(), before)
            old = json.loads(resolve_artifact(output, 'steam_library.audit.json').read_bytes())
            self.assertEqual(set(old['observation_history']['apps']), {'1'})

    def test_utc_year_month_and_unknown_filters(self):
        game = {'first_seen_at': '2025-12-31T23:30:00-01:00',
                'first_seen_evidence': {'state': 'historical', 'source': 'saved_client_snapshot'}}
        self.assertTrue(matches_first_seen(game, '2026', '01'))
        self.assertFalse(matches_first_seen(game, '2025', '12'))
        self.assertTrue(matches_first_seen({}, 'unknown'))
        self.assertFalse(matches_first_seen({}, 'unknown', '01'))

    def test_bad_history_hash_and_wrong_account_evidence_are_rejected(self):
        from steam_schema import validate_artifacts
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / 'source.json'
            rows, audit = bundle('one', (1,), '2026-01-01T00:00:00Z')
            attach_first_seen(output, rows, audit)
            original = copy.deepcopy(rows)
            rows[0]['first_seen_evidence']['steam_id'] = '76561198000000002'
            with self.assertRaises(ValueError):
                validate_artifacts(rows, audit)
            publish_run(output, original, audit)
            resolve_artifact(output, 'classified.md').write_text('altered')
            current, now = bundle('two', (1,), '2026-02-01T00:00:00Z')
            with self.assertRaises(ValueError):
                attach_first_seen(Path(d) / 'target.json', current, now, history_from=output)
