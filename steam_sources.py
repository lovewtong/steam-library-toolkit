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


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class AccountMismatchError(ValueError):
    pass


def app_type(value):
    value = str(value or "unknown").lower()
    return {"software": "application"}.get(value, value)


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

    def audit(self):
        return {"status": self.status, "count": len(self.records), "fetched_at": self.fetched_at,
                "error": self.error, "scope": self.scope}


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
        return SourceResult("license_file", records, steam_id=account, fetched_at=timestamp, scope="snapshot")
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
    return SourceResult("license_file", validate_records(records), scope="unbound_snapshot")


def reconcile(results, expected_account=None):
    """Fresh client membership wins. Old snapshots never resurrect missing apps."""
    usable = [source for source in results if source.status == "ok"]
    if not usable:
        raise RuntimeError("没有可用数据源；请配置 API 或运行 --login / --local-session，或提供 --apps-file")
    accounts = {source.steam_id for source in usable if source.steam_id}
    if expected_account:
        accounts.add(expected_account)
    if len(accounts) > 1:
        raise AccountMismatchError("数据源属于不同 Steam 账号，已拒绝合并")
    by_source = {source.source: {row["appid"]: row for row in source.records} for source in usable}
    client = next((s for s in usable if s.source == "client_library"), None)
    if client:
        ids = set(by_source["client_library"])
        membership = "client_snapshot"
    else:
        ids = set().union(*(set(rows) for name, rows in by_source.items()
                           if name in ("web_api", "license_file", "licenses")))
        membership = "degraded"
    output = []
    order = ("web_api", "client_library", "licenses", "license_file")
    for appid in sorted(ids):
        found = {name: rows[appid] for name, rows in by_source.items() if appid in rows}
        row = {"appid": appid, "sources": [name for name in order if name in found], "provenance": {}}
        for field_name, preference in (
            ("name", ("web_api", "client_library", "licenses", "license_file")),
            ("app_type", ("client_library", "licenses", "license_file", "web_api")),
        ):
            row[field_name] = "unknown" if field_name == "app_type" else f"Unknown App {appid}"
            for name in preference:
                value = found.get(name, {}).get(field_name)
                if value and value != "unknown":
                    row[field_name] = app_type(value) if field_name == "app_type" else value
                    row["provenance"][field_name] = name
                    break
        for field_name in ("playtime_forever", "playtime_2weeks", "rtime_last_played"):
            row[field_name] = None
            for name in ("web_api", "client_library", "licenses"):
                value = found.get(name, {}).get(field_name)
                if value is not None:
                    row[field_name] = value
                    row["provenance"][field_name] = name
                    break
        row["membership_source"] = "client_library" if client else row["sources"][0]
        row["membership_status"] = "observed" if client else "unverified_completeness"
        shared = found.get("licenses", {}).get("shared_only")
        row["ownership"] = "shared" if shared is True else "account_license" if shared is False else "unknown"
        output.append(row)
    api_ids = set(by_source.get("web_api", {}))
    client_ids = set(by_source.get("client_library", {}))
    audit = {
        "schema_version": 1, "generated_at": utc_now(), "steam_id": next(iter(accounts), None),
        "membership": membership,
        "status": "degraded" if not client or any(s.status == "failed" for s in results) else "ok",
        "sources": {s.source: s.audit() for s in results},
        "summary": {"records": len(output), "types": dict(Counter(r["app_type"] for r in output)),
                    "playtime_known": sum(r["playtime_forever"] is not None for r in output)},
        "difference": {"client_not_api": sorted(client_ids - api_ids),
                       "api_not_client": sorted(api_ids - client_ids),
                       "snapshot_not_client": sorted(set(by_source.get("license_file", {})) - client_ids) if client else [],
                       "license_not_client": sorted(set(by_source.get("licenses", {})) - client_ids) if client else []},
        "warnings": [],
    }
    if any(s.scope == "unbound_snapshot" for s in usable):
        audit["warnings"].append("文本清单没有账号与时间信息，无法核验账号或新鲜度")
    if not client:
        audit["warnings"].append("未取得当前电脑客户端清单，不能确认与客户端库一致")
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
