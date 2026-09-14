"""Source validation and deterministic library reconciliation (no network I/O)."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import hashlib

APP_TYPES = {"game", "application", "tool", "demo", "dlc", "guide", "driver", "config", "hardware",
             "video", "plugin", "music", "series", "comic", "beta", "shortcut", "depot", "unknown"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class AccountMismatchError(ValueError):
    pass


def app_type(value):
    value = str(value or "unknown").strip().lower()
    value = {"software": "application", "musicalbum": "music"}.get(value, value)
    return value if value in APP_TYPES else "unknown"


def records_hash(records):
    return hashlib.sha256(json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_records(records):
    if not isinstance(records, list):
        raise ValueError("应用清单必须为数组")
    result = {}
    for record in records:
        if (not isinstance(record, dict) or type(record.get("appid")) is not int
                or not 0 < record["appid"] <= 0xFFFFFFFF):
            raise ValueError("应用清单包含无效 AppID")
        if not isinstance(record.get("name", ""), str):
            raise ValueError("应用名称必须为字符串")
        for key in ("playtime_forever", "playtime_2weeks", "rtime_last_played"):
            value = record.get(key)
            if value is not None and (type(value) is not int or not 0 <= value <= 0xFFFFFFFF):
                raise ValueError("应用清单包含无效时长或时间戳")
        result.setdefault(record["appid"], dict(record))
    return list(result.values())


@dataclass
class SourceResult:
    source: str
    records: list = field(default_factory=list)
    status: str = "ok"
    steam_id: str | None = None
    fetched_at: str = field(default_factory=utc_now)
    error: str | None = None
    scope: str = "unknown"
    state: str | None = None
    error_code: str | None = None
    completeness: dict = field(default_factory=dict)
    freshness: dict = field(default_factory=dict)
    attempts: int = 0

    def __post_init__(self):
        self.state = self.state or ("complete" if self.status == "ok" else "unavailable")

    @property
    def authoritative(self):
        return (self.source == "client_library" and self.status == "ok" and self.state == "complete"
                and self.completeness.get("verified") is True)

    def audit(self):
        return {"status": self.status, "count": len(self.records), "fetched_at": self.fetched_at,
                "error": self.error, "scope": self.scope, "state": self.state, "error_code": self.error_code,
                "completeness": self.completeness, "freshness": self.freshness, "attempts": self.attempts}


def read_snapshot(path, expected_account=None):
    raw = Path(path).read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    text = raw.decode(encoding)
    if text.lstrip().startswith(("{", "[")):
        data = json.loads(text)
        if not isinstance(data, dict) or data.get("schema_version") != 2:
            raise ValueError("JSON 快照需要 schema_version=2、steam_id、generated_at 和 apps")
        account = data.get("steam_id")
        if not isinstance(account, str) or not re.fullmatch(r"[0-9]{17}", account):
            raise ValueError("快照 Steam ID 无效")
        if expected_account and account != expected_account:
            raise AccountMismatchError("快照账号与本次采集账号不匹配")
        timestamp = data.get("generated_at")
        if not isinstance(timestamp, str):
            raise ValueError("快照缺少 generated_at")
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("快照时间必须包含时区")
        records = validate_records(data.get("apps"))
        if "record_count" in data and data["record_count"] != len(records):
            raise ValueError("SNAPSHOT_INVALID：快照条数不匹配")
        if "apps_sha256" in data and data["apps_sha256"] != records_hash(records):
            raise ValueError("SNAPSHOT_INVALID：快照校验和不匹配")
        age = (datetime.now(timezone.utc) - parsed).total_seconds()
        freshness = {"age_seconds": max(0, int(age)), "state": "unknown" if age < -300 else "fresh" if age < 86400 else "stale",
                     "fresh_threshold_seconds": 86400}
        return SourceResult("license_file", records, steam_id=account, fetched_at=timestamp, scope="snapshot",
                            completeness={"declared_complete": data.get("complete"), "verified": False}, freshness=freshness)
    records = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"\s*([0-9]+)\s+(\S.*?)\s*", line)
        if not match:
            raise ValueError(f"许可清单第 {number} 行无效，应为 AppID 名称")
        records.append({"appid": int(match[1]), "name": match[2]})
    if not records:
        raise ValueError("许可清单为空")
    return SourceResult("license_file", validate_records(records), scope="unbound_snapshot", freshness={"state": "unknown"})


def resolve_playtime(found, providers, field_name):
    evidence = {}
    order = ("web_api", "client_last_played_times", "client_library", "licenses", "license_file")
    for name in order:
        value = found.get(name, {}).get(field_name)
        if value is not None:
            evidence[name] = {"value": value, "observed_at": providers[name].fetched_at,
                              "historical": name == "license_file"}
    selected = next(iter(evidence), None)
    value = evidence[selected]["value"] if selected else None
    state = "unknown" if value is None else "historical" if selected == "license_file" else "known_zero" if value == 0 else "known_nonzero"
    live = [e["value"] for e in evidence.values() if not e["historical"]]
    return {"value": value, "state": state, "source": selected,
            "observed_at": evidence[selected]["observed_at"] if selected else None,
            "evidence": evidence, "conflict": len(set(live)) > 1}


def reconcile(results, expected_account=None, *, allow_candidate_membership=False):
    """Only validated client responses determine current membership; other sets remain candidates."""
    accounts = {s.steam_id for s in results if s.steam_id}
    if expected_account:
        accounts.add(expected_account)
    if len(accounts) > 1 or any(s.state == "account_mismatch" for s in results):
        raise AccountMismatchError("ACCOUNT_MISMATCH：数据源属于不同 Steam 账号，已拒绝合并")
    usable = [s for s in results if s.status == "ok" and s.state == "complete"]
    if not usable:
        codes = ", ".join(s.error_code for s in results if s.error_code)
        detail = next((s.error for s in results if s.source == "client_library" and s.error), None)
        raise RuntimeError("NO_USABLE_SOURCE：没有可用数据源，请配置 API、客户端授权或快照" + (f" [{codes}]" if codes else "")
                           + (f"\n客户端原因：{detail}" if detail else ""))
    providers = {s.source: s for s in usable}
    by_source = {s.source: {r["appid"]: r for r in s.records} for s in usable}
    client = next((s for s in usable if s.authoritative), None)
    fallback = "license_file" if "license_file" in providers else "web_api" if "web_api" in providers else None
    if not client and not fallback and not allow_candidate_membership:
        raise RuntimeError("NO_MEMBERSHIP_SOURCE：仅有许可/时长证据；使用 --allow-candidate-membership 才能生成实验性候选")
    ids = (set(by_source["client_library"]) if client else
           set().union(*(set(rows) for name, rows in by_source.items() if name in ("web_api", "license_file", "licenses")))
           if allow_candidate_membership else set(by_source[fallback]))
    output = []
    for appid in sorted(ids):
        found = {name: rows[appid] for name, rows in by_source.items() if appid in rows}
        row = {"appid": appid, "sources": list(found), "provenance": {},
               "evidence": {name: {"present": appid in rows} for name, rows in by_source.items()}}
        for field_name, preference in (("name", ("web_api", "client_library", "licenses", "license_file")),
                                      ("app_type", ("client_library", "licenses", "license_file", "web_api"))):
            row[field_name] = "unknown" if field_name == "app_type" else f"Unknown App {appid}"
            for name in preference:
                raw = found.get(name, {}).get(field_name)
                value = app_type(raw) if field_name == "app_type" else raw
                if value and value != "unknown":
                    row[field_name] = value
                    row["provenance"][field_name] = name
                    break
            if field_name == "app_type":
                row["raw_app_types"] = {name: r["app_type"] for name, r in found.items() if "app_type" in r}
        row["playtime_evidence"] = {}
        for field_name in ("playtime_forever", "playtime_2weeks", "rtime_last_played"):
            resolved = resolve_playtime(found, providers, field_name)
            row[field_name] = resolved["value"]
            row["playtime_evidence"][field_name] = resolved
            if resolved["source"]:
                row["provenance"][field_name] = resolved["source"]
        row["membership_source"] = "client_library" if client else "candidate_union" if allow_candidate_membership else fallback
        row["membership_status"] = "observed" if client else "unverified_completeness"
        row["membership"] = {"state": "present" if client else "candidate", "source": row["membership_source"],
                             "realtime_verified": bool(client), "observed_at": client.fetched_at if client else None}
        shared = found.get("licenses", {}).get("shared_only")
        row["ownership"] = "shared" if shared is True else "account_license" if shared is False else "unknown"
        row["license_evidence"] = found.get("licenses", {}).get("license_evidence", {})
        output.append(row)
    api_ids = set(by_source.get("web_api", {}))
    client_ids = set(by_source.get("client_library", {})) if client else set()
    comparable = bool(client) and 'web_api' in providers
    comparison = {'state': 'complete' if comparable else 'unavailable',
                  'reason': None if comparable else 'client_unavailable' if not client else 'web_api_unavailable'}
    differences = {"client_not_api": sorted(client_ids - api_ids) if comparable else [],
                   "api_not_client": sorted(api_ids - client_ids) if comparable else [],
                   "snapshot_not_client": sorted(set(by_source.get("license_file", {})) - client_ids) if client else [],
                   "license_not_client": sorted(set(by_source.get("licenses", {})) - client_ids) if client else []}
    types = {r["appid"]: r["app_type"] for r in output}
    for name in ("licenses", "license_file", "web_api"):
        for appid, r in by_source.get(name, {}).items():
            types.setdefault(appid, app_type(r.get("app_type")))
    audit = {
        "schema_version": 2, "generated_at": utc_now(), "steam_id": next(iter(accounts), None),
        "membership": "client_snapshot" if client else "candidate_union",
        "membership_semantics": "client_library_membership" if client else "unverified_candidate_union" if allow_candidate_membership else "historical_snapshot" if fallback == "license_file" else "web_api_fallback",
        "fallback_source": None if client else "candidate_union" if allow_candidate_membership else fallback,
        "status": "ok" if client and all(s.state == "complete" for s in results if s.source != "client_last_played_times") else "degraded",
        "sources": {s.source: s.audit() for s in results},
        "summary": {"records": len(output), "types": dict(Counter(r["app_type"] for r in output)),
                    "playtime_known": sum(r["playtime_evidence"]["playtime_forever"]["state"] in ("known_zero", "known_nonzero") for r in output)},
        "difference": differences,
        "web_api_comparison": comparison,
        "difference_summary": {name: {"count": len(values), "by_type": dict(Counter(types.get(i, "unknown") for i in values))}
                               for name, values in differences.items()},
        "warnings": [],
    }
    for name in ('client_not_api', 'api_not_client'):
        audit['difference_summary'][name]['state'] = comparison['state']
        if not comparable:
            audit['difference_summary'][name]['count'] = None
    if client and ids != {r["appid"] for r in output}:
        raise RuntimeError("MEMBERSHIP_INVARIANT_FAILED")
    if any(s.scope == "unbound_snapshot" for s in usable):
        audit["warnings"].append("文本清单没有账号与时间信息，无法核验账号或新鲜度")
    if not client:
        audit["warnings"].append("未取得经过核验的实时客户端清单；本次仅生成候选集合")
    return output, audit


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def select_for_classification(records, include_demo=False, include_non_game=False, include_unknown=False):
    """Do not silently treat untyped imports as games. The source JSON retains them."""
    return [r for r in records if app_type(r.get("app_type")) == "game"
            or (include_demo and app_type(r.get("app_type")) == "demo")
            or (include_unknown and app_type(r.get("app_type")) == "unknown")
            or (include_non_game and app_type(r.get("app_type")) != "unknown")]
