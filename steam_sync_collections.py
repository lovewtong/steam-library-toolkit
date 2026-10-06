# -*- coding: utf-8 -*-
"""Verified collection-plan preview/export. Legacy Steam storage writes are disabled."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

from steam_runs import manifest_path, resolve_artifact, load_library
from steam_schema import validate_artifacts
from steam_sources import atomic_json, select_for_classification
from steam_picker_server import normalized_games

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / 'config_local.json'
CLASSIFIED_FILE = SCRIPT_DIR / 'steam_library_classified.json'
RESULT_JSON = SCRIPT_DIR / 'steam_collections_result.json'
LIBRARY_FILE = SCRIPT_DIR / 'steam_library.json'
EXPORT_JSON = SCRIPT_DIR / 'steam_collections_export.json'
GROUP_FIELDS = {'intensity': '强度', 'primary': '核心玩法', 'sub': '细分', 'vibe': '氛围',
                'developers': '开发商', 'publishers': '发行商',
                'first_seen_year': '首次观察年份', 'first_seen_month': '首次观察年月'}
DEFAULT_GROUPS = ('intensity', 'primary', 'sub', 'vibe')


class CollectionError(ValueError):
    pass


def appid(value):
    if type(value) is int and 0 < value <= 0xffffffff:
        return value
    if isinstance(value, str) and re.fullmatch(r'[1-9][0-9]{0,9}', value) and int(value) <= 0xffffffff:
        return int(value)
    raise CollectionError('COLLECTION_APPID_INVALID')


def get_owned_appids_from_api(api_key, steam_id):
    """Compatibility helper: unavailable is None, confirmed empty is []; not a write authority."""
    from steam_collect import get_owned_games
    try:
        return [g['appid'] for g in get_owned_games(api_key, steam_id)]
    except (OSError, ValueError, RuntimeError):
        return None


def get_owned_appids_from_library_file():
    """Compatibility read helper; main requires a verified generation instead."""
    if not LIBRARY_FILE.exists() and not manifest_path(LIBRARY_FILE).exists():
        return None
    try:
        return [g['appid'] for g in load_library(LIBRARY_FILE)]
    except (OSError, ValueError):
        return None


def filter_collections(data, owned_appids=None):
    if not isinstance(data, dict):
        raise CollectionError('COLLECTION_FORMAT_INVALID')
    owned = {appid(a) for a in owned_appids} if owned_appids is not None else None
    result, seen = {}, set()
    for name, ids in data.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(ids, list):
            raise CollectionError('COLLECTION_FORMAT_INVALID')
        key = name.strip()
        if key in seen:
            raise CollectionError('COLLECTION_NAME_COLLISION')
        seen.add(key)
        selected = sorted({appid(a) for a in ids})
        if owned is not None:
            selected = [a for a in selected if a in owned]
        if selected:
            result[key] = selected
    return result


def load_collections_from_result_json(owned_appids=None):
    """Legacy pure-data helper. None means no filter; [] means no members."""
    return filter_collections(json.loads(RESULT_JSON.read_text(encoding='utf-8')), owned_appids)


def build_collections(games, owned_appids=None, group_by=DEFAULT_GROUPS):
    if not group_by or any(key not in GROUP_FIELDS for key in group_by):
        raise CollectionError('COLLECTION_GROUP_INVALID')
    games = normalized_games(games)
    owned = {appid(a) for a in owned_appids} if owned_appids is not None else None
    groups = defaultdict(list)
    for game in games:
        aid = appid(game['appid'])
        if owned is not None and aid not in owned:
            continue
        for field in group_by:
            prefix = GROUP_FIELDS[field]
            if field in ('developers', 'publishers'):
                names = game[field]
                labels = ['未知'] if names is None else ['商店或校正明确未列出'] if not names else ['名称-' + n for n in names]
            elif field in ('first_seen_year', 'first_seen_month'):
                labels = [game[field] or '未知']
            else:
                labels = [game['analysis'][field] or '未分类']
            for label in labels:
                groups[prefix + '-' + label].append(aid)
    return {name: sorted(set(ids)) for name, ids in groups.items()}


def load_classified_and_build_collections(owned_appids=None):
    return build_collections(json.loads(CLASSIFIED_FILE.read_text(encoding='utf-8')), owned_appids)


def build_plan(source, account, *, group_by=DEFAULT_GROUPS, developer=None, publisher=None,
               first_seen_year=None, first_seen_month=None):
    if (not isinstance(account, str) or not re.fullmatch(r'[0-9]{17}', account)
            or not 76561197960265728 < int(account) <= 76561197960265728 + 0xffffffff):
        raise CollectionError('COLLECTION_ACCOUNT_INVALID')
    source = Path(source).resolve()
    pointer = source if source.name.endswith('.current.json') else manifest_path(source)
    if not pointer.exists():
        raise CollectionError('COLLECTION_VERIFIED_RUN_REQUIRED')
    before = pointer.read_bytes()
    manifest = json.loads(before)
    directory = resolve_artifact(pointer).parent  # Verify every manifest hash.
    payloads = {}
    for name in ('steam_library.json', 'steam_library.audit.json', 'steam_library_classified.json'):
        raw = (directory / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest['files'].get(name):
            raise CollectionError('COLLECTION_GENERATION_CHANGED')
        payloads[name] = json.loads(raw)
    rows, audit, games = (payloads[n] for n in ('steam_library.json', 'steam_library.audit.json', 'steam_library_classified.json'))
    validate_artifacts(rows, audit)
    if manifest.get('steam_id') != account or audit.get('steam_id') != account:
        raise CollectionError('COLLECTION_ACCOUNT_MISMATCH')
    client = audit.get('sources', {}).get('client_library', {})
    if (audit.get('membership') != 'client_snapshot' or audit.get('status') not in ('ok', 'degraded')
            or client.get('status') != 'ok' or client.get('state') != 'complete'
            or client.get('completeness', {}).get('verified') is not True
            or any(r['membership'].get('state') != 'present' or r['membership'].get('source') != 'client_library' for r in rows)):
        raise CollectionError('COLLECTION_UNVERIFIED_MEMBERSHIP')
    games = normalized_games(games)
    run = manifest['run_id']
    if audit['run_id'] != run or any(r.get('run_id') != run for r in rows + games):
        raise CollectionError('COLLECTION_RUN_MISMATCH')
    eligible = {r['appid'] for r in select_for_classification(rows)}
    if {appid(g['appid']) for g in games} != eligible:
        raise CollectionError('COLLECTION_MEMBERSHIP_MISMATCH')
    if pointer.read_bytes() != before:
        raise CollectionError('COLLECTION_GENERATION_CHANGED')
    from steam_observation import matches_first_seen
    selected = [g for g in games if (developer is None or developer in (g['developers'] or []))
                and (publisher is None or publisher in (g['publishers'] or []))
                and matches_first_seen(g, first_seen_year, first_seen_month)]
    plan = {'schema_version': 1, 'kind': 'steam_collection_plan', 'steam_id': account, 'run_id': run,
            'membership_observed_at': client.get('fetched_at'), 'source_manifest_sha256': hashlib.sha256(before).hexdigest(),
            'membership_count': len(rows), 'eligible_appids': sorted(eligible),
            'ownership_revalidated': False, 'write_supported': False,
            'group_by': list(dict.fromkeys(group_by)),
            'filters': {'developer': developer, 'publisher': publisher,
                        'first_seen_year': first_seen_year, 'first_seen_month': first_seen_month},
            'selected_appids': sorted(appid(g['appid']) for g in selected),
            'collections': build_collections(selected, eligible, group_by)}
    return plan, pointer, before, directory


def export_plan(output, plan, pointer, before, directory):
    output = Path(output).resolve()
    protected = {pointer, pointer.with_name(pointer.name.removesuffix('.current.json') + '.json'),
                 CONFIG_PATH.resolve(), CLASSIFIED_FILE.resolve(), RESULT_JSON.resolve()}
    if output in protected or output.is_relative_to(directory.parent) or output.name.endswith('.current.json'):
        raise CollectionError('COLLECTION_OUTPUT_CONFLICT')
    # A previous plan may be replaced; unrelated files must not be overwritten.
    if output.exists():
        previous = json.loads(output.read_text(encoding='utf-8'))
        if (not isinstance(previous, dict) or previous.get('kind') != 'steam_collection_plan'
                or previous.get('steam_id') != plan['steam_id']):
            raise CollectionError('COLLECTION_OUTPUT_CONFLICT')
    if pointer.read_bytes() != before:
        raise CollectionError('COLLECTION_GENERATION_CHANGED')
    atomic_json(output, plan)


def main(argv=None):
    parser = argparse.ArgumentParser(description='校验运行后预览/导出收藏计划；旧 Steam 写回已停用')
    parser.add_argument('--input', type=Path, default=LIBRARY_FILE)
    parser.add_argument('--account', required=True, help='显式选择与已核验运行一致的 SteamID64')
    parser.add_argument('-o', '--output', type=Path, default=EXPORT_JSON)
    parser.add_argument('--dry-run', action='store_true', help='只读校验和预览，不创建输出或锁文件')
    parser.add_argument('--export-only', action='store_true', help='导出带账号和运行证据的计划；不写 Steam')
    parser.add_argument('--write', action='store_true', help='已停用：拒绝未经验证的旧存储写回')
    parser.add_argument('--group-by', nargs='+', choices=list(GROUP_FIELDS), default=DEFAULT_GROUPS,
                        help='收藏分组维度；developers/publishers 支持一款游戏属于多个厂商')
    parser.add_argument('--developer', help='按开发商名称精确筛选，与发行商条件取交集')
    parser.add_argument('--publisher', help='按发行商名称精确筛选')
    from steam_observation import year_option
    parser.add_argument('--first-seen-year', type=year_option, help='首次观察年份（UTC），或 unknown')
    parser.add_argument('--first-seen-month', choices=[f'{m:02d}' for m in range(1, 13)], help='首次观察月份 01..12（UTC）')
    parser.add_argument('--from-result', action='store_true', help='已停用：平面分类文件没有账号和运行绑定')
    parser.add_argument('--use-api', action='store_true', help='已停用：API 列表不能替代可信客户端成员')
    args = parser.parse_args(argv)
    try:
        if args.from_result or args.use_api:
            raise CollectionError('COLLECTION_LEGACY_SOURCE_DISABLED')
        plan, pointer, before, directory = build_plan(args.input, args.account, group_by=args.group_by,
                                                     developer=args.developer, publisher=args.publisher,
                                                     first_seen_year=args.first_seen_year, first_seen_month=args.first_seen_month)
        if args.write and not args.dry_run:
            raise CollectionError('COLLECTION_WRITE_DISABLED')
        print(f"计划：{len(plan['collections'])} 个收藏，{len(plan['eligible_appids'])} 个 game；运行 {plan['run_id']}")
        print(f"筛选后：{len(plan['selected_appids'])} 个 game")
        print(f"成员观察时间：{plan['membership_observed_at'] or '未知'}；未重新核验当前所有权。")
        if args.dry_run or not args.export_only:
            print('仅预览：未写入输出、备份、锁文件或 Steam 存储。')
            return
        export_plan(args.output, plan, pointer, before, directory)
        print(f'已导出计划：{args.output}；不能直接交给旧写回工具。')
    except CollectionError as exc:
        parser.exit(1, f'收藏计划失败：{exc}\n')
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, '收藏计划失败：COLLECTION_INPUT_INVALID；请检查运行、账号和输出路径。\n')


if __name__ == '__main__':
    main()
