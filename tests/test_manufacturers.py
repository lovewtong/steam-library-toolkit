import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from classification_overrides import read_rules
from classify_games import classify_library
from classify_steam_games import classify_one
from steam_library_toolkit.store import cached_store_details
from steam_enrich import enrich
from steam_metadata import apply_observation, coverage, parse_fields
from steam_picker_server import PickerLibrary
from steam_reclassify import reclassify
from steam_runs import load_library, manifest_path, publish_run, resolve_artifact
from steam_sync_collections import build_plan
from support import run_bundle, ACCOUNT, ROOT


class ManufacturerTests(unittest.TestCase):
    def test_benchmark_compares_manufacturer_values_without_cache_read_timestamps(self):
        from tools.benchmark_enrichment import semantic_rows, without_metadata
        cold = {'appid': 1, 'developers': ['A'], 'publishers': ['P'],
                'manufacturer_evidence': {'developers': {'source': 'store_api', 'read_at': 10}}}
        warm = {**cold, 'manufacturer_evidence': {'developers': {'source': 'store_cache', 'read_at': 20}}}
        self.assertEqual(semantic_rows([cold]), semantic_rows([warm]))
        self.assertNotEqual(semantic_rows([cold]), semantic_rows([{**warm, 'developers': ['B']}]))
        self.assertEqual(without_metadata(cold), {'appid': 1})

    def test_presence_normalization_and_retention(self):
        row = {'appid': 1, 'developers': ['Original'], 'publishers': ['Publisher']}
        observation = {'source': 'store_api', 'fetched_at': 100, 'read_at': 101}
        for payload, expected in (({}, 'missing'), ({'developers': None}, 'invalid'),
                                   ({'developers': ['Valid', 5]}, 'invalid')):
            metadata = {}
            apply_observation(row, parse_fields(payload), {'success': 1}, observation, metadata)
            self.assertEqual(row['developers'], ['Original'])
            self.assertEqual(metadata['apps']['1']['field_actions']['developers'],
                             {'action': 'retained', 'reason': expected})
        apply_observation(row, parse_fields({'developers': [' A ', 'B', 'A'], 'publishers': []}),
                          {'success': 1}, observation, {})
        self.assertEqual(row['developers'], ['A', 'B'])
        self.assertEqual(row['publishers'], [])
        self.assertEqual(row['manufacturer_evidence']['publishers']['state'], 'empty')
        self.assertEqual(row['manufacturer_evidence']['developers']['source'], 'store_api')
        prior = copy.deepcopy(row)
        apply_observation(row, None, {'transient_error': 1}, observation, {})
        self.assertEqual(row, prior)
        self.assertEqual(coverage([row, {'developers': []}, {}])['developers'],
                         {'nonempty': 1, 'empty': 1, 'unknown': 1})

    def test_v5_cache_refetches_once_and_warm_evidence_keeps_observation_time(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / '1.json'
            path.write_text(json.dumps({'schema_version': 5, 'fetched_at': 1000,
                                       'status': 'success', 'details': parse_fields({})}))
            response = {'status': 'success', 'details': parse_fields({'developers': ['Studio'], 'publishers': []})}
            with patch('steam_library_toolkit.store.time.time', return_value=1001), patch('steam_library_toolkit.store.get_store_result', return_value=response) as fetch:
                direct, warm = {}, {}
                details = cached_store_details(1, d, observation=direct)
                again = cached_store_details(1, d, observation=warm)
            self.assertEqual(details, again)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(direct['source'], 'store_api')
            self.assertEqual(warm['source'], 'store_cache')
            self.assertEqual(direct['fetched_at'], warm['fetched_at'])
            self.assertEqual(json.loads(path.read_text())['schema_version'], 6)

    def test_manufacturer_only_override_leaves_genre_and_raw_fields_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'rules.json'
            path.write_text(json.dumps({'schema_version': 1, 'apps': {'1': {
                'developers': [' Corrected ', 'Corrected'], 'publishers': [], 'reason': 'Verified listing'}}}))
            rules = read_rules(path)
            game = {'appid': 1, 'name': 'Example', 'genres': ['Strategy'], 'developers': ['Raw']}
            before = copy.deepcopy(game)
            corrected = classify_one(game, rules)
            self.assertEqual(corrected['analysis'], classify_one(game, {})['analysis'])
            self.assertEqual(corrected['developers'], ['Corrected'])
            self.assertEqual(corrected['manufacturer_evidence']['developers']['state'], 'reviewed')
            table = classify_library([game], rules)[0]
            self.assertEqual(table['main_category'], classify_library([game], {})[0]['main_category'])
            self.assertEqual(table['publishers'], [])
            self.assertEqual(game, before)
            for invalid in (None, 'Studio', ['Studio', 1], [' ']):
                path.write_text(json.dumps({'schema_version': 1, 'apps': {'1': {'developers': invalid, 'reason': 'x'}}}))
                with self.assertRaises(ValueError):
                    read_rules(path)

    def test_verified_pipeline_filters_exports_correction_and_revert(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source, target = root / 'source.json', root / 'enriched.json'
            rows, audit = run_bundle('old', (1, 2, 3, 4))
            publish_run(source, rows, audit)
            before = manifest_path(source).read_bytes()
            old_plan, *_ = build_plan(source, ACCOUNT, group_by=('developers',))
            self.assertEqual(old_plan['collections'], {'开发商-未知': [1, 2, 3, 4]})

            def store(aid, directory, refresh, stats, **kwargs):
                stats.update(success=1, cache_hits=0)
                kwargs['observation'].update(source='store_api', fetched_at=100, read_at=101)
                return parse_fields({1: {'developers': ['A', 'B'], 'publishers': ['P']},
                                     2: {'developers': ['B'], 'publishers': ['Q']},
                                     3: {'developers': [], 'publishers': []}, 4: {}}[aid])
            with patch('steam_enrich.cached_store_details', side_effect=store):
                enrich(source, target)
            for old, new in zip(rows, load_library(target)):
                self.assertEqual({k: v for k, v in old.items() if k not in ('run_id', 'provenance')},
                                 {k: new[k] for k in old if k not in ('run_id', 'provenance')})
            picker = PickerLibrary(target).read()['games']
            self.assertEqual([g['developers'] for g in picker], [['A', 'B'], ['B'], [], None])
            self.assertEqual(manifest_path(source).read_bytes(), before)
            plan, *_ = build_plan(target, ACCOUNT, group_by=('developers', 'publishers'), developer='B', publisher='P')
            self.assertEqual(plan['selected_appids'], [1])
            self.assertEqual(plan['eligible_appids'], [1, 2, 3, 4])
            self.assertEqual(plan['collections'], {'开发商-名称-A': [1], '开发商-名称-B': [1], '发行商-名称-P': [1]})
            empty, *_ = build_plan(target, ACCOUNT, developer='Absent')
            self.assertEqual(empty['collections'], {})
            self.assertEqual(empty['selected_appids'], [])
            output = root / 'plan.json'
            command = [sys.executable, '-B', str(ROOT / 'steam_sync_collections.py'), '--input', str(target),
                       '--account', ACCOUNT, '--publisher', 'P', '--group-by', 'publishers', '-o', str(output)]
            self.assertEqual(subprocess.run(command + ['--dry-run'], capture_output=True).returncode, 0)
            self.assertFalse(output.exists())
            self.assertEqual(subprocess.run(command + ['--export-only'], capture_output=True).returncode, 0)
            self.assertEqual(json.loads(output.read_bytes())['selected_appids'], [1])
            with resolve_artifact(target, 'classified.csv').open(encoding='utf-8-sig', newline='') as stream:
                self.assertEqual(json.loads(next(csv.DictReader(stream))['developers']), ['A', 'B'])

            corrected, reverted = root / 'corrected.json', root / 'reverted.json'
            rules = {'1': {'developers': ['Personal'], 'reason': 'User confirmed'}}
            with patch('classification_overrides.load_overrides', return_value=rules):
                reclassify(target, corrected)
            self.assertEqual(PickerLibrary(corrected).read()['games'][0]['developers'], ['Personal'])
            self.assertEqual(load_library(corrected)[0]['developers'], ['A', 'B'])
            frozen = json.loads(resolve_artifact(corrected, 'classification_overrides.json').read_bytes())
            self.assertEqual(frozen['apps'], rules)
            reclassify(corrected, reverted)
            self.assertEqual(PickerLibrary(reverted).read()['games'][0]['developers'], ['A', 'B'])


if __name__ == '__main__':
    unittest.main()
