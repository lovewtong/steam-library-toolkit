import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from steam_enrich import enrich
from steam_lock import collection_lock
from steam_runs import load_library, manifest_path, publish_run, resolve_artifact
from steam_sources import SourceResult, reconcile, records_hash


class EnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / 'source.json'
        self.output = Path(self.temp.name) / 'enriched.json'
        apps = [{'appid': 1, 'name': 'Unknown time', 'app_type': 'game'},
                {'appid': 2, 'name': 'Known zero', 'app_type': 'game', 'playtime_forever': 0}]
        rows, audit = reconcile([SourceResult('client_library', apps, steam_id='76561198000000001',
                                              completeness={'verified': True})])
        audit.update(run_id='original', producer={'git_commit': 'fixture', 'dirty': False})
        audit['snapshot'] = {'schema_version': 2, 'run_id': 'original', 'producer': audit['producer'],
                             'steam_id': audit['steam_id'], 'generated_at': audit['generated_at'],
                             'source': 'client_library', 'membership_semantics': 'client_library_membership',
                             'complete': True, 'completeness': {'verified': True}, 'record_count': 2,
                             'apps_sha256': records_hash(apps), 'apps': apps}
        for row in rows:
            row.update(run_id='original', genres=['Original'], categories=[], is_multiplayer=None,
                       is_controller=None, playtime_minutes=row.get('playtime_forever'))
        publish_run(self.source, rows, audit)
        self.rows = load_library(self.source)
        self.pointer = manifest_path(self.source).read_bytes()

    @staticmethod
    def store(appid, cache_dir, refresh, stats):
        stats.update(success=1, cache_hits=1)
        return {'genres': ['Adventure'], 'categories': ['Co-op'], 'is_multiplayer': True,
                'is_controller': None, 'app_type': 'dlc'}

    def test_enrich_preserves_evidence_snapshot_and_original_generation(self):
        with patch('steam_enrich.cached_store_details', side_effect=self.store), \
                patch('steam_collect.collect_client', side_effect=AssertionError('Authentication forbidden')), \
                patch('steam_collect.load_config', side_effect=AssertionError('Credentials forbidden')):
            _, meta = enrich(manifest_path(self.source), self.output)
        result = load_library(self.output)
        for original, enriched in zip(self.rows, result):
            for key in original:
                if key not in {'run_id', 'genres', 'categories', 'is_multiplayer', 'is_controller', 'provenance'}:
                    self.assertEqual(enriched[key], original[key], key)
            self.assertEqual(enriched['app_type'], 'game')
            self.assertEqual(enriched['genres'], ['Adventure'])
            expected = copy.deepcopy(original['provenance'])
            expected['store_metadata'] = 'store_cache'
            self.assertEqual(enriched['provenance'], expected)
        self.assertEqual(meta['state'], 'complete')
        self.assertEqual(manifest_path(self.source).read_bytes(), self.pointer)
        self.assertEqual(load_library(self.source), self.rows)
        audit = json.loads(resolve_artifact(self.output, 'steam_library.audit.json').read_text())
        snapshot = json.loads(resolve_artifact(self.output, 'client.snapshot.json').read_text())
        self.assertEqual(audit['parent_run']['run_id'], 'original')
        self.assertEqual(snapshot['run_id'], audit['run_id'])
        self.assertEqual(snapshot['generated_at'], audit['parent_run']['generated_at'])

    def test_partial_failure_retains_previous_metadata(self):
        def failure(appid, cache_dir, refresh, stats):
            stats.update(not_found=1, cache_hits=0)
        with patch('steam_enrich.cached_store_details', side_effect=failure):
            _, meta = enrich(self.source, self.output, appids=[1])
        rows = load_library(self.output)
        self.assertEqual([r['genres'] for r in rows], [['Original'], ['Original']])
        self.assertEqual(meta['state'], 'partial')
        self.assertEqual(meta['apps'], {'1': {'state': 'not_found', 'cache_hit': False}})

    def test_rejects_bad_source_selection_and_conflicting_output_before_network(self):
        with patch('steam_enrich.cached_store_details') as store:
            with self.assertRaisesRegex(ValueError, 'ENRICH_OUTPUT_CONFLICT'):
                enrich(self.source, manifest_path(self.source))
            with self.assertRaisesRegex(ValueError, 'ENRICH_APPID_INVALID'):
                enrich(self.source, self.output, appids=[999])
            with self.assertRaisesRegex(ValueError, 'ENRICH_SOURCE_INVALID'):
                enrich(Path(self.temp.name) / 'flat.json', self.output)
            store.assert_not_called()
        self.assertFalse(manifest_path(self.output).exists())

    def test_corruption_and_interruption_do_not_replace_previous_result(self):
        with patch('steam_enrich.cached_store_details', side_effect=self.store):
            enrich(self.source, self.output)
        pointer = manifest_path(self.output).read_bytes()
        with patch('steam_enrich.cached_store_details', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                enrich(self.source, self.output)
        self.assertEqual(manifest_path(self.output).read_bytes(), pointer)
        resolve_artifact(self.source).write_text('[]', encoding='utf-8')
        with patch('steam_enrich.cached_store_details') as store:
            with self.assertRaisesRegex(ValueError, 'GENERATION_INVALID'):
                enrich(self.source, self.output)
            store.assert_not_called()
        self.assertEqual(manifest_path(self.output).read_bytes(), pointer)

    def test_enrichment_respects_collector_lock(self):
        with collection_lock(self.source):
            with self.assertRaisesRegex(RuntimeError, 'OUTPUT_BUSY'):
                enrich(self.source, self.output)

    def test_other_account_target_is_rejected_before_store_requests(self):
        audit = json.loads(resolve_artifact(self.source, 'steam_library.audit.json').read_text())
        audit.update(steam_id='76561198000000002', run_id='otheraccount')
        rows = copy.deepcopy(self.rows)
        for row in rows:
            row['run_id'] = 'otheraccount'
        publish_run(self.output, rows, audit)
        pointer = manifest_path(self.output).read_bytes()
        with patch('steam_enrich.cached_store_details') as store:
            with self.assertRaisesRegex(ValueError, 'ACCOUNT_MISMATCH'):
                enrich(self.source, self.output)
            store.assert_not_called()
        self.assertEqual(manifest_path(self.output).read_bytes(), pointer)


if __name__ == '__main__':
    unittest.main()
