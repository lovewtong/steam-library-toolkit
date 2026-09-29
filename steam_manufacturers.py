"""Manufacturer facets shared by reports, picker and collection plans."""
from steam_metadata import MANUFACTURER_FIELDS, manufacturer_names


def manufacturer_fields(game, rule=None):
    result, evidence = {}, {}
    raw_evidence = game.get('manufacturer_evidence')
    raw_evidence = raw_evidence if isinstance(raw_evidence, dict) else {}
    for key in MANUFACTURER_FIELDS:
        names = manufacturer_names(game.get(key))
        field = raw_evidence.get(key)
        field = field if isinstance(field, dict) else {}
        evidence[key] = {k: v for k, v in field.items()
                         if k in ('source', 'state', 'reason', 'reference', 'fetched_at', 'read_at')
                         and (v is None or type(v) in (str, int, float))}
        if names is None:
            evidence[key] = {'state': 'unknown', 'source': 'unknown'}
        elif not evidence[key]:
            evidence[key] = {'state': 'unverified', 'source': 'legacy'}
        if rule and key in rule:
            from classification_overrides import evidence as rule_evidence
            names = list(rule[key])
            evidence[key] = {**rule_evidence(rule), 'state': 'reviewed'}
        result[key] = names
    result['manufacturer_evidence'] = evidence
    return result
