"""Validate saved classifications and expose documented display fields."""
from steam_manufacturers import manufacturer_fields
from steam_observation import first_seen_fields
from steam_membership import membership_fields


def field_evidence(game):
    """Expose only documented per-field evidence, including for legacy input."""
    evidence = game.get('classification_evidence')
    fields = evidence.get('fields') if isinstance(evidence, dict) else None
    result = {}
    for key in ('primary', 'sub', 'vibe', 'intensity', 'slogan'):
        field = fields.get(key) if isinstance(fields, dict) else None
        if not isinstance(field, dict):
            continue
        result[key] = {k: v for k, v in field.items()
                       if k in ('source', 'state', 'reason', 'reference')
                       and isinstance(v, str) and len(v) <= 2000}
    return {'fields': result}


def normalized_games(games):
    if not isinstance(games, list):
        raise ValueError("PICKER_DATA_INVALID")
    result, ids = [], set()
    for game in games:
        if not isinstance(game, dict):
            raise ValueError("PICKER_DATA_INVALID")
        value = game.get("appid")
        if isinstance(value, bool) or not str(value).isdigit() or not 0 < int(value) <= 0xffffffff:
            raise ValueError("PICKER_DATA_INVALID")
        if int(value) in ids or not isinstance(game.get("name"), str) or not isinstance(game.get("analysis"), dict):
            raise ValueError("PICKER_DATA_INVALID")
        ids.add(int(value))
        analysis = game["analysis"]
        if any(not isinstance(analysis.get(k), str) for k in ("primary", "sub", "vibe", "intensity", "slogan")):
            raise ValueError("PICKER_DATA_INVALID")
        observation = first_seen_fields(game)
        result.append({"appid": str(value), "name": game["name"], "run_id": game.get("run_id"),
                       **manufacturer_fields(game),
                       **observation,
                       **membership_fields(game),
                       'first_seen_evidence': {'state': observation['first_seen_status'],
                                               'source': observation['first_seen_source']},
                       "classification_evidence": field_evidence(game),
                       "analysis": {k: analysis[k].strip() for k in ("primary", "sub", "vibe", "intensity", "slogan")}})
    return result
