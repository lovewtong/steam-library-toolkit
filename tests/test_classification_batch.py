import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from steam_library_toolkit.classification.overrides import read_rules
from steam_library_toolkit.cli.classify_table import classify_library
from steam_library_toolkit.cli.classify_five import classify_one
from steam_library_toolkit.web.server import PickerLibrary
from steam_library_toolkit.cli.reclassify import reclassify
from steam_library_toolkit.cli.review_classification import build_review
from steam_library_toolkit.storage.runs import publish_run, resolve_artifact
from steam_library_toolkit.cli.collections import build_plan
from support import ACCOUNT, run_bundle
from tools.review_classification_sample import evaluate, FIXTURES, ROOT


class ClassificationBatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = FIXTURES['batch-01']
        cls.samples = json.loads(cls.fixture.read_text(encoding='utf-8'))['samples']
        cls.rules = read_rules(ROOT / 'src/steam_library_toolkit/resources/rules/classification_overrides.json')

    def test_batch_has_independent_frozen_expectations_and_baseline(self):
        ids = {s['appid'] for s in self.samples}
        self.assertEqual(ids, {7670, 8850, 8870, 63380, 214550, 241260})
        self.assertEqual(len(self.samples), len(ids))
        report = evaluate(self.fixture)
        self.assertEqual(report['matched'], 6)
        self.assertEqual(report['evidence_status'], {'refreshed': 6})
        previous = {aid: rule for aid, rule in self.rules.items() if int(aid) not in ids}
        for sample in self.samples:
            with self.subTest(appid=sample['appid']):
                five = classify_one(sample, previous)
                baseline = {'main_category': classify_library([sample], previous)[0]['main_category'],
                            **{k: five['analysis'][k] for k in ('primary', 'sub')}}
                self.assertEqual(baseline, sample['baseline'])
                self.assertNotEqual(baseline['main_category'], sample['expected']['main_category'])
                self.assertEqual(set(self.rules[str(sample['appid'])]),
                                 {'main_category', 'sub', 'reason', 'reference'})

    def test_saved_rebuild_resolves_only_selected_items_and_plan_agrees(self):
        ids = tuple(s['appid'] for s in self.samples)
        rows, audit = run_bundle('batch-before', ids + (15150,))
        by_id = {s['appid']: s for s in self.samples}
        for row in rows:
            sample = by_id.get(row['appid'], {'name': 'Petz Catz 2', 'genres': []})
            row.update({key: copy.deepcopy(sample[key]) for key in ('name', 'genres')})
        before_rows = copy.deepcopy(rows)
        previous = {aid: rule for aid, rule in self.rules.items() if int(aid) not in ids}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / 'before.json', root / 'after.json'
            with patch('steam_library_toolkit.classification.overrides.load_overrides', return_value=previous):
                publish_run(source, rows, audit)
            old_report, *_ = build_review(source)
            self.assertEqual({i['appid'] for i in old_report['items']}, set(ids) | {15150})
            self.assertTrue(all(i['priority'] == 1 for i in old_report['items']))
            original_files = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch('steam_library_toolkit.classification.overrides.load_overrides', return_value=self.rules):
                reclassify(source, target)
            self.assertTrue(all(p.read_bytes() == content for p, content in original_files.items()))
            self.assertEqual(build_review(source)[0], old_report)
            self.assertEqual(rows, before_rows)
            after_rows = json.loads(resolve_artifact(target).read_bytes())
            for row in after_rows:
                row['run_id'] = audit['run_id']
            self.assertEqual(after_rows, before_rows)
            report, *_ = build_review(target)
            self.assertEqual([i['appid'] for i in report['items']], [15150])
            self.assertIn('primary_unknown', report['items'][0]['reasons'])
            table = {r['appid']: r for r in json.loads(resolve_artifact(target, 'classified.json').read_bytes())}
            shown = {int(g['appid']): g for g in PickerLibrary(target).read()['games']}
            frozen = read_rules(resolve_artifact(target, 'classification_overrides.json'))
            self.assertEqual(set(frozen), {str(aid) for aid in ids})
            plan, *_ = build_plan(target, ACCOUNT)
            self.assertEqual(set(plan['eligible_appids']), set(ids) | {15150})
            for aid, sample in by_id.items():
                with self.subTest(appid=aid):
                    expected = sample['expected']
                    self.assertEqual(table[aid]['main_category'], expected['main_category'])
                    for field in ('primary', 'sub'):
                        self.assertEqual(shown[aid]['analysis'][field], expected[field])
                        self.assertEqual(shown[aid]['classification_evidence']['fields'][field]['state'], 'reviewed')
                    for field in ('vibe', 'intensity', 'slogan'):
                        self.assertNotEqual(shown[aid]['classification_evidence']['fields'][field]['state'], 'reviewed')
                    self.assertEqual(frozen[str(aid)]['reference'], sample['reference'])
                    self.assertIn(aid, plan['collections']['核心玩法-' + expected['primary']])
                    self.assertIn(aid, plan['collections']['细分-' + expected['sub']])

    def test_same_names_on_other_appids_do_not_gain_reviewed_status(self):
        for sample in self.samples:
            game = {**sample, 'appid': 4294967295}
            with self.subTest(name=sample['name']):
                five = classify_one(game, self.rules)
                table = classify_library([game], self.rules)[0]
                self.assertNotEqual(five['classification_evidence']['fields']['primary']['state'], 'reviewed')
                self.assertNotEqual(table['classification_evidence']['fields']['main_category']['state'], 'reviewed')


if __name__ == '__main__':
    unittest.main()
