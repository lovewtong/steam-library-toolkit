"""Enrich an existing verified generation without authenticating or changing membership."""
from copy import deepcopy
import json
from pathlib import Path

from steam_collect import cached_store_details, OUTPUT_FILE
from steam_lock import collection_lock
from steam_runs import (check_previous, manifest_path, new_run_metadata, publish_run,
                        resolve_artifact)
from steam_schema import validate_artifacts
from steam_sources import utc_now


def library_target(path):
    path = Path(path).resolve()
    if path.name.endswith('.current.json'):
        path = path.with_name(path.name[:-len('.current.json')] + '.json')
    return path


def enrich(source, output, *, cache_dir=None, refresh=False, appids=()):
    source, output = library_target(source), library_target(output)
    if source == output:
        raise ValueError('ENRICH_OUTPUT_CONFLICT：补全结果必须使用独立输出路径')
    with collection_lock(output, extra_paths=(source,)):
        if not manifest_path(source).exists():
            raise ValueError('ENRICH_SOURCE_INVALID：需要带 current.json 指针的已核验运行')
        library_path = resolve_artifact(source)
        audit_path = resolve_artifact(source, 'steam_library.audit.json')
        if library_path.parent != audit_path.parent:
            raise ValueError('GENERATION_MISMATCH：源运行在读取时发生变化')
        rows = json.loads(library_path.read_text(encoding='utf-8'))
        audit = json.loads(audit_path.read_text(encoding='utf-8'))
        validate_artifacts(rows, audit)
        if (audit['membership'] != 'client_snapshot' or audit['status'] == 'suspicious_change'
                or any(r.get('run_id') != audit['run_id'] for r in rows)):
            raise ValueError('ENRICH_SOURCE_INVALID：需要可信客户端成员运行')
        selected = set(appids) if appids else {r['appid'] for r in rows}
        if not selected <= {r['appid'] for r in rows}:
            raise ValueError('ENRICH_APPID_INVALID：指定应用不在源库中')
        parent = {'run_id': audit['run_id'], 'producer': deepcopy(audit.get('producer')),
                  'generated_at': audit.get('generated_at')}
        # Keep collection timestamps and evidence: this command does not refresh ownership.
        audit.pop('publication', None)
        audit.pop('previous_run', None)
        audit.update(new_run_metadata())
        audit['operation'] = 'metadata_enrichment'
        audit['parent_run'] = parent
        check_previous(output, rows, audit)
        if audit['status'] == 'suspicious_change':
            raise RuntimeError('SUSPICIOUS_REMOVAL：目标现有成员与源库差异过大，请使用新的输出路径')
        metadata = {'enabled': True, 'scope': 'selected_apps' if appids else 'all_apps',
                    'requested': len(selected), 'apps': {}, 'started_at': utc_now()}
        audit['metadata'] = metadata
        snapshot_path = library_path.parent / 'client.snapshot.json'
        if snapshot_path.exists():
            snapshot_path = resolve_artifact(source, 'client.snapshot.json')
            snapshot = json.loads(snapshot_path.read_text(encoding='utf-8'))
            snapshot.update(run_id=audit['run_id'], producer=audit['producer'])
            audit['snapshot'] = snapshot
        completed = 0
        for row in rows:
            row['run_id'] = audit['run_id']
            if row['appid'] not in selected:
                continue
            stats = {}
            details = cached_store_details(row['appid'], cache_dir or OUTPUT_FILE.parent / '.steam_cache',
                                           refresh, stats)
            state = next((s for s in ('success', 'not_found', 'access_denied', 'rate_limited',
                                      'parse_error', 'transient_error') if stats.get(s)), 'unavailable')
            metadata['apps'][str(row['appid'])] = {'state': state, 'cache_hit': bool(stats.get('cache_hits'))}
            for key, value in stats.items():
                metadata[key] = metadata.get(key, 0) + value
            if details is not None:
                for key in ('genres', 'categories', 'is_multiplayer', 'is_controller'):
                    row[key] = deepcopy(details[key])
                row.setdefault('provenance', {})['store_metadata'] = 'store_cache'
            completed += 1
            if completed % 25 == 0 or completed == len(selected):
                print(f'补全商店元数据：{completed}/{len(selected)}', flush=True)
        metadata['finished_at'] = utc_now()
        metadata['state'] = 'complete' if metadata.get('success', 0) == len(selected) else 'partial'
        # Metadata failures preserve previous values; app types, membership and times never change.
        result = publish_run(output, rows, audit)
        return result, metadata


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='补全已核验 Steam 库的商店元数据，不重新认证或采集成员')
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('-o', '--output', required=True, type=Path)
    parser.add_argument('--appid', action='append', type=int, default=[], help='仅补全指定应用；可重复')
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--refresh-metadata', action='store_true')
    args = parser.parse_args(argv)
    try:
        (output, pointer, warnings), metadata = enrich(args.input, args.output, cache_dir=args.cache_dir,
                                                       refresh=args.refresh_metadata, appids=args.appid)
    except KeyboardInterrupt:
        print('已取消补全；请以 current.json 指向的完整运行为准')
        return 130
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        # Arbitrary paths, response bodies and instance values must not leak from errors.
        code = str(error).split('：', 1)[0]
        allowed = {'ENRICH_OUTPUT_CONFLICT', 'ENRICH_SOURCE_INVALID', 'ENRICH_APPID_INVALID',
                   'GENERATION_MISMATCH', 'GENERATION_INVALID', 'SCHEMA_INVALID',
                   'SUSPICIOUS_REMOVAL', 'ACCOUNT_MISMATCH', 'OUTPUT_BUSY'}
        code = code if code in allowed else 'ENRICH_FAILED'
        print(f'补全失败：{code}；请检查源运行、应用编号和独立输出路径')
        return 1
    print(f"补全状态：{metadata['state']}；成功：{metadata.get('success', 0)}/{metadata['requested']}")
    print(f'输出：{output}\n运行指针：{pointer}')
    for warning in warnings:
        print(warning)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
