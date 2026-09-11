"""
Steam 游戏库本地采集脚本
从 Steam API 获取：游戏名、appid、总时长、最近游玩时间；
可选从商店 API 获取：类型/标签、是否多人、是否手柄支持。
默认请求已游玩免费游戏/免费许可及未审核应用，但 Web API 不保证完整。
在线客户端清单决定本次成员，账号许可用于类型与差异核对；失败时明确降级。
扫码授权保存在系统凭据存储；--local-session 显式复用 Windows 本机登录态。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter
import socket

from steam_sources import (AccountMismatchError, SourceResult, app_type, atomic_json,
                           read_snapshot, reconcile, utc_now, validate_records)
from steam_auth import collect_client

try:
    import requests
except ImportError:
    print("请先安装: pip install requests")
    raise SystemExit(1)

# --- 路径与默认输出 ---
CONFIG_PATH = Path(__file__).resolve().parent / "config_local.json"
OUTPUT_FILE = Path(__file__).resolve().parent / "steam_library.json"
STORE_REQUEST_DELAY = 1.5  # 商店 API 请求间隔（秒）


def load_config():
    """API credentials are optional when a client session or snapshot is available."""
    if not CONFIG_PATH.exists():
        return {"api_key": "", "steam_id": "", "steam_path": ""}
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError("config_local.json 必须为对象")
    return {
        "api_key": str(cfg.get("steam_api_key") or "").strip(),
        "steam_id": str(cfg.get("steam_id") or "").strip(),
        "steam_path": str(cfg.get("steam_install_path") or "").strip(),
    }


def get_owned_games(api_key: str, steam_id: str, include_non_inventory: bool = True, *, access_token=None):
    """获取游戏列表：appid、name、playtime_forever、rtime_last_played 等。"""
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": api_key,
        "steamid": steam_id,
        "include_appinfo": "true",
        "include_played_free_games": "true" if include_non_inventory else "false",
        "include_free_sub": "true" if include_non_inventory else "false",
        "skip_unvetted_apps": "false" if include_non_inventory else "true",
        "format": "json",
    }
    if access_token:
        params.pop("key")
        params["access_token"] = access_token
    elif not api_key:
        raise ValueError("未配置 API Key，且没有客户端访问令牌")
    resp = requests.get(url, params=params, timeout=15, allow_redirects=False)
    if resp.status_code != 200:
        raise RuntimeError(f"GetOwnedGames 请求失败: HTTP {resp.status_code}")
    data = resp.json()
    response = data.get("response") if isinstance(data, dict) else None
    if not isinstance(response, dict):
        raise ValueError("GetOwnedGames 返回格式无效：缺少 response 对象。")
    if "game_count" not in response and "games" not in response:
        raise ValueError("Steam 未提供游戏详情，可能是可见性限制；不能视为空库")
    games = validate_records(response.get("games", []))
    if "game_count" in response and response["game_count"] != len(games):
        raise ValueError("Steam 游戏计数与返回记录不一致")
    return games


def load_apps_file(path: Path) -> list[dict]:
    return read_snapshot(path).records


def merge_games(api_games: list[dict], licensed_apps: list[dict]) -> list[dict]:
    return reconcile([SourceResult("web_api", api_games), SourceResult("license_file", licensed_apps)])[0]


def get_store_details(appid: int):
    """
    获取商店详情（可选）：类型、分类（含多人/手柄等）。
    使用公开商店 API，有频率限制，需控制请求间隔。
    """
    url = "https://store.steampowered.com/api/appdetails"
    params = {"appids": appid, "l": "schinese"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    entry = data.get(str(appid)) if isinstance(data, dict) else None
    if not isinstance(entry, dict) or not entry.get("success"):
        return None
    g = entry.get("data")
    if not isinstance(g, dict):
        return None
    def descriptions(key):
        values = g.get(key, [])
        if not isinstance(values, list):
            return []
        return [x["description"] for x in values if isinstance(x, dict)
                and isinstance(x.get("description"), str) and x["description"]]
    genres = descriptions("genres")
    categories = descriptions("categories")

    # 从 categories 推断是否多人、是否手柄（常见英文/简中描述）
    multi_keywords = ("多人", "Multi-player", "Online Multi", "Co-op", "Online Co-op", "LAN", "Shared/Split")
    ctrl_keywords = ("手柄", "Controller", "Full controller", "Partial controller")
    is_multiplayer = any(k in c for c in categories for k in multi_keywords)
    is_controller = any(k in c for c in categories for k in ctrl_keywords)

    return {
        "app_type": app_type(g.get("type")),
        "genres": genres,
        "categories": categories,
        "is_multiplayer": is_multiplayer,
        "is_controller": is_controller,
    }


def client_library(access_token, machine):
    """Read a specific online desktop, never silently choose another user's device."""
    def call(method, **params):
        response = requests.get(
            f"https://api.steampowered.com/IClientCommService/{method}/v1/",
            params={"access_token": access_token, **params}, timeout=35, allow_redirects=False)
        if response.status_code != 200 or response.headers.get("x-eresult", "1") != "1":
            raise RuntimeError("客户端清单接口返回失败")
        data = response.json()
        body = data.get("response") if isinstance(data, dict) else None
        if not isinstance(body, dict):
            raise ValueError("客户端清单响应无效")
        return body
    sessions = call("GetAllClientLogonInfo").get("sessions", [])
    if not isinstance(sessions, list) or any(not isinstance(s, dict) for s in sessions):
        raise ValueError("客户端会话列表无效")
    matches = [s for s in sessions if isinstance(s.get("machine_name"), str)
               and s["machine_name"].casefold() == machine.casefold()]
    if len(matches) != 1:
        raise RuntimeError("没有唯一匹配的在线 Steam 客户端；请启动 Steam，必要时指定 --machine")
    data = call("GetClientAppList", client_instanceid=matches[0]["client_instanceid"],
                fields="games", include_client_info="true", language="schinese")
    if not isinstance(data.get("client_info"), dict):
        raise ValueError("客户端没有确认清单响应，不能视为空库")
    apps = validate_records(data.get("apps", []))
    records = [{"appid": a["appid"], "name": a.get("app", ""), "app_type": app_type(a.get("app_type"))}
               for a in apps]
    return validate_records(records)


