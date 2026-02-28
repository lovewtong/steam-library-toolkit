"""
Steam 游戏库本地采集脚本
从 Steam API 获取：游戏名、appid、总时长、最近游玩时间；
可选从商店 API 获取：类型/标签、是否多人、是否手柄支持。
默认会包含已游玩免费游戏/免费许可记录；可用 --owned-only 关闭。
密钥仅从本地 config_local.json 读取，不提交到仓库。
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

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
    """从本地 config_local.json 加载 API Key 与 Steam ID，不提交到仓库。"""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"未找到 {CONFIG_PATH.name}。请复制 config_local.example.json 为 config_local.json，"
            "填入你的 steam_api_key 和 steam_id。该文件已在 .gitignore 中，不会被提交。"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    api_key = cfg.get("steam_api_key", "").strip()
    steam_id = cfg.get("steam_id", "").strip()
    if not api_key or not steam_id:
        raise ValueError("config_local.json 中需填写 steam_api_key 和 steam_id。")
    return {"api_key": api_key, "steam_id": steam_id}


def get_owned_games(api_key: str, steam_id: str, include_non_inventory: bool = True):
    """获取游戏列表：appid、name、playtime_forever、rtime_last_played 等。"""
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": api_key,
        "steamid": steam_id,
        "include_appinfo": True,
        "format": "json",
    }
    if include_non_inventory:
        params["include_played_free_games"] = True
        params["include_free_sub"] = True
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"GetOwnedGames 请求失败: {resp.status_code} - {resp.text[:200]}")
    data = resp.json()
    games = data.get("response", {}).get("games") or []
    return games


def get_store_details(appid: int):
    """
    获取商店详情（可选）：类型、分类（含多人/手柄等）。
    使用公开商店 API，有频率限制，需控制请求间隔。
    """
    url = "https://store.steampowered.com/api/appdetails"
    params = {"appids": appid, "l": "schinese"}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
    except Exception as e:
        return None
    if not data or str(appid) not in data or not data[str(appid)].get("success"):
        return None
    g = data[str(appid)].get("data", {})
    genres = [x.get("description", "") for x in g.get("genres", []) if x.get("description")]
    categories = [x.get("description", "") for x in g.get("categories", []) if x.get("description")]

    # 从 categories 推断是否多人、是否手柄（常见英文/简中描述）
    multi_keywords = ("多人", "Multi-player", "Online Multi", "Co-op", "Online Co-op", "LAN", "Shared/Split")
    ctrl_keywords = ("手柄", "Controller", "Full controller", "Partial controller")
    is_multiplayer = any(k in c for c in categories for k in multi_keywords)
    is_controller = any(k in c for c in categories for k in ctrl_keywords)

    return {
        "genres": genres,
        "categories": categories,
        "is_multiplayer": is_multiplayer,
        "is_controller": is_controller,
    }


def collect(fetch_store: bool = True, include_non_inventory: bool = True):
    """
    执行采集：必选字段来自 GetOwnedGames，可选字段来自商店 API。
    fetch_store=True 时会逐条请求商店并写入类型/多人/手柄，耗时会变长。
    """
    config = load_config()
    games_raw = get_owned_games(
        config["api_key"],
        config["steam_id"],
        include_non_inventory=include_non_inventory,
    )
    if not games_raw:
        print("未获取到游戏列表，请检查 Steam ID 与 API Key，以及账号是否公开游戏库。")
        return []

    library = []
    for i, g in enumerate(games_raw):
        appid = g.get("appid")
        name = g.get("name", "")
        playtime_forever = g.get("playtime_forever") or 0  # 分钟
        rtime_last_played = g.get("rtime_last_played")  # Unix 时间戳，可能缺失
        playtime_2weeks = g.get("playtime_2weeks") or 0

        row = {
            "appid": appid,
            "name": name,
            "playtime_minutes": playtime_forever,
            "playtime_2weeks_minutes": playtime_2weeks,
            "last_played_at": rtime_last_played,
            "last_played_iso": datetime.utcfromtimestamp(rtime_last_played).isoformat() + "Z" if rtime_last_played else None,
        }

        if fetch_store:
            print(f"[{i+1}/{len(games_raw)}] {name} ({appid}) ...")
            details = get_store_details(appid)
            if details:
                row["genres"] = details["genres"]
                row["categories"] = details["categories"]
                row["is_multiplayer"] = details["is_multiplayer"]
                row["is_controller"] = details["is_controller"]
            else:
                row["genres"] = []
                row["categories"] = []
                row["is_multiplayer"] = None
                row["is_controller"] = None
            time.sleep(STORE_REQUEST_DELAY)
        else:
            print(f"[{i+1}/{len(games_raw)}] {name}")
            row["genres"] = []
            row["categories"] = []
            row["is_multiplayer"] = None
            row["is_controller"] = None

        library.append(row)

    return library


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Steam 游戏库本地采集，输出 JSON")
    parser.add_argument("--no-store", action="store_true", help="不请求商店 API，仅基础字段，速度快")
    parser.add_argument(
        "--owned-only",
        action="store_true",
        help="仅拉取传统拥有游戏；不额外包含免费/非库存计数游戏记录",
    )
    parser.add_argument("-o", "--output", default=str(OUTPUT_FILE), help="输出 JSON 路径")
    args = parser.parse_args()

    print("正在从 Steam 获取游戏库...")
    library = collect(
        fetch_store=not args.no_store,
        include_non_inventory=not args.owned_only,
    )
    if not library:
        return

    out_path = Path(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(library, f, ensure_ascii=False, indent=2)
    print(f"采集完成，共 {len(library)} 款游戏，已保存至 {out_path}")


if __name__ == "__main__":
    main()
