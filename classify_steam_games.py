"""CLI for five-dimension classification; legacy imports remain available here."""
import json
from steam_library_toolkit.classification import (
    KNOWN, normalize_name, find_known, primary_from_genres, sub_from_name_and_genres,
    vibe_from_genres, intensity_from_genres, slogan_fallback, _classify_one, classify_one,
)

INPUT_FILE = 'steam_library.json'
OUTPUT_FILE = 'steam_library_classified.json'


def main():
    import argparse
    from pathlib import Path
    from steam_classification import add_selection_arguments, load_selected
    parser = argparse.ArgumentParser(description="按五维规则分类，默认仅选择明确的 game 类型")
    base = Path(__file__).resolve().parent
    parser.add_argument("-i", "--input", type=Path, default=base / INPUT_FILE)
    parser.add_argument("-o", "--output", type=Path, default=base / OUTPUT_FILE)
    add_selection_arguments(parser)
    args = parser.parse_args()
    try:
        games, selected = load_selected(args)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"分类失败：{exc}\n")
    from classification_overrides import load_overrides
    try:
        overrides = load_overrides()
    except (OSError, ValueError):
        parser.exit(1, '分类失败：请检查 AppID 校正规则文件\n')
    out = [{**classify_one(g, overrides), "run_id": g.get("run_id")} for g in selected]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"采集记录 {len(games)} 条，已分类 {len(out)} 条，结果已写入 {args.output}")

if __name__ == "__main__":
    main()
