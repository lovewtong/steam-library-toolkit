"""Validated AppID corrections shared by both classifiers; no library fields are edited."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN_TO_PRIMARY = {'射击': '射击 (FPS/TPS)', '动作/冒险': '动作/冒险', 'RPG': '角色扮演 (RPG)',
                   '策略': '策略/模拟', '模拟经营': '策略/模拟', '休闲/益智': '解谜/休闲',
                   '体育/竞速': '体育/竞速', '独立/其他': '独立/叙事', '其他': '其他'}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('CLASSIFICATION_OVERRIDE_INVALID：重复字段或 AppID')
        result[key] = value
    return result


def read_rules(path):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique_object)
        if (not isinstance(data, dict) or set(data) != {'schema_version', 'apps'}
                or type(data['schema_version']) is not int or data['schema_version'] != 1
                or not isinstance(data['apps'], dict)):
            raise ValueError()
        result = {}
        allowed = {'main_category', 'reason', 'reference', 'sub', 'vibe', 'intensity', 'slogan'}
        for appid, rule in data['apps'].items():
            if (not appid.isascii() or not appid.isdigit() or str(int(appid)) != appid
                    or not 0 < int(appid) <= 0xffffffff or not isinstance(rule, dict)
                    or not {'main_category', 'reason'} <= set(rule) or not set(rule) <= allowed
                    or any(not isinstance(v, str) or not v.strip() or len(v) > 2000 for v in rule.values())):
                raise ValueError()
            rule = {k: v.strip() for k, v in rule.items()}
            if rule['main_category'] not in MAIN_TO_PRIMARY or ('intensity' in rule and rule['intensity'] not in {'低', '中', '高'}):
                raise ValueError()
            result[appid] = rule
        return result
    except (ValueError, TypeError, KeyError):
        raise ValueError('CLASSIFICATION_OVERRIDE_INVALID：校正规则格式无效') from None


def load_overrides(local_path=None):
    result = read_rules(ROOT / 'classification_overrides.json')
    local = Path(local_path) if local_path is not None else ROOT / 'classification_overrides.local.json'
    if local.exists():
        # A local entry replaces the entire built-in entry; no hidden field inheritance.
        result.update(read_rules(local))
    return result


def correction(game, rules):
    appid = game.get('appid')
    return rules.get(str(appid)) if type(appid) is int or isinstance(appid, str) else None


def evidence(rule):
    return {'source': 'appid_override', 'reason': rule['reason'],
            **({'reference': rule['reference']} if 'reference' in rule else {})}
