"""Shared trust checks for current client and Steam Families observations."""


def verified_source(source):
    if not isinstance(source, dict):
        return False
    proof = source.get('completeness')
    return (source.get('status') == 'ok' and source.get('state') == 'complete'
            and isinstance(proof, dict) and proof.get('verified') is True)


def verified_family_source(source):
    if not verified_source(source):
        return False
    proof = source.get('completeness', {})
    count = source.get('count')
    if type(count) is not int or count < 0:
        return False
    if not all(proof.get(k) is True for k in ('account_checked', 'owners_checked', 'group_checked')) or proof.get('reads') != 2:
        return False
    if proof.get('family_state') == 'not_member':
        return count == 0 and type(proof.get('returned_apps')) is int and proof['returned_apps'] == 0
    return (proof.get('family_state') == 'member' and type(proof.get('returned_apps')) is int
            and type(proof.get('max_apps')) is int and 0 <= proof['returned_apps'] < proof['max_apps']
            and type(proof.get('eligible_games')) is int and proof['eligible_games'] == count
            and count <= proof['returned_apps'])


def family_evidence_valid(row):
    proof = row.get('family_evidence', {})
    return (row.get('app_type') == 'game' and isinstance(proof, dict) and proof.get('verified') is True
            and proof.get('source') == 'family_library' and type(proof.get('exclude_reason')) is int
            and proof['exclude_reason'] == 0 and type(proof.get('own')) is bool and type(proof.get('shared')) is bool
            and (proof['own'] or proof['shared']) and type(proof.get('owner_count')) is int
            and int(proof['own']) + int(proof['shared']) <= proof['owner_count'] <= 6
            and (proof['shared'] or proof['owner_count'] == 1))


def trusted_current_membership(audit):
    sources = audit.get('sources', {})
    if not verified_source(sources.get('client_library')):
        return False
    kind = audit.get('membership')
    return kind == 'client_snapshot' or (kind == 'accessible_snapshot' and verified_family_source(sources.get('family_library')))


def verified_membership_row(row, audit):
    membership = row.get('membership', {})
    if not trusted_current_membership(audit) or membership.get('state') != 'present':
        return False
    source = membership.get('source')
    return source == 'client_library' or (source == 'family_library' and audit.get('membership') == 'accessible_snapshot'
                                          and family_evidence_valid(row))


def membership_fields(row):
    """Public per-game view, without account, family or owner identities."""
    membership = row.get('membership', {})
    return {'ownership': row.get('ownership', 'unknown'),
            'membership_source': membership.get('source', row.get('membership_source')),
            'family_evidence': {key: value for key, value in row.get('family_evidence', {}).items()
                                if key in ('source', 'verified', 'own', 'shared', 'owner_count', 'exclude_reason')}}
