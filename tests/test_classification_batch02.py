import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from steam_library_toolkit.classification.five import classify_one
from steam_library_toolkit.classification.tables import classify_library
from steam_library_toolkit.classification.overrides import read_rules
from steam_library_toolkit.cli.reclassify import reclassify
from steam_library_toolkit.cli.review_classification import build_review
from steam_library_toolkit.cli.collections import build_plan
from steam_library_toolkit.storage.runs import publish_run, resolve_artifact
from steam_library_toolkit.web.server import PickerLibrary
from support import ACCOUNT, run_bundle
from tools.review_classification_sample import evaluate, FIXTURES, ROOT


class ClassificationBatch02Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = FIXTURES['batch-02']
        cls.samples = json.loads(cls.fixture.read_text(encoding='utf-8'))['samples']
        cls.rules = read_rules(ROOT / 'src/steam_library_toolkit/resources/rules/classification_overrides.json')
        cls.reviewed = {s['appid'] for s in cls.samples if s['action'] == 'add_appid_override'}
        cls.previous = {aid: rule for aid, rule in cls.rules.items() if int(aid) not in cls.reviewed}

    def test_frozen_expectations_baseline_and_field_scope(self):
        self.assertEqual(len({s['appid'] for s in self.samples}), 155)
        self.assertEqual(len(self.reviewed), 129)
        report = evaluate(self.fixture)
        self.assertEqual(report['matched'], 155)
        self.assertEqual(report['evidence_status'], {'refreshed': 129, 'unavailable': 26})
        for sample in self.samples:
            with self.subTest(appid=sample['appid']):
                before = classify_one(sample, self.previous)
                self.assertEqual({'main_category': classify_library([sample], self.previous)[0]['main_category'],
                                  **{k: before['analysis'][k] for k in ('primary', 'sub')}}, sample['baseline'])
                fields = classify_one(sample, self.rules)['classification_evidence']['fields']
                if sample['appid'] in self.reviewed:
                    rule = self.rules[str(sample['appid'])]
                    self.assertEqual(set(rule), {'main_category', 'reason', 'reference'} |
                                     ({'sub'} if sample['appid'] != 34330 else set()))
                    self.assertEqual(fields['primary']['state'], 'reviewed')
                    self.assertEqual(fields['primary']['reference'], sample['reference'])
                    self.assertEqual(fields['sub']['state'] == 'reviewed', 'sub' in rule)
                else:
                    self.assertEqual(sample['expected'], sample['baseline'])
                    self.assertNotEqual(fields['primary']['state'], 'reviewed')
                for field in ('vibe', 'intensity', 'slogan'):
                    self.assertNotEqual(fields[field]['state'], 'reviewed')

    def test_saved_rebuild_preserves_rows_and_pending_items_and_plan_agrees(self):
        ids = tuple(s['appid'] for s in self.samples)
        rows, audit = run_bundle('batch02-before', ids)
        samples = {s['appid']: s for s in self.samples}
        for row in rows:
            row.update({k: copy.deepcopy(samples[row['appid']][k]) for k in ('name', 'genres')})
        original_rows = copy.deepcopy(rows)
        with tempfile.TemporaryDirectory() as directory:
            source, target = Path(directory) / 'before.json', Path(directory) / 'after.json'
            with patch('steam_library_toolkit.classification.overrides.load_overrides', return_value=self.previous):
                publish_run(source, rows, audit)
            old_review = build_review(source)[0]
            self.assertEqual({i['appid'] for i in old_review['items'] if i['priority'] == 1}, set(ids))
            original_files = {p: p.read_bytes() for p in Path(directory).rglob('*') if p.is_file()}
            with patch('steam_library_toolkit.classification.overrides.load_overrides', return_value=self.rules):
                reclassify(source, target)
            self.assertTrue(all(p.read_bytes() == data for p, data in original_files.items()))
            self.assertEqual(build_review(source)[0], old_review)
            self.assertEqual(rows, original_rows)
            rebuilt = json.loads(resolve_artifact(target).read_bytes())
            for row in rebuilt:
                row['run_id'] = audit['run_id']
            self.assertEqual(rebuilt, original_rows)
            pending = {i['appid'] for i in build_review(target)[0]['items']}
            self.assertEqual(pending, set(ids) - self.reviewed)
            table = {r['appid']: r for r in json.loads(resolve_artifact(target, 'classified.json').read_bytes())}
            shown = {int(g['appid']): g for g in PickerLibrary(target).read()['games']}
            plan, *_ = build_plan(target, ACCOUNT)
            self.assertEqual(set(plan['eligible_appids']), set(ids))
            frozen = read_rules(resolve_artifact(target, 'classification_overrides.json'))
            self.assertEqual(set(frozen), {str(aid) for aid in self.reviewed})
            for aid, sample in samples.items():
                with self.subTest(appid=aid):
                    self.assertEqual(table[aid]['main_category'], sample['expected']['main_category'])
                    for field in ('primary', 'sub'):
                        self.assertEqual(shown[aid]['analysis'][field], sample['expected'][field])
                    self.assertIn(aid, plan['collections']['核心玩法-' + sample['expected']['primary']])
                    if aid in self.reviewed:
                        self.assertEqual(frozen[str(aid)]['reference'], sample['reference'])

    def test_same_names_on_other_appids_do_not_gain_reviewed_status(self):
        for sample in self.samples:
            with self.subTest(appid=sample['appid']):
                game = {**sample, 'appid': 4294967295}
                self.assertNotEqual(classify_one(game, self.rules)['classification_evidence']['fields']['primary']['state'],
                                    'reviewed')
                self.assertNotEqual(classify_library([game], self.rules)[0]['classification_evidence']['fields']['main_category']['state'],
                                    'reviewed')


if __name__ == '__main__':
    unittest.main()
