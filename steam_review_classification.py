"""Triage frozen classifications offline; never infer corrections or modify rules."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile

from classification_overrides import MAIN_TO_PRIMARY, read_rules
from steam_picker_server import normalized_games
from steam_runs import manifest_path, resolve_artifact
from steam_schema import validate_artifacts
from steam_sources import select_for_classification

ROOT = Path(__file__).resolve().parent
RESERVED_OUTPUTS = {ROOT / name for name in ('config_local.json', 'classification_overrides.json',
                                            'classification_overrides.local.json')}

REASONS = {
    'primary_disagreement': '表格与 picker 主类不同',
    'primary_unknown': '主类未知',
    'evidence_missing': '主类依据缺失或旧格式',
    'name_heuristic': '主类依赖名称规则',
    'primary_unreviewed': '主类尚未人工确认',
}


def primary_evidence(game, field):
    evidence = game.get('classification_evidence')
    fields = evidence.get('fields') if isinstance(evidence, dict) else None
    result = fields.get(field) if isinstance(fields, dict) else None
    return result if isinstance(result, dict) else {}


def build_review(source):
    """Use only saved values, never current name rules or personal overrides."""
    source = Path(source).resolve()
    pointer = source if source.name.endswith('.current.json') else manifest_path(source)
    if not pointer.is_file():
        raise ValueError('REVIEW_VERIFIED_RUN_REQUIRED')
    before = pointer.read_bytes()
    manifest = json.loads(before)
    directory = resolve_artifact(pointer).parent

    def read(name):
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['files'].get(name):
            raise ValueError('REVIEW_GENERATION_CHANGED')
        return json.loads(raw)

    rows = read('steam_library.json')
    audit = read('steam_library.audit.json')
    table = read('classified.json')
    games = normalized_games(read('steam_library_classified.json'))
    read('classification_overrides.json')
    rules = read_rules(directory / 'classification_overrides.json')
    validate_artifacts(rows, audit)
    client = audit.get('sources', {}).get('client_library', {})
    if (audit.get('membership') != 'client_snapshot' or audit.get('status') not in ('ok', 'degraded')
            or client.get('status') != 'ok' or client.get('state') != 'complete'
            or client.get('completeness', {}).get('verified') is not True
            or any(r['membership'].get('state') != 'present'
                   or r['membership'].get('source') != 'client_library' for r in rows)):
        raise ValueError('REVIEW_UNVERIFIED_MEMBERSHIP')
    if manifest.get('steam_id') != audit.get('steam_id'):
        raise ValueError('REVIEW_ACCOUNT_MISMATCH')
    run = manifest['run_id']
    if not isinstance(table, list) or any(not isinstance(r, dict) for r in table):
        raise ValueError('REVIEW_TABLE_INVALID')
    if audit['run_id'] != run or any(r.get('run_id') != run for r in rows + table + games):
        raise ValueError('REVIEW_RUN_MISMATCH')
    selected = {r['appid']: r for r in select_for_classification(rows)}
    if (any(type(r.get('appid')) is not int or r.get('main_category') not in MAIN_TO_PRIMARY for r in table)
            or len(table) != len(selected) or {r['appid'] for r in table} != set(selected)
            or {int(g['appid']) for g in games} != set(selected)
            or not set(rules) <= {str(a) for a in selected}):
        raise ValueError('REVIEW_MEMBERSHIP_MISMATCH')
    tables = {r['appid']: r for r in table}
    items = []
    for game in games:
        aid = int(game['appid'])
        row, tab = selected[aid], tables[aid]
        table_primary = MAIN_TO_PRIMARY[tab['main_category']]
        five_evidence = primary_evidence(game, 'primary')
        table_evidence = primary_evidence(tab, 'main_category')
        reasons = []
        if game['analysis']['primary'] != table_primary:
            reasons.append('primary_disagreement')
        if (game['analysis']['primary'] == '其他' or tab['main_category'] == '其他'
                or any(e.get('state') == 'unknown' for e in (five_evidence, table_evidence))):
            reasons.append('primary_unknown')
        if any(e.get('state') not in ('reviewed', 'inferred', 'unknown') or not e.get('source')
               for e in (five_evidence, table_evidence)):
            reasons.append('evidence_missing')
        if five_evidence.get('source') == 'known_name':
            reasons.append('name_heuristic')
        if any(e.get('state') != 'reviewed' for e in (five_evidence, table_evidence)):
            reasons.append('primary_unreviewed')
        if not reasons:
            continue
        urgent = any(r in reasons for r in ('primary_disagreement', 'primary_unknown', 'evidence_missing'))
        priority = 1 if urgent else 2 if 'name_heuristic' in reasons else 3
        items.append({'appid': aid, 'name': row['name'], 'priority': priority, 'reasons': reasons,
                      'genres': deepcopy(row.get('genres', [])),
                      'table': {'main_category': tab['main_category'], 'mapped_primary': table_primary,
                                'primary_evidence': deepcopy(table_evidence)},
                      'picker': {'analysis': deepcopy(game['analysis']),
                                 'evidence': deepcopy(game['classification_evidence'])},
                      'applied_override': deepcopy(rules.get(str(aid)))})
    items.sort(key=lambda item: (item['priority'], item['appid']))
    report = {'schema_version': 1, 'kind': 'classification_review_queue', 'scope': 'primary_classification',
              'run_id': run, 'source_manifest_sha256': hashlib.sha256(before).hexdigest(),
              'source_producer': audit.get('producer'), 'membership_observed_at': client.get('fetched_at'),
              'summary': {'games': len(games), 'queued': len(items), 'not_queued': len(games) - len(items),
                          'reason_counts': dict(Counter(r for item in items for r in item['reasons']))},
              'reason_labels': REASONS.copy(), 'items': items}
    if pointer.read_bytes() != before:
        raise ValueError('REVIEW_GENERATION_CHANGED')
    return report, pointer, before, directory


def export_review(output, report, pointer, before, directory):
    output = Path(output).resolve()
    library = pointer.with_name(pointer.name.removesuffix('.current.json') + '.json')
    if (output.exists() or output == library or output in RESERVED_OUTPUTS or output.name.endswith('.current.json')
            or output.is_relative_to(directory.parent)):
        raise ValueError('REVIEW_OUTPUT_CONFLICT')
    if pointer.read_bytes() != before:
        raise ValueError('REVIEW_GENERATION_CHANGED')
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=output.name + '.', suffix='.tmp', dir=output.parent)
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        if pointer.read_bytes() != before:
            raise ValueError('REVIEW_GENERATION_CHANGED')
        # Publish complete bytes without replacing an entry created after our precheck.
        # Keep the temporary on the same filesystem; unsupported hard links fail closed.
        os.link(temporary, output)
    finally:
        os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description='只读分析已保存分类，生成主类待复核清单；不修改库或规则')
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('-o', '--output', type=Path, help='可选导出到全新的本地 JSON；不覆盖已有文件')
    parser.add_argument('--limit', type=int, default=20, help='终端最多展示多少项；导出始终包含完整队列')
    args = parser.parse_args(argv)
    if args.limit < 0:
        parser.error('--limit 必须为非负整数')
    try:
        report, pointer, before, directory = build_review(args.input)
        if args.output:
            export_review(args.output, report, pointer, before, directory)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, '复核清单失败：请检查完整运行、成员证据和全新的输出路径。\n')
    summary = report['summary']
    print(f"主类待复核：{summary['queued']}/{summary['games']}；运行 {report['run_id']}")
    print('原因可重叠；差异不等于错误，未入队也不代表全部字段已审核。')
    for reason, count in summary['reason_counts'].items():
        print(f'  {REASONS[reason]}：{count}')
    for item in report['items'][:args.limit]:
        name = json.dumps(item['name'], ensure_ascii=False)
        table = json.dumps(item['table']['main_category'], ensure_ascii=False)
        primary = json.dumps(item['picker']['analysis']['primary'], ensure_ascii=False)
        print(f"P{item['priority']} AppID {item['appid']} {name}：表格 {table} / picker {primary}")
    if args.output:
        print(f'完整清单已导出：{args.output}（含个人游戏清单，请保存在本地）')
    print('核对后编辑 classification_overrides.local.json，再用 steam_reclassify.py 发布独立运行并重新检查。')


if __name__ == '__main__':
    main()
