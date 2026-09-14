"""Immutable generations with a single atomic commit pointer; flat files are compatibility exports."""
from __future__ import annotations

import hashlib
import csv
import json
import os
from pathlib import Path
import subprocess
import uuid
import platform

from steam_sources import AccountMismatchError, atomic_json, select_for_classification, utc_now


def new_run_metadata():
    root = Path(__file__).resolve().parent
    from steam_diagnostics import environment_report
    try:
        command = ["git", "-c", f"safe.directory={root.as_posix()}"]
        commit_result = subprocess.run(command + ["rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=5)
        status_result = subprocess.run(command + ["status", "--porcelain"], cwd=root, capture_output=True, text=True, timeout=5)
        commit = commit_result.stdout.strip() if commit_result.returncode == 0 else None
        dirty = bool(status_result.stdout) if status_result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        commit, dirty = None, None
    return {"run_id": uuid.uuid4().hex, "started_at": utc_now(),
            "producer": {"git_commit": commit, "dirty": dirty},
            "environment": environment_report()}


def save_failed_run(output, audit, code):
    """Persist only allowlisted diagnostics. Never serialize an exception or credentials."""
    import re
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", code):
        code = "COLLECTION_FAILED"
    metadata = new_run_metadata()
    failed = {"schema_version": 1, **metadata, "status": "failed", "error_code": code,
              "finished_at": utc_now(), "sources": {}}
    for name, source in audit.get("sources", {}).items():
        if name not in {"client_library", "licenses", "web_api", "license_file", "client_last_played_times"}:
            continue
        state = source.get("state")
        error = source.get("error_code")
        failed["sources"][name] = {
            "state": state if state in {"complete", "partial", "unavailable", "invalid", "account_mismatch"} else "unavailable",
            "count": source.get("count") if type(source.get("count")) is int else 0,
            "error_code": error if isinstance(error, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", error) else None}
    output = Path(output)
    path = output.parent / ("." + output.stem + ".failed-runs") / metadata["run_id"] / "diagnostic.json"
    atomic_json(path, failed)
    return path


def manifest_path(output):
    return Path(output).with_suffix(".current.json")


def resolve_artifact(output, artifact="steam_library.json"):
    output = Path(output)
    pointer = output if output.name.endswith(".current.json") else manifest_path(output)
    if not pointer.exists():
        return output
    data = json.loads(pointer.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("status") != "complete"
            or not isinstance(data.get("path"), str) or not isinstance(data.get("run_id"), str)
            or not isinstance(data.get("files"), dict) or not data["files"]):
        raise ValueError("GENERATION_INVALID：运行指针无效")
    directory = (pointer.parent / data["path"]).resolve()
    if not directory.is_relative_to(pointer.parent.resolve()):
        raise ValueError("GENERATION_INVALID：运行目录越界")
    target = directory / artifact
    if directory.name != data.get("run_id"):
        raise ValueError("GENERATION_INVALID：目录与运行编号不一致")
    for name, expected in data["files"].items():
        file = (directory / name).resolve()
        if file.parent != directory or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError("GENERATION_INVALID：运行产物校验失败")
    digest = data["files"].get(artifact)
    if not digest or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError("GENERATION_INVALID：产物缺失或校验失败")
    return target


def load_library(output):
    path = resolve_artifact(output)
    rows = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list):
        raise ValueError("LIBRARY_INVALID：游戏库必须为数组")
    if any(not isinstance(r, dict) or type(r.get("appid")) is not int or not 0 < r["appid"] <= 0xffffffff for r in rows):
        raise ValueError("LIBRARY_INVALID：游戏库包含无效记录")
    runs = {r.get("run_id") for r in rows if isinstance(r, dict) and r.get("run_id")}
    if len(runs) > 1:
        raise ValueError("GENERATION_MISMATCH：条目来自不同运行")
    if path != Path(output):
        audit = json.loads((path.parent / "steam_library.audit.json").read_text(encoding="utf-8"))
        if runs and runs != {audit.get("run_id")}:
            raise ValueError("GENERATION_MISMATCH：库与审计版本不同")
    return rows


def check_previous(output, rows, audit, max_removal_ratio=.20):
    """A threshold is a guardrail, not proof that any particular removal is wrong."""
    output = Path(output)
    if not output.exists() and not manifest_path(output).exists():
        return
    previous_path = resolve_artifact(output)
    previous_audit = previous_path.with_name("steam_library.audit.json") if previous_path != output else output.with_suffix(".audit.json")
    if not previous_audit.exists():
        audit["warnings"].append("旧库缺少账号审计，无法作为缩减检查基线")
        return
    old_audit = json.loads(previous_audit.read_text(encoding="utf-8"))
    if old_audit.get("steam_id") != audit.get("steam_id"):
        raise AccountMismatchError("ACCOUNT_MISMATCH：现有输出属于其他账号，请使用独立输出路径")
    if old_audit.get("membership") != "client_snapshot" or audit.get("membership") != "client_snapshot":
        return
    previous = {r["appid"] for r in load_library(output)}
    current = {r["appid"] for r in rows}
    removed = sorted(previous - current)
    audit["previous_run"] = {"run_id": old_audit.get("run_id"), "previous_count": len(previous),
                             "current_count": len(current), "added": sorted(current - previous), "removed": removed,
                             "removal_ratio": len(removed) / len(previous) if previous else 0,
                             "max_unexplained_removal_ratio": max_removal_ratio,
                             "removal_evidence": "absence_in_repeated_rpc_snapshot"}
    if previous and len(removed) / len(previous) > max_removal_ratio:
        audit["status"] = "suspicious_change"
        audit["warnings"].append("SUSPICIOUS_REMOVAL：库成员缩减超过保护阈值；未切换当前运行")


def publish_run(output, rows, audit, *, audit_export=None, snapshot_export=None, allow_candidates=False):
    """Write and validate all files first. current.json is the sole authoritative commit point."""
    from classify_games import classify_library, write_csv, write_md_table
    from classify_steam_games import classify_one
    output = Path(output)
    candidate = audit["membership"] != "client_snapshot"
    if candidate and not allow_candidates:
        output = output.with_suffix(".candidates.json")
    run_id = audit["run_id"]
    directory = output.parent / ("." + output.stem + ".runs") / run_id
    directory.mkdir(parents=True, exist_ok=False)
    snapshot = audit.pop("snapshot", None)
    from steam_schema import validate_artifacts
    validate_artifacts(rows, audit, snapshot)
    if snapshot and (snapshot.get("run_id") != run_id or snapshot.get("steam_id") != audit["steam_id"]):
        raise AccountMismatchError("GENERATION_MISMATCH：快照账号或运行编号不同")
    audit["publication"] = {"kind": "candidates" if candidate else "current_library", "generation": run_id}
    if any(r.get("run_id") != run_id for r in rows):
        raise ValueError("GENERATION_MISMATCH：条目运行编号不一致")
    selected = select_for_classification(rows)
    from classification_overrides import load_overrides
    overrides = load_overrides()
    applied = {str(g['appid']): overrides[str(g['appid'])] for g in selected if str(g['appid']) in overrides}
    audit['classification'] = {'override_count': len(applied), 'rules_artifact': 'classification_overrides.json'}
    table = classify_library(selected, overrides)
    five = [{**classify_one(g, overrides), "run_id": run_id} for g in selected]
    expected = {g["appid"] for g in selected}
    if {g["appid"] for g in table} != expected or {int(g["appid"]) for g in five} != expected:
        raise RuntimeError("CLASSIFICATION_INVARIANT_FAILED")
    atomic_json(directory / "steam_library.json", rows)
    atomic_json(directory / "steam_library.audit.json", audit)
    atomic_json(directory / "steam_library_classified.json", five)
    atomic_json(directory / "classification_overrides.json", {'schema_version': 1, 'apps': applied})
    atomic_json(directory / "summary.json", {"run_id": run_id, "producer": audit["producer"], **audit["summary"]})
    absent = set(audit.get("difference", {}).get("client_not_api", []))
    comparison = audit.get('web_api_comparison', {'state': 'complete' if
        audit.get('sources', {}).get('web_api', {}).get('state') == 'complete'
        and audit.get('membership') == 'client_snapshot' else 'unavailable'})
    comparable = comparison['state'] == 'complete'
    atomic_json(directory / "missing_from_web_api.json", {"run_id": run_id, 'comparison': comparison, "apps": [
        {"appid": r["appid"], "name": r["name"], "app_type": r["app_type"],
         "present_in_client": True, "present_in_web_api": False if comparable else None,
         "license_evidence": r.get("license_evidence", {}),
         "classification": {"cause": "web_api_absent" if comparable else 'comparison_unavailable', "cause_confirmed": False}}
        for r in rows if (r["appid"] in absent if comparable else audit.get('membership') == 'client_snapshot')]})
    atomic_json(directory / "playtime_probe.json", {"run_id": run_id, **audit.get("overview_probe", {})})
    if snapshot:
        atomic_json(directory / "client.snapshot.json", snapshot)
    write_csv(table, directory / "classified.csv")
    write_md_table(table, directory / "classified.md", run_id=run_id)
    with (directory / "classified.csv").open(encoding="utf-8-sig", newline="") as stream:
        written = list(csv.DictReader(stream))
    if ({int(r["appid"]) for r in written} != expected or len(written) != len(expected)
            or any(r["run_id"] != run_id for r in written)):
        raise RuntimeError("CLASSIFICATION_INVARIANT_FAILED：生成的 CSV 不匹配")
    files = {}
    for file in directory.iterdir():
        if file.is_file():
            with file.open("r+b") as stream:
                files[file.name] = hashlib.sha256(stream.read()).hexdigest()
                os.fsync(stream.fileno())
    manifest = {"schema_version": 1, "run_id": run_id, "producer": audit["producer"], "committed_at": utc_now(),
                "steam_id": audit["steam_id"], "status": "complete", "library_status": audit["status"],
                "path": directory.relative_to(output.parent).as_posix(), "files": files}
    # Every artifact is durable before publishing the pointer. Failure here leaves the old pointer intact.
    atomic_json(manifest_path(output), manifest)
    warnings = []
    # Legacy exports are conveniences. Readers in this project use the verified generation.
    exports = [(output, rows), (audit_export if audit_export and not candidate else output.with_suffix(".audit.json"), audit)]
    if snapshot_export and snapshot:
        exports.append((snapshot_export, snapshot))
    for path, data in exports:
        try:
            atomic_json(path, data)
        except OSError:
            warnings.append("COMPAT_EXPORT_FAILED：兼容副本写入失败，完整结果已保存在运行目录")
    return output, manifest_path(output), warnings
