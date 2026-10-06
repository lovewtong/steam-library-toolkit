"""Account-scoped first observations; dates describe available history, not purchases."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from steam_membership import trusted_current_membership

OBSERVATION_SOURCES = ('client_library', 'saved_client_snapshot', 'family_library', 'saved_family_snapshot')


def utc_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def first_seen_fields(row):
    evidence = row.get('first_seen_evidence')
    evidence = evidence if isinstance(evidence, dict) else {}
    at = utc_timestamp(row.get('first_seen_at'))
    if (evidence.get('state') not in ('observed', 'historical')
            or evidence.get('source') not in OBSERVATION_SOURCES):
        at = None
    return {'first_seen_at': at, 'first_seen_year': at[:4] if at else None,
            'first_seen_month': at[:7] if at else None,
            'first_seen_status': evidence.get('state') if at else 'unknown',
            'first_seen_source': evidence.get('source') if at else None}


def trusted_client(audit):
    return trusted_current_membership(audit)


def attach_first_seen(output, rows, audit, *, history_from=None):
    """Called by collection under its output lock; the ledger commits with the run."""
    from steam_runs import manifest_path, resolve_artifact
    from steam_sources import AccountMismatchError
    account = audit.get('steam_id')
    ledger = {}
    targets = [Path(output)]
    if history_from is not None:
        targets.append(Path(history_from))
    for target in dict.fromkeys(targets):
        pointer = target if target.name.endswith('.current.json') else manifest_path(target)
        if not pointer.exists():
            if history_from is not None and target == Path(history_from):
                raise ValueError('OBSERVATION_HISTORY_INVALID：历史来源必须有已核验运行指针')
            continue
        before = pointer.read_bytes()
        path = resolve_artifact(pointer)
        previous = json.loads((path.parent / 'steam_library.audit.json').read_bytes())
        if previous.get('steam_id') != account:
            raise AccountMismatchError('ACCOUNT_MISMATCH：观察历史属于其他账号')
        if not trusted_client(previous):
            if history_from is not None and target == Path(history_from):
                raise ValueError('OBSERVATION_HISTORY_INVALID：候选库不能用作首次观察历史')
            continue
        history = previous.get('observation_history', {})
        if not isinstance(history, dict):
            raise ValueError('OBSERVATION_HISTORY_INVALID：观察历史无效')
        old_rows = json.loads(path.read_bytes())
        entries = deepcopy(history.get('apps', {}))
        if not isinstance(entries, dict):
            raise ValueError('OBSERVATION_HISTORY_INVALID：观察历史无效')
        # Seed only from a verified saved client observation, never from file mtime.
        for row in old_rows:
            key = str(row['appid'])
            member_source = row.get('membership', {}).get('source')
            saved_at = utc_timestamp(previous.get('sources', {}).get(member_source, {}).get('fetched_at'))
            if key not in entries and saved_at:
                entries[key] = {'at': saved_at, 'state': 'historical',
                                'source': 'saved_family_snapshot' if member_source == 'family_library' else 'saved_client_snapshot',
                                'steam_id': account, 'run_id': previous['run_id']}
        for key, entry in entries.items():
            if (not isinstance(key, str) or not key.isascii() or not key.isdigit()
                    or str(int(key)) != key or not 0 < int(key) <= 0xffffffff
                    or not isinstance(entry, dict) or entry.get('steam_id') != account
                    or not utc_timestamp(entry.get('at'))
                    or entry.get('state') not in ('observed', 'historical')
                    or entry.get('source') not in OBSERVATION_SOURCES
                    or not isinstance(entry.get('run_id'), str) or not entry['run_id']):
                raise ValueError('OBSERVATION_HISTORY_INVALID：观察历史无效')
            entry['at'] = utc_timestamp(entry['at'])
            if key not in ledger or entry['at'] < ledger[key]['at']:
                ledger[key] = entry
        if pointer.read_bytes() != before:
            raise ValueError('GENERATION_MISMATCH：观察历史在读取时发生变化')
    trusted = trusted_client(audit)
    for row in rows:
        key = str(row['appid'])
        member_source = row.get('membership', {}).get('source')
        now = utc_timestamp(audit.get('sources', {}).get(member_source, {}).get('fetched_at')) if trusted else None
        if now and key not in ledger:
            ledger[key] = {'at': now, 'state': 'observed', 'source': member_source,
                           'steam_id': account, 'run_id': audit['run_id']}
        entry = ledger.get(key) if trusted else None
        row['first_seen_at'] = entry['at'] if entry else None
        row['first_seen_evidence'] = {k: v for k, v in entry.items() if k != 'at'} if entry else {'state': 'unknown'}
    audit['observation_history'] = {'schema_version': 1,
                                    'scope': 'available_membership_history' if audit.get('membership') == 'accessible_snapshot' else 'available_client_history',
                                    'steam_id': account, 'apps': ledger if trusted else {}}


def matches_first_seen(game, year=None, month=None):
    fields = first_seen_fields(game)
    return ((not year or (fields['first_seen_year'] or 'unknown') == year)
            and (not month or bool(fields['first_seen_month']) and fields['first_seen_month'][5:7] == month))


def year_option(value):
    if value == 'unknown' or len(value) == 4 and value.isascii() and value.isdigit() and 1 <= int(value) <= 9999:
        return value
    import argparse
    raise argparse.ArgumentTypeError('年份应为四位数字或 unknown')
