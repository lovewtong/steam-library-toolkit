"""Publish new classifications from a verified run without network or authentication."""
import argparse
import json
from pathlib import Path
from steam_lock import collection_lock
from steam_runs import resolve_artifact, manifest_path, new_run_metadata, publish_run, check_previous
from steam_schema import validate_artifacts
from steam_enrich import library_target


def reclassify(source, output):
    source, output = library_target(source), library_target(output)
    if source == output:
        raise ValueError('RECLASSIFY_OUTPUT_CONFLICT：请使用独立输出路径')
    with collection_lock(output, extra_paths=(source,)):
        if not manifest_path(source).exists():
            raise ValueError('RECLASSIFY_SOURCE_INVALID：需要已核验运行指针')
        path = resolve_artifact(source)
        rows = json.loads(path.read_text(encoding='utf-8'))
        audit = json.loads(resolve_artifact(source, 'steam_library.audit.json').read_text(encoding='utf-8'))
        validate_artifacts(rows, audit)
        if (audit['membership'] != 'client_snapshot' or audit['status'] == 'suspicious_change'
                or any(r.get('run_id') != audit['run_id'] for r in rows)):
            raise ValueError('RECLASSIFY_SOURCE_INVALID：需要可信客户端成员运行')
        parent = {'run_id': audit['run_id'], 'producer': audit.get('producer'), 'generated_at': audit.get('generated_at')}
        audit.update(new_run_metadata(), parent_run=parent, operation='classification_rebuild')
        audit.pop('publication', None)
        audit.pop('previous_run', None)
        for row in rows:
            row['run_id'] = audit['run_id']
        if (path.parent / 'client.snapshot.json').exists():
            snapshot = json.loads(resolve_artifact(source, 'client.snapshot.json').read_text(encoding='utf-8'))
            snapshot.update(run_id=audit['run_id'], producer=audit['producer'])
            audit['snapshot'] = snapshot
        check_previous(output, rows, audit)
        if audit['status'] == 'suspicious_change':
            raise ValueError('RECLASSIFY_SOURCE_INVALID：目标成员缩减超过保护阈值')
        return publish_run(output, rows, audit)


def main():
    parser = argparse.ArgumentParser(description='离线重建已核验库的分类，不认证、不请求商店')
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('-o', '--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        output, pointer, warnings = reclassify(args.input, args.output)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError):
        parser.exit(1, '重建失败：请检查输入运行、校正规则和独立输出路径\n')
    except KeyboardInterrupt:
        parser.exit(130, '已取消；以 current.json 指向的完整运行为准\n')
    print(f'输出：{output}\n运行指针：{pointer}')
    for warning in warnings:
        print(warning)


if __name__ == '__main__':
    main()
