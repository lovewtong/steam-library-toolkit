import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classification_overrides import read_rules
from classify_games import classify_library
from classify_steam_games import classify_one, find_known
from steam_picker_server import PickerLibrary
from steam_runs import publish_run, resolve_artifact
from steam_sync_collections import build_plan
from test_phase_two import run_bundle, ACCOUNT
from tools.review_classification_sample import evaluate, FIXTURE, FIXTURES, ROOT


class R1ClassificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples = json.loads(FIXTURE.read_text(encoding='utf-8'))['samples']
        cls.editorial_samples = [sample for path in FIXTURES.values()
                                 for sample in json.loads(path.read_text(encoding='utf-8'))['samples']]
        cls.rules = read_rules(ROOT / 'classification_overrides.json')

    def test_fixed_sample_retains_all_cohorts_and_original_overrides(self):
        ids = {s['appid'] for s in self.samples}
        self.assertEqual(len(ids), 31)
        self.assertEqual(len(self.samples), len(ids))
        self.assertEqual({s['cohort'] for s in self.samples},
                         {'existing_override', 'unresolved', 'known_name', 'genre_rules'})
        self.assertEqual({s['appid'] for s in self.samples if s['cohort'] == 'existing_override'},
                         {500, 550, 730, 241930, 326480, 627270, 745960, 923810,
                          976310, 1971870, 622590, 813000, 654310, 770720, 1966970, 2202120})
        covered = {s['appid'] for s in self.editorial_samples}
        self.assertTrue(set(map(int, self.rules)) <= covered, 'New rules need an editorial sample too')

    def test_frozen_editorial_expectations_match_both_classifiers(self):
        report = evaluate()
        for row in report['results']:
            with self.subTest(appid=row['appid'], name=row['name']):
                self.assertEqual(row['actual'], row['expected'])
                self.assertEqual(row['mismatches'], [])
        self.assertEqual(report['evidence_status'],
                         {'refreshed': 25, 'unavailable': 2, 'historical_not_refreshed': 4})

    def test_all_builtin_rules_survive_renaming_and_do_not_overclaim_field_review(self):
        expected = {str(s['appid']): s['expected'] for s in self.editorial_samples}
        for aid, rule in self.rules.items():
            for name, genres in (('本地化名称™', []), ('BioShock', ['Action'])):
                with self.subTest(appid=aid, name=name):
                    game = {'appid': int(aid), 'name': name, 'genres': genres,
                            'app_type': 'game', 'playtime_minutes': None}
                    before = copy.deepcopy(game)
                    five, table = classify_one(game, self.rules), classify_library([game], self.rules)[0]
                    self.assertEqual(table['main_category'], expected[aid]['main_category'])
                    self.assertEqual(five['analysis']['primary'], expected[aid]['primary'])
                    self.assertEqual(five['analysis']['sub'], expected[aid]['sub'])
                    for field, evidence in five['classification_evidence']['fields'].items():
                        reviewed = field == 'primary' or field in rule
                        self.assertEqual(evidence['state'] == 'reviewed', reviewed)
                        if reviewed:
                            self.assertEqual(evidence['reference'], rule['reference'])
                            self.assertEqual(evidence['source'], 'appid_override')
                    self.assertEqual(table['classification_evidence']['fields']['main_category']['reference'], rule['reference'])
                    self.assertNotEqual(table['classification_evidence']['fields']['tags']['state'], 'reviewed')
                    self.assertEqual(game, before)

    def test_migrated_or_unverified_names_no_longer_infer_identity(self):
        names = ('Broken Age', 'Caveman World', 'BROK the InvestiGator', 'One Gun Guy',
                 'Lair Land Story', 'Destroyer: The U-Boat Hunter', 'Wrestledunk Sports', 'Petz Catz 2')
        for name in names:
            with self.subTest(name=name):
                self.assertIsNone(find_known(name))
                result = classify_one({'appid': 4294967295, 'name': name, 'genres': []}, self.rules)
                self.assertEqual(result['analysis']['primary'], '其他')
                self.assertEqual(result['classification_evidence']['fields']['primary']['state'], 'unknown')

    def test_simulation_alone_does_not_imply_management(self):
        for name, genres in (('Simple Adventure', ['Action']), ('Fixture', ['模拟']),
                             ('Fixture', ['Simulation']), ('Sim Thing', ['Adventure'])):
            with self.subTest(name=name, genres=genres):
                result = classify_one({'appid': 1, 'name': name, 'genres': genres}, {})
                self.assertEqual(result['analysis']['sub'], '多种元素')
                self.assertEqual(result['classification_evidence']['fields']['sub']['state'], 'unknown')

    def test_published_sample_picker_and_collection_plan_agree_without_mutating_library(self):
        rows, audit = run_bundle('r1-fixture', tuple(s['appid'] for s in self.samples))
        inputs = {s['appid']: s for s in self.samples}
        for row in rows:
            row.update({k: copy.deepcopy(inputs[row['appid']][k]) for k in ('name', 'genres')})
        before = copy.deepcopy(rows)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'library.json'
            with patch('classification_overrides.load_overrides', return_value=self.rules):
                publish_run(target, rows, audit)
            self.assertEqual(rows, before)
            table = {r['appid']: r for r in json.loads(resolve_artifact(target, 'classified.json').read_bytes())}
            shown = {int(g['appid']): g for g in PickerLibrary(target).read()['games']}
            plan, *_ = build_plan(target, ACCOUNT)
            self.assertEqual(set(shown), set(inputs))
            self.assertEqual(set(plan['eligible_appids']), set(inputs))
            for aid, sample in inputs.items():
                with self.subTest(appid=aid):
                    expected = sample['expected']
                    self.assertEqual(table[aid]['main_category'], expected['main_category'])
                    self.assertEqual(shown[aid]['analysis']['primary'], expected['primary'])
                    self.assertEqual(shown[aid]['analysis']['sub'], expected['sub'])
                    self.assertIn(aid, plan['collections']['核心玩法-' + expected['primary']])
                    self.assertIn(aid, plan['collections']['细分-' + expected['sub']])


if __name__ == '__main__':
    unittest.main()
