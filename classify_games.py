"""
基于 steam_library.json 的游戏库自动分类
输出：主分类 + 多标签；分类结果表格（CSV/Markdown）及维护规则引用。
"""
import json
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
from steam_sources import select_for_classification
from steam_classification import add_selection_arguments, load_selected
from classification_rules import genre_category

# --- 路径 ---
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "steam_library.json"
DEFAULT_TABLE_CSV = SCRIPT_DIR / "game_library_classified.csv"
DEFAULT_TABLE_MD = SCRIPT_DIR / "game_library_classified.md"
RULES_FILE = SCRIPT_DIR / "CLASSIFICATION_RULES.md"


# 主分类映射由 classification_rules.py 统一维护。

# 标签：可多选，用于细粒度描述
TAG_RULES = [
    {"tag": "单人", "condition": "single"},           # 仅单人
    {"tag": "多人", "condition": "multiplayer"},     # is_multiplayer True
    {"tag": "合作", "condition": "coop"},            # categories 含 Co-op
    {"tag": "手柄", "condition": "controller"},      # is_controller True
    {"tag": "剧情", "keywords": ["剧情", "Story", "叙事", "Visual Novel", "视觉小说"]},
    {"tag": "Roguelike", "keywords": ["Roguelike", "Roguelite", "Rogue"]},
    {"tag": "开放世界", "keywords": ["开放世界", "Open World", "沙盒", "Sandbox"]},
    {"tag": "像素/复古", "keywords": ["像素", "Pixel", "复古", "Retro", "2D"]},
    {"tag": "恐怖", "keywords": ["恐怖", "Horror", "惊悚"]},
    {"tag": "回合制", "keywords": ["回合", "Turn-based", "Turn-Based"]},
    {"tag": "即时战略", "keywords": ["RTS", "即时战略", "Real-Time Strategy"]},
    {"tag": "卡牌", "keywords": ["卡牌", "Card", "Deck"]},
    {"tag": "模拟", "keywords": ["模拟", "Simulation", "管理", "建造"]},
]


def load_library(path: Path) -> list:
    """加载 steam_library.json。"""
    if not path.exists():
        raise FileNotFoundError(f"未找到 {path}，请先运行 steam_collect.py 生成游戏库 JSON。")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def match_main_category(game: dict) -> str:
    """只使用明确的类型标签；名称特例通过 AppID 校正维护。"""
    return genre_category(game.get('genres'))[0]


def match_tags(game: dict) -> list[str]:
    """匹配多标签。"""
    tags = []
    name = (game.get("name") or "").lower()
    genres = [x.lower() for x in (game.get("genres") or [])]
    categories = [x.lower() for x in (game.get("categories") or [])]
    combined = name + " " + " ".join(genres) + " " + " ".join(categories)

    for rule in TAG_RULES:
        if rule.get("condition") == "multiplayer" and game.get("is_multiplayer") is True:
            tags.append(rule["tag"])
        elif rule.get("condition") == "controller" and game.get("is_controller") is True:
            tags.append(rule["tag"])
        elif rule.get("condition") == "coop" and any("co-op" in c or "合作" in c for c in categories):
            tags.append(rule["tag"])
        elif rule.get("condition") == "single":
            if game.get("is_multiplayer") is False or any("single-player" in c or "单人" in c for c in categories):
                tags.append(rule["tag"])
        elif rule.get("keywords"):
            for kw in rule["keywords"]:
                if kw.lower() in combined:
                    tags.append(rule["tag"])
                    break

    return list(dict.fromkeys(tags))  # 去重保序


def classify_library(library: list, overrides=None) -> list[dict]:
    """对每款游戏赋予主分类与标签。"""
    from classification_overrides import load_overrides, correction, evidence
    overrides = load_overrides() if overrides is None else overrides
    result = []
    for g in library:
        rule = correction(g, overrides)
        main = rule['main_category'] if rule else match_main_category(g)
        tags = match_tags(g)
        result.append({
            "run_id": g.get("run_id"),
            "appid": g.get("appid"),
            "name": g.get("name"),
            "playtime_minutes": g.get("playtime_minutes") if g.get("playtime_available", True) else None,
            "playtime_available": g.get("playtime_available", g.get("playtime_minutes") is not None),
            "app_type": g.get("app_type", "unknown"),
            "playtime_state": g.get("playtime", {}).get("state"),
            **last_played_fields(g),
            "main_category": main,
            "classification_evidence": {
                **(evidence(rule) if rule else genre_category(g.get('genres'))[1]),
                'fields': {
                    'main_category': {**evidence(rule), 'state': 'reviewed'} if rule else genre_category(g.get('genres'))[1],
                    'tags': {'source': 'tag_rules', 'state': 'inferred'},
                }},
            "tags": tags,
            "is_multiplayer": g.get("is_multiplayer"),
            "is_controller": g.get("is_controller"),
        })
    return result


def last_played_fields(game):
    """The timestamp's own evidence governs its display, independently of total playtime."""
    evidence = game.get('playtime_evidence', {}).get('rtime_last_played')
    if isinstance(evidence, dict):
        state = evidence.get('state', 'unknown')
        value = evidence.get('value') if state != 'unknown' else None
        iso = datetime.fromtimestamp(value, timezone.utc).isoformat().replace('+00:00', 'Z') if value else None
        source, observed = evidence.get('source'), evidence.get('observed_at')
    else:
        value, iso = game.get('last_played_at'), game.get('last_played_iso')
        state = 'unverified' if value is not None or iso else 'unknown'
        source, observed = None, None
    return {'last_played_at': value, 'last_played_iso': iso, 'last_played_status': state,
            'last_played_source': source, 'last_played_observed_at': observed}


