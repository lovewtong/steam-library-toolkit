"""Local-only JSON Schema validation before publishing a generation."""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent / "schemas"


def validate_artifacts(rows, audit, snapshot=None):
    for filename, value in (("steam-library-v2.schema.json", rows), ("steam-audit-v2.schema.json", audit),
                            ("client-snapshot-v2.schema.json", snapshot)):
        if value is None:
            continue
        schema = json.loads((ROOT / filename).read_text(encoding="utf-8"))
        if next(Draft202012Validator(schema).iter_errors(value), None) is not None:
            # ValidationError embeds instance values: do not print or serialize it.
            raise ValueError("SCHEMA_INVALID：产物不符合 " + filename)
    if len({r["appid"] for r in rows}) != len(rows):
        raise ValueError("SCHEMA_INVALID：重复 AppID")
    if audit["summary"]["records"] != len(rows):
        raise ValueError("SCHEMA_INVALID：摘要条数不一致")
    if audit.get('membership') == 'accessible_snapshot':
        from steam_membership import trusted_current_membership, verified_membership_row, family_evidence_valid
        if (not trusted_current_membership(audit) or any(not verified_membership_row(r, audit) for r in rows)
                or any('family_evidence' in r and not family_evidence_valid(r) for r in rows)
                or sum(r['membership']['source'] == 'client_library' for r in rows) != audit['sources']['client_library']['count']
                or sum('family_evidence' in r for r in rows) != audit['sources']['family_library']['count']):
            raise ValueError('SCHEMA_INVALID：家庭成员与来源证据不一致')
    if snapshot is not None:
        from steam_sources import records_hash
        if (snapshot["record_count"] != len(snapshot["apps"])
                or snapshot["apps_sha256"] != records_hash(snapshot["apps"])
                or {r["appid"] for r in snapshot["apps"]} != {r["appid"] for r in rows}):
            raise ValueError("SCHEMA_INVALID：快照成员或校验和不一致")
    for row in rows:
        if 'first_seen_at' in row or 'first_seen_evidence' in row:
            from steam_observation import first_seen_fields
            evidence = row.get('first_seen_evidence', {})
            fields = first_seen_fields(row)
            if ((row.get('first_seen_at') is not None and fields['first_seen_at'] is None)
                    or (evidence.get('state') != 'unknown' and (fields['first_seen_at'] is None
                        or evidence.get('steam_id') != audit['steam_id'] or not evidence.get('run_id')))
                    or (evidence.get('state') == 'unknown' and row.get('first_seen_at') is not None)):
                raise ValueError('SCHEMA_INVALID：首次观察时间与证据不一致')
        if row.get("playtime") is not None:
            evidence = row["playtime_evidence"]["playtime_forever"]
            if (row["playtime"].get("minutes") != evidence["value"]
                    or row["playtime"].get("state") != evidence["state"]
                    or row.get("playtime_minutes") != evidence["value"]):
                raise ValueError("SCHEMA_INVALID：时长证据与输出值不一致")
