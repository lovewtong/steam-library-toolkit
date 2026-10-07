import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import steam_library_toolkit.cli.collect as steam_collect
from steam_library_toolkit.sources.membership import trusted_current_membership, verified_source, verified_family_source
from steam_library_toolkit.sources.observation import attach_first_seen
from steam_library_toolkit.web.server import PickerLibrary
from steam_library_toolkit.cli.reclassify import reclassify
from steam_library_toolkit.cli.review_classification import build_review
from steam_library_toolkit.storage.runs import publish_run, manifest_path, resolve_artifact, check_previous
from steam_library_toolkit.storage.schema import validate_artifacts
from steam_library_toolkit.sources.reconcile import SourceResult, reconcile, AccountMismatchError
from steam_library_toolkit.cli.collections import build_plan

ACCOUNT = '76561198000000001'
REFS = (3017860, 2183900)


def family_row(appid, own=False):
    return {'appid': appid, 'name': f'Family Game {appid}', 'app_type': 'game', 'family_evidence': {
        'source': 'family_library', 'verified': True, 'own': own, 'shared': True, 'owner_count': 2, 'exclude_reason': 0}}


def payload():
    return {'steam_id': ACCOUNT, 'client': {'state': 'complete', 'completeness': {'verified': True},
            'records': [{'appid': 1, 'name': 'Own Game', 'app_type': 'game'}]},
        'family': {'state': 'complete', 'records': [family_row(1, True), *(family_row(i) for i in REFS)],
                   'completeness': {'verified': True, 'reads': 2, 'account_checked': True,
                     'owners_checked': True, 'group_checked': True, 'family_state': 'member',
                     'returned_apps': 4, 'max_apps': 100000, 'eligible_games': 3}},
        'api': {'state': 'complete', 'records': [{'appid': 1, 'playtime_forever': 0}]},
        'license_status': 'ok', 'licenses': [{'appid': 1, 'shared_only': False},
             *({'appid': i, 'shared_only': True} for i in REFS), {'appid': 4, 'app_type': 'dlc'}],
        'playtime_status': 'ok', 'playtimes': []}


def collected(data=None, **options):
    audit = {}
    with patch('steam_library_toolkit.cli.collect.load_config', return_value={}), patch('steam_library_toolkit.cli.collect.collect_client', return_value=data or payload()):
        rows = steam_collect.collect(fetch_store=False, use_client=True, audit=audit, **options)
    return rows, audit


class FamiliesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'library.json'

    def test_verified_family_games_extend_membership_and_keep_personal_unknown_times(self):
        rows, audit = collected(strict=True, strict_membership=True, require_sources=['family_library'])
        self.assertEqual([r['appid'] for r in rows], [1, 2183900, 3017860])
        self.assertEqual(audit['membership'], 'accessible_snapshot')
        self.assertTrue(trusted_current_membership(audit))
        self.assertEqual(audit['summary']['current_client_apps'], 1)
        self.assertEqual(audit['summary']['family_added_games'], 2)
        self.assertEqual(audit['difference']['accessible_not_api'], list(sorted(REFS)))
        for row in rows[1:]:
            self.assertEqual(row['membership']['source'], 'family_library')
            self.assertEqual(row['ownership'], 'shared')
            self.assertIsNone(row['playtime_minutes'])
            self.assertEqual(row['playtime']['state'], 'unknown')
        self.assertEqual(rows[0]['ownership'], 'account_license')
        self.assertEqual(rows[0]['playtime']['state'], 'known_zero')
        validate_artifacts(rows, audit, audit['snapshot'])

    def test_failed_partial_or_unverified_family_never_publishes_a_smaller_library(self):
        rows, audit = collected()
        publish_run(self.output, rows, audit)
        before = manifest_path(self.output).read_bytes()
        for bad in [None, {'state': 'partial', 'error_code': 'FAMILY_LIST_CHANGED'},
                    {'state': 'complete', 'records': []}, {'state': 'unavailable', 'error_code': 'HTTP_503'}]:
            data = payload(); data['family'] = bad
            with patch('steam_library_toolkit.cli.collect.load_config', return_value={}), patch('steam_library_toolkit.cli.collect.collect_client', return_value=data), \
                 patch.object(sys, 'argv', ['steam_collect.py', '--local-session', '--no-store', '-o', str(self.output)]), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                steam_collect.main()
            self.assertEqual(manifest_path(self.output).read_bytes(), before)
        diagnostics = list(self.output.parent.glob('.library.failed-runs/*/diagnostic.json'))
        self.assertEqual(len(diagnostics), 4)

    def test_wrong_account_and_unsafe_family_evidence_are_rejected(self):
        data = payload(); data['family'] = {'state': 'account_mismatch', 'error_code': 'ACCOUNT_MISMATCH'}
        with self.assertRaises(AccountMismatchError):
            collected(data)
        for field in ({'exclude_reason': 3}, {'verified': False}, {'own': None}, {'owner_count': 0}):
            data = payload(); data['family']['records'][1]['family_evidence'].update(field)
            with self.assertRaisesRegex(RuntimeError, 'FAMILY_SOURCE_FAILED'):
                collected(data)
        rows, audit = collected(); rows[1]['family_evidence']['exclude_reason'] = 1
        with self.assertRaisesRegex(ValueError, 'SCHEMA_INVALID'):
            validate_artifacts(rows, audit)

    def test_malformed_completeness_is_rejected_without_crashing_or_replacing_output(self):
        rows, audit = collected()
        publish_run(self.output, rows, audit)
        before = manifest_path(self.output).read_bytes()
        for proof in (None, [], 'complete', True):
            source = {'status': 'ok', 'state': 'complete', 'count': 0, 'completeness': proof}
            self.assertFalse(verified_source(source))
            self.assertFalse(verified_family_source(source))
            self.assertFalse(SourceResult('client_library', completeness=proof).authoritative)
            for name in ('client', 'family'):
                data = payload(); data[name]['completeness'] = proof
                with patch('steam_library_toolkit.cli.collect.load_config', return_value={}), patch('steam_library_toolkit.cli.collect.collect_client', return_value=data), \
                     patch.object(sys, 'argv', ['steam_collect.py', '--local-session', '--no-store', '--strict-membership', '-o', str(self.output)]), \
                     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
                    steam_collect.main()
                self.assertEqual(failure.exception.code, 1)
                self.assertEqual(manifest_path(self.output).read_bytes(), before)

    def test_family_completeness_counts_require_integers(self):
        _, audit = collected()
        good = audit['sources']['family_library']
        self.assertTrue(verified_family_source(good))
        for value in (None, '3', True, -1):
            bad = deepcopy(good); bad['count'] = value; bad['completeness']['eligible_games'] = value
            self.assertFalse(verified_family_source(bad))
        for field in ('eligible_games', 'returned_apps', 'max_apps'):
            bad = deepcopy(good); bad['completeness'][field] = True
            self.assertFalse(verified_family_source(bad))
        no_family = deepcopy(good); no_family.update(count=0)
        no_family['completeness'].update(family_state='not_member', returned_apps=0)
        self.assertTrue(verified_family_source(no_family))
        no_family['completeness']['returned_apps'] = False
        self.assertFalse(verified_family_source(no_family))

    def test_family_without_client_cannot_turn_into_current_membership(self):
        data = payload(); data['client'] = {'state': 'unavailable', 'error_code': 'HTTP_503'}
        rows, audit = collected(data)
        self.assertEqual(audit['membership'], 'candidate_union')
        self.assertEqual([r['appid'] for r in rows], [1])
        with self.assertRaisesRegex(RuntimeError, 'STRICT_MEMBERSHIP_FAILED'):
            collected(data, strict_membership=True)

    def test_explicit_client_scope_uses_no_family_and_cannot_replace_accessible_scope(self):
        rows, audit = collected(); publish_run(self.output, rows, audit)
        data = payload(); data.pop('family')
        with patch('steam_library_toolkit.cli.collect.load_config', return_value={}), patch('steam_library_toolkit.cli.collect.collect_client', return_value=data) as helper:
            reduced_audit = {}; reduced = steam_collect.collect(fetch_store=False, use_client=True, include_family=False, audit=reduced_audit)
            self.assertIs(helper.call_args.kwargs['use_family'], False)
        self.assertEqual(reduced_audit['membership'], 'client_snapshot')
        with self.assertRaisesRegex(ValueError, 'MEMBERSHIP_SCOPE_CHANGED'):
            check_previous(self.output, reduced, reduced_audit)

    def test_family_disappearance_keeps_ledger_and_removal_guardrail(self):
        rows, audit = collected(); attach_first_seen(self.output, rows, audit); publish_run(self.output, rows, audit)
        data = payload(); data['family']['records'] = [family_row(1, True)]
        data['family']['completeness']['eligible_games'] = 1
        reduced, next_audit = collected(data)
        check_previous(self.output, reduced, next_audit)
        self.assertEqual(next_audit['status'], 'suspicious_change')
        attach_first_seen(self.output, reduced, next_audit)
        self.assertEqual(len(next_audit['observation_history']['apps']), 3)

    def test_first_observation_follows_membership_source_and_preserves_old_own_history(self):
        old, previous = reconcile([SourceResult('client_library', [{'appid': 1, 'name': 'Own Game', 'app_type': 'game'}],
            steam_id=ACCOUNT, fetched_at='2026-09-01T00:00:00Z', completeness={'verified': True})])
        previous.update(run_id='previous', producer={'dirty': False})
        old[0]['run_id'] = 'previous'
        publish_run(self.output, old, previous)
        rows, audit = collected(); audit['sources']['family_library']['fetched_at'] = '2026-10-06T00:00:00Z'
        attach_first_seen(self.output, rows, audit)
        self.assertTrue(rows[0]['first_seen_at'].startswith('2026-09'))
        for row in rows[1:]:
            self.assertTrue(row['first_seen_at'].startswith('2026-10'))
            self.assertEqual(row['first_seen_evidence']['source'], 'family_library')
        validate_artifacts(rows, audit)

    def test_picker_table_review_plan_and_offline_rebuild_keep_family_members(self):
        rows, audit = collected(); attach_first_seen(self.output, rows, audit)
        publish_run(self.output, rows, audit)
        before = manifest_path(self.output).read_bytes()
        picker = PickerLibrary(self.output).read()
        self.assertEqual(len(picker['games']), 3)
        self.assertEqual(picker['games'][1]['membership_source'], 'family_library')
        self.assertEqual(picker['games'][1]['ownership'], 'shared')
        table = json.loads(resolve_artifact(self.output, 'classified.json').read_bytes())
        self.assertEqual(table[1]['membership_source'], 'family_library')
        self.assertEqual(table[1]['ownership'], 'shared')
        self.assertNotIn(ACCOUNT, json.dumps(picker))
        plan = build_plan(self.output, ACCOUNT)[0]
        self.assertEqual(plan['eligible_appids'], [1, 2183900, 3017860])
        self.assertEqual(plan['shared_appids'], sorted(REFS))
        self.assertFalse(plan['write_supported'])
        review = build_review(self.output)[0]
        self.assertEqual(review['summary']['games'], 3)
        missing = json.loads(resolve_artifact(self.output, 'missing_from_web_api.json').read_bytes())['apps']
        self.assertTrue(all(r['present_in_family'] and not r['present_in_client'] for r in missing))
        with patch('socket.create_connection', side_effect=AssertionError('offline must not connect')):
            rebuilt = self.output.parent / 'rebuilt.json'; reclassify(self.output, rebuilt)
        self.assertEqual(len(PickerLibrary(rebuilt).read()['games']), 3)
        self.assertEqual(manifest_path(self.output).read_bytes(), before)

    def test_ownership_conflict_is_unknown_with_both_evidence_sources_retained(self):
        data = payload(); data['licenses'][1]['shared_only'] = False
        rows, _ = collected(data)
        row = next(r for r in rows if r['appid'] == REFS[0])
        self.assertEqual(row['ownership'], 'unknown')
        self.assertTrue(row['ownership_conflict'])
        self.assertIn('family_library', row['sources'])
        self.assertIn('licenses', row['sources'])
