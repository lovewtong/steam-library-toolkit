"""Parent-enforced total HTTP deadline, cancellation and bounded response bodies."""
import base64
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time
from email.utils import parsedate_to_datetime
import requests


class RequestCancelled(RuntimeError):
    pass


class SourceCoolingDown(requests.RequestException):
    pass


def check_cancel(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise RequestCancelled('HTTP_CANCELLED')


def wait_delay(delay, deadline, cancel_event=None):
    until = min(time.monotonic() + delay, deadline)
    while time.monotonic() < until:
        check_cancel(cancel_event)
        time.sleep(max(0, min(.05, until - time.monotonic())))
    check_cancel(cancel_event)


def request_once(url, *, params, timeout, deadline, cancel_event=None, max_bytes=8 * 1024 * 1024):
    check_cancel(cancel_event)
    if time.monotonic() >= deadline:
        raise requests.Timeout('HTTP_DEADLINE_EXCEEDED')
    # Killable isolation also bounds DNS, TLS and slow-drip bodies, not just socket inactivity.
    process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('steam_http_worker.py'))],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    payload = json.dumps({'url': url, 'params': params, 'timeout': timeout, 'max_bytes': max_bytes}).encode('utf-8')
    try:
        while True:
            check_cancel(cancel_event)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise requests.Timeout('HTTP_DEADLINE_EXCEEDED')
            try:
                output, _ = process.communicate(input=payload, timeout=min(.1, remaining))
                break
            except subprocess.TimeoutExpired:
                payload = None
        check_cancel(cancel_event)
        if time.monotonic() >= deadline:
            raise requests.Timeout('HTTP_DEADLINE_EXCEEDED')
        result = json.loads(output)
        if result.get('error') == 'HTTP_TIMEOUT':
            raise requests.Timeout('HTTP_TIMEOUT')
        if result.get('error') == 'HTTP_RESPONSE_TOO_LARGE':
            raise requests.RequestException('HTTP_RESPONSE_TOO_LARGE')
        if result.get('error'):
            raise requests.ConnectionError('HTTP_TRANSPORT_FAILED')
        response = requests.Response()
        response.status_code = result['status']
        response.headers.update(result['headers'])
        response._content = base64.b64decode(result['body'])
        return response
    except (ValueError, KeyError, TypeError):
        raise requests.ConnectionError('HTTP_WORKER_INVALID') from None
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=2)


def get_response(url, *, params, timeout, stats=None, gate=None, cancel_event=None,
                 total_timeout=35, max_bytes=8 * 1024 * 1024):
    deadline = time.monotonic() + total_timeout
    for attempt in range(1, 4):
        check_cancel(cancel_event)
        if gate is not None:
            gate.wait(deadline=deadline, cancel_event=cancel_event)
        if time.monotonic() >= deadline:
            raise requests.Timeout('HTTP_DEADLINE_EXCEEDED')
        if stats is not None:
            stats["attempts"] = attempt
        response, error, retry_after = None, None, 0
        try:
            response = request_once(url, params=params, timeout=min(timeout, deadline - time.monotonic()),
                                    deadline=deadline, cancel_event=cancel_event, max_bytes=max_bytes)
            if response.status_code not in (408, 429, 500, 502, 503, 504):
                return response
            header = response.headers.get("Retry-After")
            if isinstance(header, str):
                try:
                    retry_after = float(header) if header.isdigit() else parsedate_to_datetime(header).timestamp() - time.time()
                    if not math.isfinite(retry_after):
                        retry_after = 0
                except (ValueError, TypeError, OverflowError):
                    pass
        except (requests.Timeout, requests.ConnectionError, requests.exceptions.ChunkedEncodingError) as exc:
            error = exc
        delay = max(retry_after, .25 * 2 ** (attempt - 1) * random.uniform(.75, 1.25))
        if gate is not None and response is not None and response.status_code in (429, 503):
            gate.defer(delay)
        if attempt == 3 or delay >= deadline - time.monotonic():
            if error:
                raise error
            return response
        if response is not None:
            response.close()
        wait_delay(delay, deadline, cancel_event)
