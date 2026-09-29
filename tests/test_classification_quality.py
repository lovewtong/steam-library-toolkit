import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from classify_games import classify_library
from classify_steam_games import classify_one
from classification_overrides import load_overrides
from steam_runs import publish_run, resolve_artifact
from test_phase_two import run_bundle


class ClassificationQualityTests(unittest.TestCase):
    def test_reviewed_appids_ignore_localized_names(self):
        rules = load_overrides(Path('nonexistent-local-rules.json'))
        for appid, main, primary, sub in (
                (1966970, '动作/冒险', '动作/冒险', '精确平台跳跃'),
                (2202120, '策略', '策略/模拟', '即时战术/潜行')):
            with self.subTest(appid=appid):
                game = {'appid': appid, 'name': '本地化名称', 'genres': ['Action']}
                self.assertEqual(classify_library([game], rules)[0]['main_category'], main)
                result = classify_one(game, rules)
                self.assertEqual(result['analysis']['primary'], primary)
                self.assertEqual(result['analysis']['sub'], sub)
                self.assertIn(str(appid), result['classification_evidence']['reference'])

    def test_shared_genre_mapping_and_priority(self):
        cases = [(['Racing'], '体育/竞速', '体育/竞速'),
                 (['Sports'], '体育/竞速', '体育/竞速'),
                 (['Strategy'], '策略', '策略/模拟'),
                 (['Simulation'], '模拟经营', '策略/模拟'),
                 (['Casual'], '休闲/益智', '解谜/休闲'),
                 (['Indie'], '独立/其他', '独立/叙事'),
                 (['Action', 'RPG'], 'RPG', '角色扮演 (RPG)'),
                 (['动作', '策略'], '策略', '策略/模拟'),
                 (['Action'], '动作/冒险', '动作/冒险')]
        for genres, main, primary in cases:
            with self.subTest(genres=genres):
                game = {'appid': 1, 'name': 'Fixture', 'genres': genres}
                self.assertEqual(classify_library([game], {})[0]['main_category'], main)
                self.assertEqual(classify_one(game, {})['analysis']['primary'], primary)
        strategy = classify_one({'appid': 1, 'genres': ['Strategy']}, {})
        self.assertEqual(strategy['analysis']['intensity'], '中')
        self.assertEqual(strategy['classification_evidence']['fields']['intensity']['state'], 'inferred')
        racing = classify_one({'appid': 1, 'genres': ['Racing']}, {})
        self.assertEqual(racing['analysis']['intensity'], '未知')
        self.assertEqual(racing['classification_evidence']['fields']['intensity']['state'], 'unknown')

    def test_unknown_and_name_fragments_are_not_genre_evidence(self):
        for name, genres in [('Faction', []), ('Racing', []), ('Fixture', ['不明']),
                             ('Fixture', []), ('Fixture', ['Satisfaction'])]:
            with self.subTest(name=name, genres=genres):
                game = {'appid': 1, 'name': name, 'genres': genres}
                for result, field in ((classify_one(game, {}), 'primary'),
                                      (classify_library([game], {})[0], 'main_category')):
                    self.assertEqual(result.get('analysis', result)[field], '其他')
                    self.assertEqual(result['classification_evidence']['fields'][field]['state'], 'unknown')

    def test_primary_override_invalidates_unspecified_details(self):
        game = {'appid': 1, 'name': 'BioShock', 'genres': ['Action']}
        before = copy.deepcopy(game)
        rules = {'1': {'main_category': '休闲/益智', 'reason': '测试用户校正'}}
        result = classify_one(game, rules)
        self.assertEqual(result['analysis']['primary'], '解谜/休闲')
        self.assertEqual(result['analysis']['sub'], '待核对')
        self.assertEqual(result['analysis']['vibe'], '待核对')
        self.assertEqual(result['analysis']['intensity'], '未知')
        self.assertNotIn('霰弹枪', result['analysis']['slogan'])
        fields = result['classification_evidence']['fields']
        self.assertEqual(fields['primary']['state'], 'reviewed')
        self.assertEqual(fields['sub']['reason'], 'primary_changed')
        self.assertEqual(fields['slogan']['state'], 'generated')
        self.assertEqual(game, before)

    def test_same_primary_retains_heuristics_without_claiming_review(self):
        game = {'appid': 1, 'name': 'BioShock'}
        result = classify_one(game, {'1': {'main_category': '射击', 'reason': '只复核主类'}})
        self.assertEqual(result['analysis']['sub'], '叙事FPS')
        fields = result['classification_evidence']['fields']
        self.assertEqual(fields['primary']['state'], 'reviewed')
        self.assertEqual(fields['sub']['source'], 'known_name')
        self.assertEqual(fields['sub']['state'], 'inferred')

    def test_explicit_details_win_and_sub_change_invalidates_old_slogan(self):
        game = {'appid': 1, 'name': 'BioShock'}
        rule = {'main_category': '射击', 'sub': '用户细分', 'reason': '只核对两个字段'}
        result = classify_one(game, {'1': rule})
        self.assertEqual(result['analysis']['sub'], '用户细分')
        self.assertEqual(result['classification_evidence']['fields']['sub']['state'], 'reviewed')
        self.assertEqual(result['classification_evidence']['fields']['slogan']['state'], 'generated')
        rule.update(main_category='其他', vibe='自定氛围', intensity='低', slogan='自定推荐语')
        result = classify_one(game, {'1': rule})
        self.assertEqual(result['analysis']['slogan'], '自定推荐语')
        self.assertTrue(all(f['state'] == 'reviewed' for f in result['classification_evidence']['fields'].values()))

    def test_publication_freezes_field_evidence_and_preserves_library(self):
        with tempfile.TemporaryDirectory() as directory:
            rows, audit = run_bundle('review', (1,))
            rows[0]['name'] = 'BioShock'
            original = copy.deepcopy(rows)
            rule = {'1': {'main_category': '其他', 'reason': '只核对主类'}}
            target = Path(directory) / 'library.json'
            with patch('classification_overrides.load_overrides', return_value=rule):
                publish_run(target, rows, audit)
            five = json.loads(resolve_artifact(target, 'steam_library_classified.json').read_text(encoding='utf-8'))
            table = json.loads(resolve_artifact(target, 'classified.json').read_text(encoding='utf-8'))
            self.assertEqual(five[0]['classification_evidence']['fields']['sub']['state'], 'unknown')
            self.assertEqual(table[0]['classification_evidence']['fields']['main_category']['state'], 'reviewed')
            self.assertNotEqual(table[0]['classification_evidence']['fields']['tags']['state'], 'reviewed')
            self.assertEqual(rows, original)
            from steam_picker_server import PickerLibrary
            shown = PickerLibrary(target).read()['games']
            self.assertEqual(shown[0]['classification_evidence']['fields']['primary']['state'], 'reviewed')
            self.assertEqual(shown[0]['classification_evidence']['fields']['sub']['state'], 'unknown')

    def test_picker_legacy_evidence_does_not_claim_review_or_expose_extra_fields(self):
        from steam_picker_server import normalized_games
        game = classify_one({'appid': 1, 'name': 'BioShock'}, {})
        game.pop('classification_evidence')
        self.assertEqual(normalized_games([game])[0]['classification_evidence'], {'fields': {}})
        game['classification_evidence'] = {'private': 'do not export', 'fields': {
            'primary': {'source': 'known_name', 'state': 'inferred', 'private': 'do not export'},
            'extra': {'state': 'reviewed'}}}
        self.assertEqual(normalized_games([game])[0]['classification_evidence'], {
            'fields': {'primary': {'source': 'known_name', 'state': 'inferred'}}})
