"""Bounded retry for transient HTTP failures; no URL or exception logging."""
import random
import time
from email.utils import parsedate_to_datetime
import requests


def get_response(url, *, params, timeout, stats=None):
    deadline = time.monotonic() + 35
    for attempt in range(1, 4):
        if stats is not None:
            stats["attempts"] = attempt
        response, error, retry_after = None, None, 0
        try:
            response = requests.get(url, params=params, timeout=min(timeout, max(.01, deadline - time.monotonic())), allow_redirects=False)
            if response.status_code not in (408, 429, 500, 502, 503, 504):
                return response
            header = response.headers.get("Retry-After")
            if isinstance(header, str):
                try:
                    retry_after = float(header) if header.isdigit() else parsedate_to_datetime(header).timestamp() - time.time()
                except (ValueError, TypeError, OverflowError):
                    pass
        except (requests.Timeout, requests.ConnectionError) as exc:
            error = exc
        delay = max(retry_after, .25 * 2 ** (attempt - 1) * random.uniform(.75, 1.25))
        if attempt == 3 or delay >= deadline - time.monotonic():
            if error:
                raise error
            return response
        if response is not None:
            response.close()
        time.sleep(delay)
