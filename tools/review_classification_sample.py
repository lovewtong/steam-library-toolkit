"""Replay the fixed editorial sample offline; passing is not a full-library accuracy score."""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from classification_overrides import read_rules
from classify_games import classify_library
from classify_steam_games import classify_one
from steam_sources import atomic_json

FIXTURE = ROOT / 'tests/fixtures/classification-r1.json'


def evaluate():
    fixture = json.loads(FIXTURE.read_text(encoding='utf-8'))
    rules = read_rules(ROOT / 'classification_overrides.json')  # Never load personal rules.
    results = []
    for sample in fixture['samples']:
        game = {key: copy.deepcopy(sample[key]) for key in ('appid', 'name', 'genres')}
        before = copy.deepcopy(game)
        table = classify_library([game], rules)[0]
        five = classify_one(game, rules)
        actual = {'main_category': table['main_category'],
                  **{k: five['analysis'][k] for k in ('primary', 'sub')}}
        mismatches = [key for key in actual if actual[key] != sample['expected'][key]]
        if game != before:
            mismatches.append('input_mutated')
        results.append({**sample, 'actual': actual, 'mismatches': mismatches,
                        'fields': five['classification_evidence']['fields'],
                        'table_fields': table['classification_evidence']['fields']})
    return {'schema_version': 1, 'baseline_commit': fixture['baseline_commit'],
            'reviewed_at': fixture['reviewed_at'], 'scope': fixture['scope'],
            'samples': len(results), 'matched': sum(not r['mismatches'] for r in results),
            'evidence_status': dict(Counter(r['evidence_status'] for r in results)),
            'builtin_rules': len(rules), 'results': results}


def main():
    parser = argparse.ArgumentParser(description='离线重放固定 R1 分类样本；不联网、不读取个人规则')
    parser.add_argument('-o', '--output', type=Path, help='可选本地报告路径')
    args = parser.parse_args()
    report = evaluate()
    if args.output:
        atomic_json(args.output, report)
    print(f"R1: {report['matched']}/{report['samples']} 结果符合预期；内置校正 {report['builtin_rules']} 条")
    print('证据状态：' + json.dumps(report['evidence_status'], ensure_ascii=False))
    print('样本回归不等于全部样本均有新证据，也不是全库准确率。')
    return int(report['matched'] != report['samples'])


if __name__ == '__main__':
    sys.exit(main())
