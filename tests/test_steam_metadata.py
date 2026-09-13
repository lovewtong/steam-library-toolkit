import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from steam_metadata import RequestGate, parse_fields, merge_fields, coverage
from steam_http import get_response


class MetadataFieldsTests(unittest.TestCase):
    def test_missing_invalid_and_explicit_empty_are_distinct(self):
        row = dict(genres=['Action'], categories=['Single-player'], is_multiplayer=False, is_controller=True)
        for data in ({}, {'genres': None, 'categories': [{}]}):
            self.assertEqual(merge_fields(row, parse_fields(data)), [])
            self.assertEqual(row['genres'], ['Action'])
            self.assertTrue(row['is_controller'])
        merge_fields(row, parse_fields({'genres': [], 'categories': []}))
        self.assertEqual(row['genres'], [])
        self.assertFalse(row['is_controller'])
        self.assertEqual(coverage([row])['is_controller'], {'true': 0, 'false': 1, 'unknown': 0})

    def test_category_ids_work_without_english_descriptions(self):
        details = parse_fields({'categories': [{'id': 9, 'description': '合作'}, {'id': 28, 'description': '完全支持控制器'}]})
        self.assertTrue(details['is_multiplayer'])
        self.assertTrue(details['is_controller'])
        # Valid IDs can establish capabilities even when descriptions are malformed.
        details = parse_fields({'categories': [{'id': 1}]})
        self.assertTrue(details['is_multiplayer'])
        self.assertEqual(details['field_states']['categories'], 'invalid')
        self.assertIsNone(parse_fields({})['is_multiplayer'])
        self.assertTrue(parse_fields({'controller_support': 'full'})['is_controller'])

    def test_legacy_text_fallback_and_negative_are_not_unknown(self):
        self.assertTrue(parse_fields({'categories': [{'description': '合作'}]})['is_multiplayer'])
        self.assertTrue(parse_fields({'categories': [{'description': '完全支持控制器'}]})['is_controller'])
        self.assertFalse(parse_fields({'categories': [{'id': 2, 'description': '单人'}]})['is_multiplayer'])

    def test_shared_gate_spaces_request_starts(self):
        gate = RequestGate(1.5)
        clock = [0.0]
        def sleep(delay):
            clock[0] += delay
        with patch('steam_metadata.time.monotonic', side_effect=lambda: clock[0]), \
                patch('steam_metadata.time.sleep', side_effect=sleep):
            gate.wait()
            self.assertEqual(clock[0], 0)
            gate.wait()
            self.assertEqual(clock[0], 1.5)
            clock[0] += .5  # Network latency overlaps pacing, not added afterward.
            gate.wait()
            self.assertEqual(clock[0], 3)

    def test_retries_also_pass_through_request_gate(self):
        limited = Mock(status_code=429, headers={'Retry-After': '0'})
        success = Mock(status_code=200)
        gate = Mock()
        with patch('steam_http.requests.get', side_effect=[limited, success]), patch('steam_http.time.sleep'):
            self.assertIs(get_response('https://example.invalid', params={}, timeout=1, before_attempt=gate), success)
        self.assertEqual(gate.call_count, 2)

    def test_old_cache_cannot_keep_incorrect_controller_result(self):
        from steam_collect import cached_store_details
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '1.json'
            old = {'schema_version': 3, 'fetched_at': 1000, 'status': 'success',
                   'details': {'genres': [], 'categories': ['完全支持控制器'],
                               'is_controller': False, 'is_multiplayer': False}}
            path.write_text(json.dumps(old), encoding='utf-8')
            result = {'status': 'success', 'details': parse_fields({'categories': [{'id': 28, 'description': '完全支持控制器'}]})}
            with patch('steam_collect.time.time', return_value=1001), \
                    patch('steam_collect.get_store_result', return_value=result) as fetch:
                self.assertTrue(cached_store_details(1, directory)['is_controller'])
                self.assertTrue(cached_store_details(1, directory)['is_controller'])
                self.assertEqual(fetch.call_count, 1)
