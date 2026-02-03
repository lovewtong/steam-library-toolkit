# -*- coding: utf-8 -*-
"""
路线 B：API + 本地文件写入，把分类结果写回 Steam 客户端收藏。

流程：
  1）Steam Web API 或 steam_library.json 拿到拥有游戏（appid）
  2）用 steam_library_classified.json 做分类规则 → 收藏名 -> [appid]
  3）写回 Steam userdata 下的收藏文件（需关闭 Steam）

配置：config_local.json 中 steam_api_key、steam_id；可选 steam_install_path。
收藏文件路径（Stelicas 等采用）：Steam/userdata/{Steam64_ID}/config/cloudstorage/cloud-storage-namespace-1.json
"""
import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path
from collections import defaultdict

try:
    import requests
except ImportError:
    requests = None

# --- 路径 ---
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "config_local.json"
CLASSIFIED_FILE = SCRIPT_DIR / "steam_library_classified.json"
RESULT_JSON = SCRIPT_DIR / "steam_collections_result.json"  # 分类名 -> [appid]，由 classify_steam.js 生成
LIBRARY_FILE = SCRIPT_DIR / "steam_library.json"
EXPORT_JSON = SCRIPT_DIR / "steam_collections_export.json"
CLOUD_FILENAME = "cloud-storage-namespace-1.json"


def load_config():
    """从 config_local.json 读取 steam_id、steam_api_key、可选 steam_install_path。"""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"未找到 {CONFIG_PATH.name}。请复制 config_local.example.json 为 config_local.json，"
            "填入 steam_api_key、steam_id；可选 steam_install_path。"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    steam_id = (cfg.get("steam_id") or os.environ.get("STEAM_ID") or "").strip()
    if not steam_id:
        raise ValueError("请在 config_local.json 或环境变量 STEAM_ID 中填写 steam_id（Steam64 位 ID）。")
    return {
        "steam_id": steam_id,
        "steam_api_key": (cfg.get("steam_api_key") or os.environ.get("STEAM_API_KEY") or "").strip(),
        "steam_install_path": (cfg.get("steam_install_path") or os.environ.get("STEAM_PATH") or "").strip(),
    }


def get_steam_install_path(config_path: str) -> str:
    """获取 Steam 安装目录：config > 环境变量 STEAM_PATH > Windows 注册表 > 常见路径。"""
    if config_path:
        p = Path(config_path).resolve()
        if p.is_dir():
            return str(p)
    env = os.environ.get("STEAM_PATH", "").strip()
    if env:
        p = Path(env).resolve()
        if p.is_dir():
            return str(p)
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Valve\Steam",
                0,
                winreg.KEY_READ
            )
            path, _ = winreg.QueryValueEx(key, "InstallPath")
            winreg.CloseKey(key)
            if path and Path(path).is_dir():
                return path
        except Exception:
            pass
        for candidate in [
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")) / "Steam",
            Path("C:/Program Files (x86)/Steam"),
        ]:
            if candidate.is_dir():
                return str(candidate)
    # Linux/macOS 常见路径
    for candidate in [
        Path.home() / ".steam" / "steam",
        Path.home() / ".local/share/Steam",
    ]:
        if candidate.is_dir():
            return str(candidate)
    return ""


def get_owned_appids_from_api(api_key: str, steam_id: str):
    """通过 GetOwnedGames 获取拥有游戏的 appid 列表。"""
    if not requests:
        return None
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {"key": api_key, "steamid": steam_id, "include_appinfo": True, "format": "json"}
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            return None
        games = r.json().get("response", {}).get("games") or []
        return [g["appid"] for g in games]
    except Exception:
        return None


def get_owned_appids_from_library_file():
    """从 steam_library.json 读取 appid 列表（若存在）。"""
    if not LIBRARY_FILE.exists():
        return None
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [g.get("appid") for g in data if g.get("appid") is not None]
        return None
    except Exception:
        return None


