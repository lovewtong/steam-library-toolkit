"""Shared coarse genre mapping. Titles are not evidence of a store genre."""
from classification_overrides import MAIN_TO_PRIMARY

# More specific gameplay wins over broad Action/Adventure and Indie labels.
GENRE_RULES = (
    ('射击', ('Shooter', 'FPS', 'TPS', '射击')),
    ('RPG', ('RPG', 'JRPG', '角色扮演')),
    ('策略', ('Strategy', '策略')),
    ('模拟经营', ('Simulation', '模拟')),
    ('体育/竞速', ('Sports', 'Racing', '体育', '竞速')),
    ('动作/冒险', ('Action', 'Adventure', '动作', '冒险')),
    ('休闲/益智', ('Casual', 'Puzzle', '休闲', '益智', '解谜')),
    ('独立/其他', ('Indie', '独立')),
)


def genre_category(genres):
    labels = {label.strip().casefold() for label in (genres or []) if isinstance(label, str)}
    for category, aliases in GENRE_RULES:
        matched = sorted(labels.intersection(alias.casefold() for alias in aliases))
        if matched:
            return category, {'source': 'genre_rules', 'state': 'inferred', 'matched_genres': matched}
    return '其他', {'source': 'unknown', 'state': 'unknown', 'reason': 'no_recognized_genre'}


def genre_primary(genres):
    return MAIN_TO_PRIMARY[genre_category(genres)[0]]
