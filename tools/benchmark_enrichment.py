"""R2 measurement wrapper: real transport, unchanged limits, per-trial checkpoints.

Run against a clean repository. Reports and generated libraries may contain personal
library data; keep the output directory local. No credentials are used by this tool.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import statistics
import sys
import threading
import time
from unittest.mock import patch


def digest(value):
    return hashlib.sha256(value).hexdigest()


def without_metadata(row):
    value = deepcopy(row)
    for field in ('run_id', 'genres', 'categories', 'is_multiplayer', 'is_controller'):
        value.pop(field, None)
    value.get('provenance', {}).pop('store_metadata', None)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--phase', choices=('prepare', 'cold', 'warm1', 'warm2', 'warm3', 'subset1', 'subset2', 'subset4', 'summary'), required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve()))
    import steam_collect
    import steam_http
    from steam_enrich import enrich, library_target
    from steam_runs import new_run_metadata, load_library, manifest_path, resolve_artifact
    from steam_sources import atomic_json
    from classification_overrides import load_overrides, read_rules
    source = library_target(args.input)
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    frozen_path = root / 'frozen.json'
    current = new_run_metadata()
    assert current['producer']['dirty'] is False, 'Benchmark requires a clean Git tree'
    assert load_overrides() == read_rules(args.repo / 'classification_overrides.json'), 'Personal overrides require separate review'
    pointer_bytes = manifest_path(source).read_bytes()
    rows = load_library(source)
    audit = json.loads(resolve_artifact(source, 'steam_library.audit.json').read_bytes())
    subset = [500, 550, 730, 241930, 770720, 326480, 627270, 15150]
    signature = {'producer': current['producer'], 'environment': current['environment'],
                 'source_pointer_sha256': digest(pointer_bytes),
                 'source_library_sha256': digest(resolve_artifact(source).read_bytes()),
                 'script_sha256': digest(Path(__file__).read_bytes()),
                 'source_run_id': audit['run_id'], 'records': len(rows),
                 'ordered_appids': [r['appid'] for r in rows], 'subset': subset,
                 'gate_interval_seconds': steam_collect.STORE_GATE.interval}
    if args.phase == 'prepare':
        assert not frozen_path.exists(), 'Use a new output directory'
        assert set(subset) <= {r['appid'] for r in rows}
        atomic_json(frozen_path, {**signature, 'frozen_at': current['started_at'],
                    'phase_order': ['cold', 'warm1', 'warm2', 'warm3', 'subset1', 'subset2', 'subset4']})
        print(json.dumps({k: v for k, v in signature.items() if k not in ('ordered_appids', 'source_run_id')}, ensure_ascii=False))
        return
    frozen = json.loads(frozen_path.read_bytes())
    assert all(frozen[k] == v for k, v in signature.items()), 'Input, environment, code or harness changed'
    if args.phase == 'summary':
        results = [json.loads((root / p / 'report.json').read_bytes()) for p in frozen['phase_order']]
        assert all(r['checks']['passed'] for r in results)
        warm = [r for r in results if r['phase'].startswith('warm')]
        sub = [r for r in results if r['phase'].startswith('subset')]
        result = {'producer': signature['producer'], 'environment': signature['environment'],
                  'source_pointer_sha256': signature['source_pointer_sha256'],
                  'warm_median_seconds': statistics.median(r['wall_seconds'] for r in warm),
                  'warm_range_seconds': [min(r['wall_seconds'] for r in warm), max(r['wall_seconds'] for r in warm)],
                  'warm_semantic_results_equal': len({r['semantic_sha256'] for r in results[:4]}) == 1,
                  'subset_semantic_results_equal': len({r['semantic_sha256'] for r in sub}) == 1,
                  'subset_observation_results_equal': len({r['observations_sha256'] for r in sub}) == 1,
                  'trials': results}
        atomic_json(root / 'summary.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'trials'}, ensure_ascii=False))
        return
    phase_dir = root / args.phase
    assert not phase_dir.exists(), 'A trial is never silently overwritten'
    phase_dir.mkdir()
    index = frozen['phase_order'].index(args.phase)
    if index:
        previous = root / frozen['phase_order'][index - 1] / 'report.json'
        assert previous.exists(), 'Complete trials in frozen order'
    is_subset = args.phase.startswith('subset')
    workers = int(args.phase[-1]) if is_subset else 2
    selected = subset if is_subset else []
    cache = root / ('cache-' + args.phase if is_subset else 'cache-full')
    if not args.phase.startswith('warm'):
        assert not cache.exists(), 'Cold cache must not already exist'
    else:
        assert cache.is_dir(), 'Warm trial needs the previous cache'
    cache_before = {p.name: digest(p.read_bytes()) for p in cache.glob('*.json')}
    output = phase_dir / 'library.json'
    attempts, grants, defers = [], [], []
    trace_lock = threading.Lock()
    original_request = steam_http.request_once
    gate = steam_collect.STORE_GATE
    original_wait, original_defer = gate.wait, gate.defer
    origin = time.monotonic()

    def record_wait(**kwargs):
        result = original_wait(**kwargs)
        with trace_lock:
            grants.append(time.monotonic() - origin)
        return result

    def record_defer(seconds):
        result = original_defer(seconds)
        with trace_lock:
            defers.append({'at': time.monotonic() - origin, 'seconds': seconds})
        return result

    def record_request(url, **kwargs):
        assert url == 'https://store.steampowered.com/api/appdetails', 'Only public store endpoint allowed'
        assert set(kwargs['params']) == {'appids', 'l'}, 'Credentials forbidden'
        event = {'appid': kwargs['params']['appids'], 'start': time.monotonic() - origin}
        try:
            response = original_request(url, **kwargs)
            event['status'] = response.status_code
            return response
        except BaseException as error:
            event['error_type'] = type(error).__name__
            raise
        finally:
            event['end'] = time.monotonic() - origin
            with trace_lock:
                attempts.append(event)

    try:
        with ExitStack() as stack:
            stack.enter_context(patch('steam_http.request_once', side_effect=record_request))
            stack.enter_context(patch.object(gate, 'wait', side_effect=record_wait))
            stack.enter_context(patch.object(gate, 'defer', side_effect=record_defer))
            for name in ('load_config', 'collect_client', 'get_owned_games'):
                stack.enter_context(patch.object(steam_collect, name, side_effect=AssertionError('No credentials or authentication')))
            started = time.monotonic()
            _, metadata = enrich(source, output, cache_dir=cache, appids=selected, workers=workers)
            wall = time.monotonic() - started
        after = load_library(output)  # Validates every file in the new manifest.
        after_audit = json.loads(resolve_artifact(output, 'steam_library.audit.json').read_bytes())
        assert after_audit['producer'] == current['producer']
        assert [r['appid'] for r in rows] == [r['appid'] for r in after]
        assert [without_metadata(r) for r in rows] == [without_metadata(r) for r in after]
        assert manifest_path(source).read_bytes() == pointer_bytes
        load_library(source)  # Revalidate source contents, not just the pointer.
        mutable_audit = {'run_id', 'producer', 'environment', 'started_at', 'operation', 'parent_run',
                         'metadata', 'classification', 'publication', 'previous_run'}
        assert {k: v for k, v in audit.items() if k not in mutable_audit} == {
            k: v for k, v in after_audit.items() if k not in mutable_audit}
        old_snapshot = json.loads(resolve_artifact(source, 'client.snapshot.json').read_bytes())
        new_snapshot = json.loads(resolve_artifact(output, 'client.snapshot.json').read_bytes())
        strip_snapshot = lambda x: {k: v for k, v in x.items() if k not in ('run_id', 'producer')}
        assert strip_snapshot(old_snapshot) == strip_snapshot(new_snapshot)
        per_app = Counter(e['appid'] for e in attempts)
        attempts.sort(key=lambda e: e['start'])
        grants.sort()
        gaps = [b - a for a, b in zip(grants, grants[1:])]
        assert not gaps or min(gaps) >= gate.interval - .02, 'Request gate spacing violated'
        semantic = [{k: v for k, v in r.items() if k not in ('run_id', 'provenance')} for r in after]
        observations = {k: {f: v for f, v in entry.items() if f not in ('source', 'fetched_at', 'read_at', 'cache_hit')}
                        for k, entry in metadata['apps'].items()}
        normalized_hash = lambda v: digest(json.dumps(v, ensure_ascii=False, sort_keys=True).encode('utf-8'))
        cache_after = {p.name: digest(p.read_bytes()) for p in cache.glob('*.json')}
        report = {'phase': args.phase, 'producer': after_audit['producer'], 'run_id': after_audit['run_id'],
                  'wall_seconds': round(wall, 3), 'metadata_seconds': metadata['elapsed_seconds'],
                  'workers': workers, 'selected': len(selected) if selected else len(rows),
                  'records': len(after), 'games': sum(r['app_type'] == 'game' for r in after),
                  'unknown_playtime': sum(r.get('playtime_minutes') is None for r in after),
                  'metadata_state': metadata['state'],
                  'counts': {k: metadata.get(k, 0) for k in ('success', 'not_found', 'access_denied', 'rate_limited',
                            'parse_error', 'transient_error', 'deferred', 'cache_hits', 'cache_misses', 'cache_write_errors')},
                  'http_attempts': len(attempts), 'http_retries': sum(n - 1 for n in per_app.values()),
                  'http_statuses': dict(Counter(str(e.get('status', e.get('error_type'))) for e in attempts)),
                  'gate_grants': len(grants), 'gate_min_gap_seconds': round(min(gaps), 6) if gaps else None,
                  'cooldown_events': len(defers), 'coverage_before': metadata['coverage_before'],
                  'coverage_after': metadata['coverage_after'], 'semantic_sha256': normalized_hash(semantic),
                  'observations_sha256': normalized_hash(observations),
                  'cache_files_before': len(cache_before), 'cache_files_after': len(cache_after),
                  'cache_unchanged': cache_before == cache_after,
                  'checks': {'passed': True, 'members_and_protected_fields_unchanged': True,
                             'collection_audit_and_snapshot_unchanged': True, 'source_unchanged': True,
                             'all_manifest_hashes_valid': True, 'gate_spacing_valid': True}}
        atomic_json(phase_dir / 'transport.json', {'attempts': attempts, 'gate_grants': grants, 'cooldowns': defers})
        atomic_json(phase_dir / 'report.json', report)
        print(json.dumps({k: v for k, v in report.items() if k not in ('run_id', 'coverage_before', 'coverage_after')}, ensure_ascii=False))
    except BaseException as error:
        atomic_json(phase_dir / 'failure.json', {'error_type': type(error).__name__,
                    'source_pointer_unchanged': manifest_path(source).read_bytes() == pointer_bytes,
                    'http_attempts': len(attempts)})
        atomic_json(phase_dir / 'transport.json', {'attempts': attempts, 'gate_grants': grants, 'cooldowns': defers})
        raise


if __name__ == '__main__':
    main()