def cached_store_details(appid, cache_dir, refresh=False):
    path = Path(cache_dir) / f"{appid}.json"
    if not refresh and path.exists():
        try:
            cache = json.loads(path.read_text(encoding="utf-8"))
            if (0 <= time.time() - cache["fetched_at"] < 7 * 86400
                    and valid_store_details(cache["details"])):
                return cache["details"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    details = get_store_details(appid)
    time.sleep(STORE_REQUEST_DELAY)
    if details:
        try:
            atomic_json(path, {"fetched_at": time.time(), "details": details})
        except OSError:
            pass  # Optional cache persistence must not break collection.
    return details


def valid_store_details(details):
    return (isinstance(details, dict)
            and all(isinstance(details.get(key), list)
                    and all(isinstance(x, str) for x in details[key]) for key in ("genres", "categories"))
            and all(type(details.get(key)) is bool for key in ("is_multiplayer", "is_controller")))


def collect(fetch_store=True, include_non_inventory=True, apps_file=None, use_api=True,
            *, use_client=False, login=False, local_session=False, account=None, machine=None,
            strict=False, audit=None, cache_dir=None, refresh_metadata=False, snapshot_output=None):
    if not include_non_inventory and (apps_file or use_client):
        raise ValueError("--owned-only 只能用于 API 模式，不能同时导入或启用客户端")
    if not use_api and not use_client and apps_file is None:
        raise ValueError("至少启用一个数据源")
    config = load_config() if use_api or use_client else {"api_key": "", "steam_id": ""}
    configured = config.get("steam_id") or None
    if account and configured and account != configured:
        # --account is an explicit override, allowing multi-account operation.
        configured = account
    account = account or configured
    snapshot = read_snapshot(apps_file, account) if apps_file else None
    if snapshot and not account:
        account = snapshot.steam_id
    results = []
    access_token = None
    native = None
    if use_client:
        try:
            native = collect_client(account, login=login, local_session=local_session,
                                    steam_path=config.get("steam_path"), machine=machine)
            account = native["steam_id"]
            access_token = native["access_token"]
            licenses = validate_records(native.get("licenses", []))
            playtimes = {r["appid"]: r for r in validate_records(native.get("playtimes", []))}
            for record in licenses:
                if record["appid"] in playtimes:
                    record.update({k: v for k, v in playtimes[record["appid"]].items() if k != "appid"})
            results.append(SourceResult("licenses", licenses, status=native.get("license_status", "failed"),
                                        steam_id=account, scope="account_and_shared_entitlements"))
            try:
                records = client_library(access_token, machine or socket.gethostname())
                for record in records:
                    record.update({k: v for k, v in playtimes.get(record["appid"], {}).items() if k != "appid"})
                results.append(SourceResult("client_library", records, steam_id=account, scope="current_desktop"))
            except (requests.RequestException, ValueError, RuntimeError, KeyError):
                results.append(SourceResult("client_library", status="failed", error="在线客户端清单不可用", steam_id=account))
        except AccountMismatchError:
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            results.append(SourceResult("client_library", status="failed", error=str(exc)))
    if snapshot:
        if account and snapshot.steam_id and snapshot.steam_id != account:
            raise AccountMismatchError("快照账号与认证账号不一致")
        results.append(snapshot)
    if use_api:
        try:
            if not account:
                raise ValueError("未配置 Steam ID；请填写 config_local.json 或使用 --account / --login")
            records = get_owned_games(config.get("api_key", ""), account,
                                      include_non_inventory, access_token=access_token)
            results.append(SourceResult("web_api", records, steam_id=account, scope="api_visible"))
        except (requests.RequestException, ValueError, RuntimeError):
            # Exception URLs can contain credentials. Only fixed diagnostics reach disk/stdout.
            results.append(SourceResult("web_api", status="failed", error="Web API 不可用或未提供游戏详情", steam_id=account))
    raw, report = reconcile(results, account)
    if strict and report["status"] != "ok":
        raise RuntimeError("严格模式要求实时客户端与所有启用来源成功；本次未覆盖原输出")
    # License-only fallback keeps candidates, with explicit degraded status. Classification filters types.
    library = []
    for g in raw:
        if fetch_store and len(library) % 25 == 0:
            print(f"读取商店元数据：{len(library)}/{len(raw)}", flush=True)
        timestamp = g.get("rtime_last_played")
        row = {key: value for key, value in g.items() if key not in ("playtime_forever", "playtime_2weeks", "rtime_last_played")}
        row.update({"playtime_minutes": g.get("playtime_forever"),
                    "playtime_2weeks_minutes": g.get("playtime_2weeks"),
                    "playtime_available": g.get("playtime_forever") is not None,
                    "last_played_at": timestamp,
                    "last_played_iso": datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z") if timestamp else None,
                    "genres": [], "categories": [], "is_multiplayer": None, "is_controller": None})
        if fetch_store:
            details = cached_store_details(g["appid"], cache_dir or OUTPUT_FILE.parent / ".steam_cache", refresh_metadata)
            if details:
                row.update({k: details[k] for k in ("genres", "categories", "is_multiplayer", "is_controller")})
                row["provenance"]["store_metadata"] = "store_cache"
                if row["app_type"] == "unknown" and details.get("app_type"):
                    row["app_type"] = details["app_type"]
                    row["provenance"]["app_type"] = "store_cache"
        library.append(row)
    report["summary"]["types"] = dict(Counter(r["app_type"] for r in library))
    if native:
        report["client_playtime_status"] = native.get("playtime_status")
    if snapshot_output:
        client = next((r for r in results if r.source == "client_library" and r.status == "ok"), None)
        if not client:
            raise RuntimeError("只有成功读取实时客户端清单才能导出新的客户端快照")
        atomic_json(snapshot_output, {"schema_version": 2, "steam_id": account, "generated_at": client.fetched_at,
                                      "source": "client_library", "apps": client.records})
    if audit is not None:
        audit.update(report)
    return library


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Steam 多来源采集，输出应用记录与来源审计")
    parser.add_argument("--no-store", action="store_true", help="跳过商店请求，保留未知元数据")
    parser.add_argument("--owned-only", action="store_true", help="仅使用传统 API 过滤")
    parser.add_argument("--source", choices=("auto", "api", "client"), default="auto")
    parser.add_argument("--no-api", action="store_true")
    parser.add_argument("--no-client", action="store_true")
    parser.add_argument("--apps-file", type=Path, help="带账号的 JSON v2 快照或旧 AppID 名称文本")
    auth = parser.add_mutually_exclusive_group()
    auth.add_argument("--login", action="store_true", help="扫码登录，授权保存在系统凭据存储")
    auth.add_argument("--local-session", action="store_true", help="显式复用 Windows Steam 当前账号凭据（不保存）")
    parser.add_argument("--account", help="SteamID64；显式覆盖配置账号")
    parser.add_argument("--machine", help="客户端机器名；默认当前电脑")
    parser.add_argument("--strict", action="store_true", help="来源降级时失败，保留原输出")
    parser.add_argument("--snapshot-out", type=Path, help="导出带账号、时间、类型的客户端快照")
    parser.add_argument("--refresh-metadata", action="store_true")
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=OUTPUT_FILE)
    parser.add_argument("--audit", type=Path, help="默认 <output>.audit.json")
    args = parser.parse_args()
    if args.account and (not args.account.isdigit() or len(args.account) != 17):
        parser.error("--account 必须为 17 位 SteamID64")
    use_api = args.source != "client" and not args.no_api
    use_client = args.source != "api" and not args.no_client and not args.owned_only
    # Explicit offline file mode never reads credentials or starts the helper.
    if args.no_api and args.apps_file and not (args.login or args.local_session or args.source == "client"):
        use_client = False
    if (args.login or args.local_session) and not use_client:
        parser.error("认证选项不能与禁用客户端的模式同时使用")
    if args.owned_only and (args.apps_file or not use_api):
        parser.error("--owned-only 只能用于 API 模式，且不能使用 --apps-file")
    if not use_api and not use_client and not args.apps_file:
        parser.error("至少启用一个数据源")
    report = {}
    audit_path = args.audit or args.output.with_suffix(".audit.json")
    paths = [args.output.resolve(), audit_path.resolve()]
    if args.snapshot_out:
        paths.append(args.snapshot_out.resolve())
    if len(set(paths)) != len(paths):
        parser.error("库、快照与审计输出路径必须不同")
    try:
        library = collect(not args.no_store, not args.owned_only, args.apps_file, use_api,
                          use_client=use_client, login=args.login, local_session=args.local_session,
                          account=args.account, machine=args.machine, strict=args.strict, audit=report,
                          cache_dir=args.cache_dir, refresh_metadata=args.refresh_metadata, snapshot_output=args.snapshot_out)
        if not library and report["membership"] != "client_snapshot":
            raise RuntimeError("未确认空库，保留原输出")
        atomic_json(audit_path, report)
        atomic_json(args.output, library)
    except (OSError, ValueError, RuntimeError, requests.RequestException) as exc:
        message = "Steam 网络请求失败" if isinstance(exc, requests.RequestException) else str(exc)
        parser.exit(1, f"采集失败：{message}\n")
    print(f"采集记录：{len(library)}；状态：{report['status']}")
    print("应用类型：" + "，".join(f"{kind}: {count}" for kind, count in report["summary"]["types"].items()))
    for name, result in report["sources"].items():
        print(f"  {name}: {result['status']} ({result['count']})")
    for warning in report["warnings"]:
        print("提示：" + warning)
    print(f"输出：{args.output}\n审计：{audit_path}")


if __name__ == "__main__":
    main()
