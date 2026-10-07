"""Public store requests and cache observations shared by collection and enrichment."""
import json
import time
from pathlib import Path
import requests

from steam_library_toolkit.sources.http import get_response, SourceCoolingDown, check_cancel
from steam_library_toolkit.sources.metadata import STORE_GATE, parse_fields
from steam_library_toolkit.sources.reconcile import app_type, atomic_json


def get_store_result(appid: int, *, cancel_event=None):
    """
    获取商店详情（可选）：类型、分类（含多人/手柄等）。
    使用公开商店 API，有频率限制，需控制请求间隔。
    """
    url = "https://store.steampowered.com/api/appdetails"
    params = {"appids": appid, "l": "schinese"}
    try:
        resp = get_response(url, params=params, timeout=10, gate=STORE_GATE, cancel_event=cancel_event)
        if resp.status_code != 200:
            state = "rate_limited" if resp.status_code == 429 else "access_denied" if resp.status_code in (401, 403) else "not_found" if resp.status_code == 404 else "transient_error"
            return {"status": state, "details": None}
        data = resp.json()
    except SourceCoolingDown:
        return {"status": "deferred", "details": None}
    except requests.RequestException:
        return {"status": "transient_error", "details": None}
    except ValueError:
        return {"status": "parse_error", "details": None}
    entry = data.get(str(appid)) if isinstance(data, dict) else None
    if not isinstance(entry, dict):
        return {"status": "parse_error", "details": None}
    if not entry.get("success"):
        return {"status": "not_found", "details": None}
    g = entry.get("data")
    if not isinstance(g, dict):
        return {"status": "parse_error", "details": None}
    return {"status": "success", "details": {
        "app_type": app_type(g.get("type")), **parse_fields(g),
    }}


def get_store_details(appid):
    return get_store_result(appid)["details"]


def cached_store_details(appid, cache_dir, refresh=False, audit_meta=None, *, cancel_event=None, observation=None):
    check_cancel(cancel_event)
    path = Path(cache_dir) / f"{appid}.json"
    ttl = {"success": 7 * 86400, "not_found": 21600, "access_denied": 600,
           "rate_limited": 60, "parse_error": 60, "transient_error": 30}
    cache = None
    if not refresh and path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            status = cached.get("status", "success")
            if (cached.get("schema_version") == 6 and status in ttl and 0 <= time.time() - cached["fetched_at"] < ttl[status]
                    and (status != "success" or valid_store_details(cached["details"]))):
                cache = cached
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
    hit = cache is not None
    if cache is None:
        result = get_store_result(appid, cancel_event=cancel_event)
        check_cancel(cancel_event)
        cache = {"schema_version": 6, "fetched_at": time.time(), **result}
        if result['status'] != 'deferred':
            try:
                atomic_json(path, cache)
            except OSError:
                if audit_meta is not None:
                    audit_meta["cache_write_errors"] = audit_meta.get("cache_write_errors", 0) + 1
    if observation is not None:
        observation.update(source='store_cache' if hit else 'store_api' if cache['status'] != 'deferred' else 'none',
                           fetched_at=cache['fetched_at'] if cache['status'] != 'deferred' else None, read_at=time.time())
    if audit_meta is not None:
        key = cache["status"]
        audit_meta[key] = audit_meta.get(key, 0) + 1
        audit_meta["cache_hits"] = audit_meta.get("cache_hits", 0) + int(hit)
        audit_meta["cache_misses"] = audit_meta.get("cache_misses", 0) + int(not hit)
    return cache.get("details") if cache["status"] == "success" else None


def valid_store_details(details):
    from steam_library_toolkit.sources.metadata import MANUFACTURER_FIELDS, manufacturer_names
    return (isinstance(details, dict)
            and all(key in details and (details[key] is None or manufacturer_names(details[key]) is not None)
                    for key in MANUFACTURER_FIELDS)
            and all(isinstance(details.get(key), list)
                    and all(isinstance(x, str) for x in details[key]) for key in ("genres", "categories"))
            and all(details.get(key) is None or type(details.get(key)) is bool for key in ("is_multiplayer", "is_controller"))
            and isinstance(details.get('field_states'), dict)
            and all(details['field_states'].get(key) in ('present', 'empty', 'missing', 'invalid')
                    for key in ('genres', 'categories', *MANUFACTURER_FIELDS))
            and all(details['field_states'].get(key) in ('known', 'missing')
                    for key in ('is_multiplayer', 'is_controller')))
