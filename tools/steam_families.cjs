'use strict';
// Group and owner identities are used only for validation and never returned.
const MAX_APPS = 100000;
async function familyLibrary(token, account, fetcher, policy = {}) {
  const {call, SourceError} = require('./steam_web_sources.cjs');
  policy = {...policy, deadline: Math.min(policy.deadline ?? Infinity, Date.now() + 90000)};
  const invalid = () => { throw new SourceError('FAMILY_RESPONSE_INVALID', 'invalid'); };
  const changed = () => { throw new SourceError('FAMILY_LIST_CHANGED', 'partial'); };
  const group = async () => {
    const body = await call('IFamilyGroupsService', 'GetFamilyGroupForUser', token,
      {steamid: account, include_family_group_response: 'true'}, fetcher, policy);
    if (body.is_not_member_of_any_group === true && (!body.family_groupid || body.family_groupid === '0'))
      return {id: null, members: [], fingerprint: 'no_family'};
    if (body.is_not_member_of_any_group === true || typeof body.family_groupid !== 'string'
        || !/^[1-9]\d{0,19}$/.test(body.family_groupid) || !Array.isArray(body.family_group?.members)) invalid();
    const members = body.family_group.members;
    const ids = members.map(m => m?.steamid);
    if (!ids.includes(account)) throw new SourceError('ACCOUNT_MISMATCH', 'account_mismatch');
    if (!ids.length || ids.length > 6 || new Set(ids).size !== ids.length || members.some(m =>
      typeof m.steamid !== 'string' || !/^\d{17}$/.test(m.steamid) || ![1, 2].includes(m.role))) invalid();
    return {id: body.family_groupid, members: ids,
      fingerprint: JSON.stringify([body.family_groupid, members.map(m => [m.steamid, m.role]).sort()])};
  };
  const before = await group();
  const completeness = {verified: true, account_checked: true, owners_checked: true,
    group_checked: true, reads: 2, protocol_completion_marker: false, semantic_completeness_proven: false};
  if (!before.id) {
    if ((await group()).fingerprint !== before.fingerprint) changed();
    return {state: 'complete', records: [], completeness: {...completeness,
      method: 'two_consistent_no_family_responses', family_state: 'not_member', returned_apps: 0}};
  }
  const read = async () => {
    const body = await call('IFamilyGroupsService', 'GetSharedLibraryApps', token,
      {family_groupid: before.id, steamid: account, include_own: 'true', include_excluded: 'true',
        include_non_games: 'true', language: 'schinese', max_apps: String(MAX_APPS)}, fetcher, policy);
    if (body.owner_steamid !== account) throw new SourceError('ACCOUNT_MISMATCH', 'account_mismatch');
    if (!Array.isArray(body.apps)) throw new SourceError('FAMILY_LIST_UNCONFIRMED', 'partial');
    if (body.apps.length >= MAX_APPS || body.has_more === true || body.truncated === true
        || body.next_cursor || body.next_page_token) throw new SourceError('FAMILY_LIST_TRUNCATED', 'partial');
    const ids = new Set(), rows = [], fingerprints = [];
    for (const app of body.apps) {
      if (!app || !Number.isInteger(app.appid) || app.appid <= 0 || app.appid > 0xffffffff || ids.has(app.appid)
          || typeof app.name !== 'string' || !Number.isInteger(app.app_type) || app.app_type <= 0
          || !Number.isInteger(app.exclude_reason) || app.exclude_reason < 0
          || !Array.isArray(app.owner_steamids) || !app.owner_steamids.length
          || new Set(app.owner_steamids).size !== app.owner_steamids.length
          || app.owner_steamids.some(id => !before.members.includes(id))) invalid();
      ids.add(app.appid);
      fingerprints.push([app.appid, app.app_type, app.exclude_reason, [...app.owner_steamids].sort()]);
      if (app.app_type !== 1 || app.exclude_reason !== 0) continue;
      rows.push({appid: app.appid, name: app.name, app_type: 'game', family_evidence: {
        source: 'family_library', verified: true, own: app.owner_steamids.includes(account),
        shared: app.owner_steamids.some(id => id !== account), owner_count: app.owner_steamids.length, exclude_reason: 0}});
    }
    return {rows, count: body.apps.length, fingerprint: JSON.stringify(fingerprints.sort((a, b) => a[0] - b[0]))};
  };
  const first = await read(), second = await read(), after = await group();
  if (first.fingerprint !== second.fingerprint || before.fingerprint !== after.fingerprint) changed();
  return {state: 'complete', records: second.rows, completeness: {...completeness,
    method: 'two_consistent_family_responses', family_state: 'member', member_count: before.members.length,
    returned_apps: second.count, max_apps: MAX_APPS, eligible_games: second.rows.length}};
}
module.exports = {familyLibrary, MAX_APPS};