def load_collections_from_result_json(owned_appids=None):
    """
    从 steam_collections_result.json 读取收藏（分类名 -> [appid]）。
    若提供 owned_appids，只保留其中的 appid；否则保留全部。
    """
    if not RESULT_JSON.exists():
        raise FileNotFoundError(
            f"未找到 {RESULT_JSON.name}。请先运行 node classify_steam.js 生成分类。"
        )
    with open(RESULT_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{RESULT_JSON.name} 格式应为 分类名 -> [appid] 的对象。")
    owned = set(owned_appids) if owned_appids else None
    collections = {}
    for name, appids in data.items():
        if not isinstance(appids, list):
            continue
        ids = [int(a) for a in appids if isinstance(a, (int, float, str)) and str(a).isdigit()]
        if owned is not None:
            ids = [a for a in ids if a in owned]
        if ids:
            collections[str(name).strip() or "未命名"] = sorted(set(ids))
    return collections


def load_classified_and_build_collections(owned_appids=None):
    """
    读取 steam_library_classified.json，按 强度/核心玩法/细分/氛围 建收藏名 -> [appid]。
    若 provided owned_appids，只包含其中的 appid；否则包含分类里出现的全部。
    """
    if not CLASSIFIED_FILE.exists():
        raise FileNotFoundError(f"未找到 {CLASSIFIED_FILE.name}，请先运行 classify_steam_games.py 生成分类。")
    with open(CLASSIFIED_FILE, "r", encoding="utf-8") as f:
        games = json.load(f)
    owned = set(owned_appids) if owned_appids else None
    by_intensity = defaultdict(list)
    by_primary = defaultdict(list)
    by_sub = defaultdict(list)
    by_vibe = defaultdict(list)
    for g in games:
        appid = g.get("appid")
        if appid is None:
            continue
        try:
            aid = int(appid)
        except (TypeError, ValueError):
            continue
        if owned is not None and aid not in owned:
            continue
        a = g.get("analysis") or {}
        intensity = (a.get("intensity") or "").strip() or "未分类"
        primary = (a.get("primary") or "").strip() or "未分类"
        sub = (a.get("sub") or "").strip() or "未分类"
        vibe = (a.get("vibe") or "").strip() or "未分类"
        by_intensity[intensity].append(aid)
        by_primary[primary].append(aid)
        by_sub[sub].append(aid)
        by_vibe[vibe].append(aid)
    # 收藏名 -> [appid]，避免重名用前缀
    collections = {}
    for name, appids in by_intensity.items():
        if appids:
            collections[f"强度-{name}"] = sorted(set(appids))
    def _uniq_key(prefix, name):
        key = f"{prefix}-{name}"
        n = 0
        while key in collections:
            n += 1
            key = f"{prefix}-{name}-{n}"
        return key
    for name, appids in by_primary.items():
        if appids:
            collections[_uniq_key("核心玩法", name)] = sorted(set(appids))
    for name, appids in by_sub.items():
        if appids:
            collections[_uniq_key("细分", name)] = sorted(set(appids))
    for name, appids in by_vibe.items():
        if appids:
            collections[_uniq_key("氛围", name)] = sorted(set(appids))
    return collections


def get_cloud_storage_path(steam_install_path: str, steam_id: str) -> Path:
    """Steam/userdata/{Steam64_ID}/config/cloudstorage/cloud-storage-namespace-1.json"""
    base = Path(steam_install_path) / "userdata" / steam_id / "config" / "cloudstorage"
    return base / CLOUD_FILENAME


def is_steam_running(steam_install_path: str) -> bool:
    """简单检测本机是否在跑 Steam（Windows 看进程名）。"""
    if sys.platform != "win32":
        return False
    try:
        import subprocess
        out = subprocess.run(
            ["wmic", "process", "get", "name", "/format:csv"],
            capture_output=True, text=True, timeout=5, creationflags=0x08000000
        )
        return "steam.exe" in (out.stdout or "").lower()
    except Exception:
        return False


def read_cloud_storage(file_path: Path):
    """
    读取 cloud-storage-namespace-1.json。
    返回 (raw_data, format_hint)。
    format_hint: "list_of_entries" | "object_with_value_strings" | "single_key_list" | "unknown"
    """
    if not file_path.exists():
        return None, "unknown"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return None, "unknown"
    if isinstance(raw, list):
        return raw, "list_of_entries"
    if isinstance(raw, dict):
        # 单一大 key（如 namespace URL），值为 list
        keys = list(raw.keys())
        if len(keys) == 1:
            v = raw[keys[0]]
            if isinstance(v, list):
                return raw, "single_key_list"
        for v in raw.values() if raw else []:
            if isinstance(v, dict) and "value" in v:
                return raw, "object_with_value_strings"
            if isinstance(v, list):
                return raw, "single_key_list"
        return raw, "object_with_value_strings"
    return raw, "unknown"


def make_collection_entry(collection_id: str, name: str, added_appids: list):
    """生成单条收藏的结构，与 DumpSteamCollections 中 value 一致。"""
    return {
        "id": collection_id,
        "name": name,
        "added": list(added_appids),
        "removed": [],
    }


def generate_uc_id():
    """生成 uc-xxxxxxxx 形式 ID。"""
    return "uc-" + uuid.uuid4().hex[:12]


def _make_steam_entry(cid, entry):
    key = f"user-collections.{cid}"
    return [
        key,
        {
            "key": key,
            "timestamp": 0,
            "value": json.dumps(entry, ensure_ascii=False),
            "conflictResolutionMethod": "custom",
            "strMethodId": "union-collections",
            "version": "1",
        }
    ]


def merge_our_collections_into_raw(raw_data, our_collections: dict, format_hint: str):
    """
    将 our_collections (name -> [appid]) 合并进 raw_data。
    尽量保留原有结构；新增收藏用 uc-xxx 与 Steam 常见 value 格式。
    返回合并后的可 JSON 序列化结构；若无法识别格式则返回 None。
    """
    new_entries = []
    for name, appids in our_collections.items():
        if not appids:
            continue
        cid = generate_uc_id()
        entry = make_collection_entry(cid, name, appids)
        new_entries.append((cid, entry))
    if format_hint == "list_of_entries":
        out = list(raw_data) if raw_data else []
        for cid, entry in new_entries:
            out.append(_make_steam_entry(cid, entry))
        return out
    if format_hint == "single_key_list":
        # 单一大 key，值为 list，与 list_of_entries 结构相同
        (k,) = raw_data.keys()
        out_list = list(raw_data[k]) if raw_data[k] else []
        for cid, entry in new_entries:
            out_list.append(_make_steam_entry(cid, entry))
        return {k: out_list}
    if format_hint == "object_with_value_strings":
        out = dict(raw_data) if isinstance(raw_data, dict) else {}
        for cid, entry in new_entries:
            key = f"user-collections.{cid}"
            out[key] = {
                "key": key,
                "timestamp": 0,
                "value": json.dumps(entry, ensure_ascii=False),
                "conflictResolutionMethod": "custom",
                "strMethodId": "union-collections",
                "version": "1",
            }
        return out
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="路线 B：把分类结果写回 Steam 收藏文件（需关闭 Steam）")
    parser.add_argument("--dry-run", action="store_true", help="只打印路径与将写入的收藏，不写文件")
    parser.add_argument("--backup", action="store_true", default=True, help="写回前备份原文件（默认开启）")
    parser.add_argument("--no-backup", action="store_true", dest="no_backup", help="写回前不备份")
    parser.add_argument("--write", action="store_true", help="实际写回 Steam 目录下的 cloud-storage 文件")
    parser.add_argument("--export-only", action="store_true", help="只导出 steam_collections_export.json，不写 Steam 目录")
    parser.add_argument("--use-api", action="store_true", help="用 Web API 拉取拥有游戏（否则用 steam_library.json）")
    parser.add_argument("--from-result", action="store_true", help="使用 steam_collections_result.json 作为收藏来源（由 classify_steam.js 生成）")
    args = parser.parse_args()
    do_write = args.write and not args.dry_run
    do_backup = args.backup and not args.no_backup

    config = load_config()
    steam_id = config["steam_id"]
    steam_path = get_steam_install_path(config["steam_install_path"])
    if not steam_path:
        print("未找到 Steam 安装目录。请在 config_local.json 中设置 steam_install_path，或设置环境变量 STEAM_PATH。")
        sys.exit(1)
    cloud_path = get_cloud_storage_path(steam_path, steam_id)
    print(f"Steam 目录: {steam_path}")
    print(f"收藏文件: {cloud_path}")
    print(f"文件存在: {cloud_path.exists()}")

    # 拥有游戏
    owned_appids = None
    if args.use_api and config.get("steam_api_key"):
        owned_appids = get_owned_appids_from_api(config["steam_api_key"], steam_id)
        if owned_appids is not None:
            print(f"从 API 获取拥有游戏数: {len(owned_appids)}")
    if owned_appids is None:
        owned_appids = get_owned_appids_from_library_file()
        if owned_appids is not None:
            print(f"从 steam_library.json 获取拥有游戏数: {len(owned_appids)}")
    if owned_appids is None and args.use_api:
        print("未使用 --use-api 或 API 失败时，将使用分类中的全部 appid（不按拥有过滤）。")

    if args.from_result:
        collections = load_collections_from_result_json(owned_appids)
        print("收藏来源: steam_collections_result.json")
    else:
        collections = load_classified_and_build_collections(owned_appids)
        print("收藏来源: steam_library_classified.json")
    print(f"生成的收藏数: {len(collections)}")
    for name, appids in sorted(collections.items(), key=lambda x: -len(x[1])):
        print(f"  - {name}: {len(appids)} 款")

    # 导出供手动合并的 JSON（始终生成）
    with open(EXPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(collections, f, ensure_ascii=False)
    print(f"已导出: {EXPORT_JSON}（可手动合并到 Steam 配置）")

    if args.export_only:
        print("已使用 --export-only，未写入 Steam 目录。")
        return

    if do_write:
        if is_steam_running(steam_path):
            print("警告：检测到 Steam 可能在运行。写收藏文件时请关闭 Steam，避免冲突或损坏。")
        raw_data, format_hint = read_cloud_storage(cloud_path)
        merged = merge_our_collections_into_raw(raw_data, collections, format_hint)
        if merged is None:
            print("无法识别现有收藏文件格式，未写入。请手动将 steam_collections_export.json 合并到 Steam 配置。")
            print("可参考 STEAM_SYNC_README.md 或 Stelicas 项目说明。")
            return
        if do_backup and cloud_path.exists():
            backup_path = cloud_path.with_suffix(".json.bak")
            shutil.copy2(cloud_path, backup_path)
            print(f"已备份: {backup_path}")
        cloud_path.parent.mkdir(parents=True, exist_ok=True)
        # 使用紧凑 JSON（无 indent），与 Steam 原始文件格式一致，降低被覆盖或解析异常风险
        with open(cloud_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False)
        print(f"已写入: {cloud_path}")
        print("请先完全关闭 Steam（含托盘图标），再运行本脚本；写完后可尝试以离线模式启动 Steam 再查看收藏。")
    else:
        if args.dry_run:
            print("--dry-run：未写入任何文件。")
        else:
            print("未使用 --write，未写入 Steam 目录。若要写回，请加上 --write（并先关闭 Steam）。")


if __name__ == "__main__":
    main()
