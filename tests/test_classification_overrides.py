import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classification_overrides import load_overrides, read_rules
from classify_games import classify_library
from classify_steam_games import classify_one, find_known
from steam_runs import publish_run, load_library, resolve_artifact, manifest_path
from test_phase_two import run_bundle


class ClassificationOverridesTests(unittest.TestCase):
    def test_reviewed_missing_genre_examples_use_agreed_categories(self):
        # Editorial expectations from CLASSIFICATION_REVIEW.md, not generated from rules.
        cases = [
            (241930, '动作/冒险', '动作/冒险', '开放世界动作'),
            (326480, '独立/其他', '独立/叙事', '视觉小说'),
            (627270, '动作/冒险', '动作/冒险', '格斗'),
            (745960, '独立/其他', '独立/叙事', '视觉小说'),
            (923810, '独立/其他', '独立/叙事', '视觉小说'),
            (976310, '动作/冒险', '动作/冒险', '格斗'),
            (1971870, '动作/冒险', '动作/冒险', '格斗'),
            (622590, '射击', '射击 (FPS/TPS)', '战术竞技射击（测试分支）'),
            (813000, '射击', '射击 (FPS/TPS)', '战术竞技射击（实验分支）'),
            (654310, '动作/冒险', '动作/冒险', '冷兵器动作（测试分支）'),
            (770720, '射击', '射击 (FPS/TPS)', '战术射击（测试分支）'),
        ]
        rules = load_overrides(Path('nonexistent-local-rules.json'))
        for appid, main, primary, sub in cases:
            with self.subTest(appid=appid):
                game = {'appid': appid, 'name': '名称不可用', 'genres': [], 'playtime_minutes': None}
                self.assertEqual(classify_library([game], rules)[0]['main_category'], main)
                result = classify_one(game, rules)
                self.assertEqual(result['analysis']['primary'], primary)
                self.assertEqual(result['analysis']['sub'], sub)
                self.assertIn('reference', result['classification_evidence'])

    def test_name_matching_rejects_word_fragments(self):
        for name in ('Konami', 'Shanked', 'xBioshock', 'BioshockInfinite'):
            with self.subTest(name=name):
                self.assertIsNone(find_known(name))

    def test_name_matching_keeps_series_specificity_and_trademarks(self):
        for name, sub in [('  BIOSHOCK™   INFINITE  ', '叙事FPS'),
                          ('Batman: Arkham Knight', '开放世界动作'),
                          ('Hitman: Sniper Challenge', '狙击'),
                          ('Shank 2', '横版清版')]:
            with self.subTest(name=name):
                self.assertEqual(find_known(name)['sub'], sub)
        self.assertEqual(find_known('BioShock Infinite: Complete Edition'), find_known('BioShock Infinite'))
        self.assertEqual(find_known('Batman™: Arkham Knight'), find_known('Batman: Arkham Knight'))

    def test_appid_survives_renaming_and_does_not_match_unrelated_same_name(self):
        rules = load_overrides(Path('nonexistent-local-rules.json'))
        for appid in (500, 550, 730):
            game = {'appid': appid, 'name': '本地化名称™', 'genres': ['动作'], 'playtime_minutes': None}
            original = copy.deepcopy(game)
            self.assertEqual(classify_library([game], rules)[0]['main_category'], '射击')
            result = classify_one(game, rules)
            self.assertEqual(result['analysis']['primary'], '射击 (FPS/TPS)')
            self.assertEqual(result['classification_evidence']['source'], 'appid_override')
            self.assertEqual(game, original)
        self.assertNotEqual(classify_one({'appid': 999999, 'name': 'Counter-Strike 2'}, rules)
                            ['classification_evidence']['source'], 'appid_override')

    def test_local_rule_replaces_builtin_and_normalizes_fields(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'rules.json'
            p.write_text(json.dumps({'schema_version': 1, 'apps': {'730': {
                'main_category': ' 策略 ', 'reason': ' 用户偏好 ', 'sub': ' 战术 '}}}), encoding='utf-8')
            rules = load_overrides(p)
            self.assertNotIn('reference', rules['730'])
            self.assertEqual(classify_library([{'appid': 730}], rules)[0]['main_category'], '策略')
            self.assertEqual(classify_one({'appid': 730}, rules)['analysis']['primary'], '策略/模拟')
            self.assertEqual(classify_one({'appid': 730}, rules)['analysis']['sub'], '战术')

    def test_invalid_duplicate_or_membership_editing_rules_fail(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'rules.json'
            for entry in ({'main_category': 'bad', 'reason': 'x'},
                          {'main_category': '射击'},
                          {'main_category': '射击', 'reason': 'x', 'app_type': 'game'},
                          {'main_category': '射击', 'reason': 'x', 'playtime_minutes': 0}):
                p.write_text(json.dumps({'schema_version': 1, 'apps': {'730': entry}}), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'CLASSIFICATION_OVERRIDE_INVALID'):
                    read_rules(p)
            p.write_text('{"schema_version":1,"apps":{"730":{},"730":{}}}', encoding='utf-8')
            with self.assertRaises(ValueError):
                read_rules(p)

    def test_publication_freezes_applied_rules_without_changing_members_or_times(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'library.json'
            rows, audit = run_bundle('original', (730,))
            original = copy.deepcopy(rows)
            publish_run(p, rows, audit)
            self.assertEqual(load_library(p), original)
            rules = json.loads(resolve_artifact(p, 'classification_overrides.json').read_text(encoding='utf-8'))
            self.assertEqual(set(rules['apps']), {'730'})
            before = manifest_path(p).read_bytes()
            with patch('classification_overrides.load_overrides', side_effect=ValueError('invalid rules')):
                with self.assertRaises(ValueError):
                    publish_run(p, *run_bundle('failed', (730,)))
            self.assertEqual(manifest_path(p).read_bytes(), before)

    def test_rebuild_requires_no_network_and_keeps_original_generation(self):
        from steam_reclassify import reclassify
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d) / 'source.json', Path(d) / 'target.json'
            rows, audit = run_bundle('original', (730,))
            publish_run(source, rows, audit)
            original = manifest_path(source).read_bytes()
            with patch('requests.get', side_effect=AssertionError('network forbidden')), \
                    patch('steam_auth.collect_client', side_effect=AssertionError('auth forbidden')):
                reclassify(source, target)
            self.assertEqual(manifest_path(source).read_bytes(), original)
            self.assertEqual([{k:v for k,v in r.items() if k != 'run_id'} for r in load_library(target)],
                             [{k:v for k,v in r.items() if k != 'run_id'} for r in rows])
            with self.assertRaises(ValueError):
                reclassify(source, source)


if __name__ == '__main__':
    unittest.main()
