"""Presence-aware store fields and process-wide request pacing."""
from copy import deepcopy
import threading
import time

FIELDS = ('genres', 'categories', 'is_multiplayer', 'is_controller')


class RequestGate:
    def __init__(self, interval=1.5):
        self.interval = interval
        self.lock = threading.Lock()
        self.next_start = 0

    def wait(self):
        with self.lock:
            time.sleep(max(0, self.next_start - time.monotonic()))
            self.next_start = time.monotonic() + self.interval


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
    valid_ids = isinstance(raw, list) and all(isinstance(x, dict) and type(x.get('id')) is int for x in raw)
    ids = {x['id'] for x in raw} if valid_ids else set()
    text_valid = states['categories'] in ('present', 'empty')
    text = ' '.join(details['categories']).casefold()
    for key, positive, keywords in (
        ('is_multiplayer', {1, 9, 27, 36, 37, 38, 39, 47, 48, 49}, ('多人', '合作', 'multi-player', 'co-op', 'shared/split', 'lan')),
        ('is_controller', {18, 28}, ('手柄', '控制器', 'controller')),
    ):
        value = bool(ids & positive) if valid_ids else any(k in text for k in keywords) if text_valid else None
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
