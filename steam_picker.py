# -*- coding: utf-8 -*-
"""
用分类数据在本地「应用」：按核心玩法/细分/氛围/强度筛选游戏，并用 Steam 打开。
Steam 本身不支持写入自定义分类，这里通过「筛选 + 启动」在本地使用你的分类。
"""
import json
import argparse
import webbrowser
import subprocess
import sys
import os

CLASSIFIED_FILE = "steam_library_classified.json"
STEAM_URL_PREFIX = "steam://rungameid/"

def load_classified(source=None, allow_candidates=False):
    from steam_picker_server import PickerLibrary
    return PickerLibrary(source, allow_candidates).read()["games"]

def filter_games(games, primary=None, sub=None, vibe=None, intensity=None, name_contains=None):
    """按维度筛选，空表示不限制。"""
    out = []
    for g in games:
        a = g.get("analysis") or {}
        if primary and primary not in a.get("primary", ""):
            continue
        if sub and sub not in a.get("sub", ""):
            continue
        if vibe and vibe not in a.get("vibe", ""):
            continue
        if intensity and intensity not in a.get("intensity", ""):
            continue
        if name_contains and name_contains.lower() not in (g.get("name") or "").lower():
            continue
        out.append(g)
    return out

def main():
    parser = argparse.ArgumentParser(
        description="按分类筛选游戏，或在浏览器中打开选游戏页面，或用 Steam 启动游戏。"
    )
    parser.add_argument("--primary", "-p", type=str, help="核心玩法关键词，如：射击、策略、角色扮演")
    parser.add_argument("--sub", "-s", type=str, help="细分流派关键词，如：肉鸽、类魂、塔防")
    parser.add_argument("--vibe", "-v", type=str, help="氛围关键词，如：解压、黑暗、赛博朋克")
    parser.add_argument("--intensity", "-i", type=str, choices=["低", "中", "高"], help="游玩强度")
    parser.add_argument("--name", "-n", type=str, help="游戏名称包含")
    parser.add_argument("--open", "-o", type=int, metavar="INDEX", help="用 Steam 启动筛选结果中的第 N 个（从 0 开始）")
    parser.add_argument("--serve", action="store_true", help="启动本地选游戏页面（浏览器 + 简单 HTTP 服务）")
    parser.add_argument("--input", help="采集库或 .current.json 指针；默认 steam_library.json")
    parser.add_argument("--allow-candidates", action="store_true", help="显式允许查看候选库")
    parser.add_argument("--port", type=int, default=8765, help="仅监听 127.0.0.1")
    parser.add_argument("--no-browser", action="store_true", help="启动服务时不自动打开浏览器")
    parser.add_argument("--list", "-l", action="store_true", help="只列出筛选结果，不交互")
    parser.add_argument("--export-collections", action="store_true", help="导出「收藏清单」MD，便于在 Steam 里建同名收藏并对照添加")
    args = parser.parse_args()

    if not 0 <= args.port <= 65535:
        parser.error("--port 必须在 0..65535 范围内")
    try:
        games = load_classified(args.input, args.allow_candidates)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "无法读取游戏库：请检查采集结果、运行校验和 --input；候选库需 --allow-candidates。\n")
    filtered = filter_games(
        games,
        primary=args.primary,
        sub=args.sub,
        vibe=args.vibe,
        intensity=args.intensity,
        name_contains=args.name,
    )

    if args.export_collections:
        # 按 强度 / 核心玩法 / 细分 / 氛围 分组，生成 MD 清单
        out_path = os.path.join(os.path.dirname(__file__), "steam_collections_guide.md")
        lines = [
            "# Steam 收藏清单（按分类对照添加）",
            "",
            "在 Steam 客户端：**视图 → 收藏 → 创建新收藏**，按下面分组建同名收藏，再根据下列游戏名在库中搜索并「添加到收藏」。",
            "",
            "---",
            "",
        ]
        from collections import defaultdict
        by_intensity = defaultdict(list)
        by_primary = defaultdict(list)
        by_sub = defaultdict(list)
        by_vibe = defaultdict(list)
        for g in games:
            a = g.get("analysis") or {}
            name = g.get("name") or ""
            by_intensity[a.get("intensity") or "未分类"].append(name)
            by_primary[a.get("primary") or "未分类"].append(name)
            by_sub[a.get("sub") or "未分类"].append(name)
            by_vibe[a.get("vibe") or "未分类"].append(name)
        def section(title, d):
            nonlocal lines
            lines.append(f"## {title}")
            lines.append("")
            for key in sorted(d.keys(), key=lambda x: (-len(d[x]), x)):
                lines.append(f"### 收藏名：{key}")
                lines.append("")
                for n in sorted(d[key]):
                    lines.append(f"- {n}")
                lines.append("")
        section("按强度", by_intensity)
        section("按核心玩法", by_primary)
        section("按细分流派", by_sub)
        section("按氛围", by_vibe)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"已导出收藏清单：{out_path}")
        return

    if args.serve:
        # 启动内置 HTTP 服务 + 打开浏览器
        try:
            from steam_picker_server import PickerLibrary, create_server
            with create_server(PickerLibrary(args.input, args.allow_candidates), args.port) as server:
                url = f"http://127.0.0.1:{server.server_port}/"
                if not args.no_browser:
                    webbrowser.open(url)
                print("选游戏页面地址:", url, flush=True)
                print("刷新页面会读取所选采集目标的最新运行；Ctrl+C 可停止服务。", flush=True)
                server.serve_forever()
        except KeyboardInterrupt:
            pass
        except OSError:
            parser.exit(1, "网页服务启动失败：端口可能被占用，请使用 --port 指定其他端口。\n")
        return

    if args.open is not None:
        if not filtered:
            print("没有匹配的游戏。")
            sys.exit(1)
        idx = args.open
        if idx < 0 or idx >= len(filtered):
            print(f"索引需在 0 到 {len(filtered)-1} 之间。")
            sys.exit(1)
        appid = filtered[idx].get("appid")
        url = STEAM_URL_PREFIX + str(appid)
        print("正在用 Steam 启动:", filtered[idx].get("name"), "(", url, ")")
        try:
            if sys.platform == "win32":
                os.startfile(url)
            else:
                webbrowser.open(url)
        except Exception as e:
            print("打开失败:", e, "可手动在浏览器或 Steam 中打开:", url)
        return

    # 列出结果
    if not args.list and not filtered:
        print("提示：未加筛选条件时将显示全部游戏。可用 -p / -s / -v / -i / -n 筛选。")
    print(f"共 {len(filtered)} 款")
    for i, g in enumerate(filtered[:50]):
        a = g.get("analysis") or {}
        print(f"  [{i}] {g.get('name')} | {a.get('primary')} | {a.get('sub')} | {a.get('vibe')} | {a.get('intensity')} | {a.get('slogan')}")
    if len(filtered) > 50:
        print(f"  ... 仅显示前 50 款，共 {len(filtered)} 款。")
    print("\n用 Steam 启动： python steam_picker.py <筛选条件> --open <序号>")

if __name__ == "__main__":
    main()
