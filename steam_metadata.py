"""Presence-aware store fields and process-wide request pacing."""
from copy import deepcopy
import threading
import time
from steam_http import check_cancel, SourceCoolingDown, wait_delay

FIELDS = ('genres', 'categories', 'is_multiplayer', 'is_controller')


class RequestGate:
    def __init__(self, interval=1.5):
        self.interval = interval
        self.lock = threading.Lock()
        self.next_start = 0
        self.cooldown_until = 0

    def defer(self, seconds):
        with self.lock:
            self.cooldown_until = max(self.cooldown_until, time.monotonic() + seconds)

    def wait(self, *, deadline=float('inf'), cancel_event=None):
        while True:
            check_cancel(cancel_event)
            with self.lock:
                now = time.monotonic()
                ready = max(self.next_start, self.cooldown_until)
                if ready >= deadline:
                    raise SourceCoolingDown('STORE_COOLDOWN')
                if now >= ready:
                    self.next_start = now + self.interval
                    return
            wait_delay(min(.05, ready - now), deadline, cancel_event)


STORE_GATE = RequestGate()


def parse_fields(data):
    details, states = {}, {}
    for key in ('genres', 'categories'):
        raw = data.get(key)
        valid = isinstance(raw, list) and all(isinstance(x, dict) and
                    isinstance(x.get('description'), str) and x['description'].strip() for x in raw)
        states[key] = ('present' if raw else 'empty') if valid else 'missing' if key not in data else 'invalid'
        details[key] = [x['description'].strip() for x in raw] if valid else []
    raw = data.get('categories')
    def has_id(entry):
        return isinstance(entry, dict) and type(entry.get('id')) is int and entry['id'] > 0

    valid_ids = isinstance(raw, list) and all(has_id(x) for x in raw)
    entries = raw if isinstance(raw, list) else []
    ids = {x['id'] for x in entries if has_id(x)}
    text = ' '.join(x['description'] for x in entries
                    if isinstance(x, dict) and isinstance(x.get('description'), str)).casefold()
    for key, positive, keywords in (
        ('is_multiplayer', {1, 9, 27, 36, 37, 38, 39, 47, 48, 49}, ('多人', '合作', 'multi-player', 'co-op', 'shared/split', 'lan')),
        ('is_controller', {18, 28}, ('手柄', '控制器', 'controller')),
    ):
        # Positive evidence survives malformed siblings; incomplete lists cannot prove absence.
        value = True if ids & positive or any(k in text for k in keywords) else False if valid_ids else None
        # The explicit controller field can establish support even without categories.
        if key == 'is_controller' and data.get('controller_support') in ('full', 'partial'):
            value = True
        details[key] = value
        states[key] = 'known' if value is not None else 'missing'
    details['field_states'] = states
    return details


def merge_fields(row, details):
    """A successful but incomplete response must not erase prior observations."""
    states = details.get('field_states', {})
    applied = []
    for key in FIELDS:
        if states.get(key) in ('missing', 'invalid') or details.get(key) is None:
            continue
        row[key] = deepcopy(details[key])
        applied.append(key)
    return applied


def coverage(rows):
    result = {}
    for key in FIELDS:
        if key in ('genres', 'categories'):
            result[key] = {'nonempty': sum(bool(r.get(key)) for r in rows),
                           'empty_or_unknown': sum(not r.get(key) for r in rows)}
        else:
            result[key] = {state: sum(r.get(key) is value for r in rows)
                           for state, value in (('true', True), ('false', False), ('unknown', None))}
    return result


def apply_observation(row, details, stats, observation, metadata):
    state = next((s for s in ('success', 'not_found', 'access_denied', 'rate_limited',
                              'parse_error', 'transient_error', 'deferred') if stats.get(s)), 'unavailable')
    applied = merge_fields(row, details) if details is not None else []
    states = details.get('field_states', {}) if details is not None else {}
    source = observation.get('source', 'store_cache')
    entry = {'state': state, 'cache_hit': bool(stats.get('cache_hits')), **observation}
    if details is not None:
        entry.update(fields=states, applied_fields=applied)
    entry['field_actions'] = {key: {'action': 'updated' if key in applied else 'retained',
        'reason': 'observed' if key in applied else states.get(key, state)} for key in FIELDS}
    metadata.setdefault('apps', {})[str(row['appid'])] = entry
    for key, value in stats.items():
        metadata[key] = metadata.get(key, 0) + value
    if applied:
        row.setdefault('provenance', {})['store_metadata'] = source
