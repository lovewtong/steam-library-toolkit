"""Shared input, type selection and run identity for both classification schemes."""
from steam_runs import load_library
from steam_sources import APP_TYPES, app_type, select_for_classification


def add_selection_arguments(parser):
    parser.add_argument("--include-type", help="逗号分隔的精确类型，例如 game,demo；all 包含未知类型")
    parser.add_argument("--include-demo", action="store_true")
    parser.add_argument("--include-non-game", action="store_true")
    parser.add_argument("--include-unknown", "--include-unknown-type", action="store_true")
    parser.add_argument("--allow-candidates", action="store_true", help="显式允许分类未经实时确认的候选库")


def load_selected(args):
    rows = load_library(args.input)
    if not args.allow_candidates and any(r.get("membership", {}).get("state") == "candidate" for r in rows):
        raise ValueError("CANDIDATE_LIBRARY：输入仅是候选集合，使用 --allow-candidates 明确选择")
    if args.include_type:
        wanted = set(args.include_type.lower().split(","))
        if wanted != {"all"} and not wanted <= APP_TYPES:
            raise ValueError("TYPE_FILTER_INVALID：类型无效")
        selected = [r for r in rows if wanted == {"all"} or app_type(r.get("app_type")) in wanted]
    else:
        selected = select_for_classification(rows, args.include_demo, args.include_non_game, args.include_unknown)
    return rows, selected
