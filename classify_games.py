"""CLI for table classification; legacy imports remain available here."""
from pathlib import Path
from steam_classification import add_selection_arguments, load_selected
from steam_library_toolkit.paths import ROOT as SCRIPT_DIR, OUTPUT_FILE as DEFAULT_INPUT, RULES_FILE
from steam_library_toolkit.tables import (
    TAG_RULES, load_library, match_main_category, match_tags, classify_library,
    last_played_fields, last_played_str, playtime_str, write_csv, write_md_table, print_summary,
)

DEFAULT_TABLE_CSV = SCRIPT_DIR / 'game_library_classified.csv'
DEFAULT_TABLE_MD = SCRIPT_DIR / 'game_library_classified.md'


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