def last_played_str(row):
    state = row.get('last_played_status', 'unverified' if row.get('last_played_iso') else 'unknown')
    if state == 'unknown':
        return '未知'
    value = '无时间记录' if row.get('last_played_at') == 0 else (row.get('last_played_iso') or '')[:10] or '未知'
    prefix = '历史 ' if state == 'historical' else '未核验 ' if state == 'unverified' else ''
    return prefix + value


def playtime_str(minutes: int, available=True, state=None) -> str:
    if not available or minutes is None:
        return "未知"
    if state == "historical":
        return "历史 " + playtime_str(minutes)
    if minutes == 0:
        return "0 分钟"
    if minutes < 60:
        return f"{minutes} 分钟"
    h, m = divmod(int(minutes), 60)
    if m:
        return f"{h}h {m}m"
    return f"{h}h"


def write_csv(classified: list[dict], path: Path) -> None:
    """输出 CSV 表格。"""
    rows = []
    rows.append(["appid", "name", "playtime", "last_played", "main_category", "tags", "multiplayer", "controller", "run_id", "playtime_minutes", "playtime_status",
                 "last_played_at", "last_played_status", "last_played_source", "last_played_observed_at"])
    for r in classified:
        tags_str = ";".join(r["tags"]) if r["tags"] else ""
        last = last_played_str(r)
        multi = "是" if r.get("is_multiplayer") else ("否" if r.get("is_multiplayer") is False else "")
        ctrl = "是" if r.get("is_controller") else ("否" if r.get("is_controller") is False else "")
        known = r.get('playtime_available', True) and r['playtime_minutes'] is not None
        status = 'historical' if known and r.get('playtime_state') == 'historical' else 'known' if known else 'unknown'
        rows.append([r['appid'], r['name'], playtime_str(r['playtime_minutes'], known, r.get('playtime_state')),
                     last, r['main_category'], tags_str, multi, ctrl, r.get('run_id'),
                     r['playtime_minutes'] if known else None, status,
                     r.get('last_played_at'), r.get('last_played_status', 'unknown'),
                     r.get('last_played_source'), r.get('last_played_observed_at')])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        csv.writer(stream).writerows(rows)


def write_md_table(classified: list[dict], path: Path, run_id=None) -> None:
    """输出 Markdown 表格。"""
    lines = [
        "# 游戏库分类结果",
        "<!-- run_id: " + (run_id or (classified[0].get("run_id") if classified else None) or "legacy") + " -->",
        "",
        "基于 `steam_library.json` 自动分类，主分类 + 多标签。维护规则见 `CLASSIFICATION_RULES.md`。",
        "",
        "| 游戏名 | appid | 总时长 | 最近游玩 | 主分类 | 标签 | 多人 | 手柄 | 最近游玩状态 | 来源 | 观察时间 |",
        "|--------|-------|--------|----------|--------|------|------|------|--------------|------|----------|",
    ]
    for r in classified:
        last = last_played_str(r)
        tags_str = "、".join(r["tags"]) if r["tags"] else "-"
        multi = "是" if r.get("is_multiplayer") else ("否" if r.get("is_multiplayer") is False else "-")
        ctrl = "是" if r.get("is_controller") else ("否" if r.get("is_controller") is False else "-")
        name_esc = (r["name"] or "").replace("|", "\\|")
        time_evidence = [str(r.get(k) or '-').replace('|', '\\|').replace('\n', ' ') for k in
                         ('last_played_status', 'last_played_source', 'last_played_observed_at')]
        lines.append(f"| {name_esc} | {r['appid']} | {playtime_str(r['playtime_minutes'], r.get('playtime_available', True), r.get('playtime_state'))} | {last} | {r['main_category']} | {tags_str} | {multi} | {ctrl} | " + ' | '.join(time_evidence) + ' |')
    lines.extend(["", f"共 {len(classified)} 条分类记录。", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def print_summary(classified: list[dict]) -> None:
    """打印主分类统计。"""
    by_cat = defaultdict(int)
    for r in classified:
        by_cat[r["main_category"]] += 1
    print("\n主分类统计:")
    for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="游戏库自动分类，输出表格与规则")
    parser.add_argument("-i", "--input", default=str(DEFAULT_INPUT), help="输入 steam_library.json 路径")
    parser.add_argument("--csv", default=str(DEFAULT_TABLE_CSV), help="输出 CSV 路径")
    parser.add_argument("--md", default=str(DEFAULT_TABLE_MD), help="输出 Markdown 路径")
    add_selection_arguments(parser)
    args = parser.parse_args()

    try:
        library, selected = load_selected(args)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"分类失败：{exc}\n")
    try:
        classified = classify_library(selected)
    except (OSError, ValueError):
        parser.exit(1, '分类失败：请检查 AppID 校正规则文件\n')

    write_csv(classified, Path(args.csv))
    write_md_table(classified, Path(args.md))

    print(f"采集记录 {len(library)} 条，已分类 {len(classified)} 条；未选条目仍保留在原始 JSON 中")
    print(f"  CSV: {args.csv}")
    print(f"  MD:  {args.md}")
    print_summary(classified)
    if RULES_FILE.exists():
        print(f"维护规则: {RULES_FILE}")
if __name__ == "__main__":
    main()
