'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {familyLibrary, MAX_APPS} = require('../tools/steam_families.cjs');
const {collectWebSources} = require('../tools/steam_web_sources.cjs');
const account = '76561198000000001', other = '76561198000000002';
const group = () => ({family_groupid: '123', family_group: {members: [{steamid: account, role: 1}, {steamid: other, role: 2}]}});
const app = (appid = 3017860, owners = [other]) => ({appid, name: 'Game', app_type: 1, exclude_reason: 0,
  owner_steamids: owners, rt_playtime: 999, rt_time_acquired: 123});
const list = apps => ({owner_steamid: account, apps});
function sequence(items, seen = []) {
  return async url => {seen.push(new URL(url)); const body = items.shift(); assert.notEqual(body, undefined);
    return {status: 200, headers: {get: () => '1'}, json: async () => ({response: body})};};
}
test('family eligibility extends games only, with stable owners and no private identities or owner times', async () => {
  const apps = [app(), app(2183900), app(10, [account, other]), {...app(20), app_type: 4}, {...app(30), exclude_reason: 1}];
  const seen = [];
  const result = await familyLibrary('private-token', account, sequence([group(), list(apps), list([...apps].reverse()), group()], seen));
  assert.deepEqual(result.records.map(r => r.appid), [10, 2183900, 3017860]);
  assert.equal(result.records[0].family_evidence.own, true);
  assert.equal(result.records[1].family_evidence.own, false);
  assert.equal(result.completeness.returned_apps, 5);
  assert.equal(result.completeness.semantic_completeness_proven, false);
  assert.equal(seen[1].searchParams.get('max_apps'), String(MAX_APPS));
  for (const value of [account, other, 'private-token', 'rt_playtime', 'rt_time_acquired', 'family_groupid'])
    assert.equal(JSON.stringify(result).includes(value), false);
});
test('confirmed no-family and confirmed empty list are distinct from absent list', async () => {
  const noGroup = {is_not_member_of_any_group: true};
  assert.equal((await familyLibrary('token', account, sequence([noGroup, noGroup]))).completeness.family_state, 'not_member');
  assert.deepEqual((await familyLibrary('token', account, sequence([group(), list([]), list([]), group()]))).records, []);
  await assert.rejects(() => familyLibrary('token', account, sequence([group(), {owner_steamid: account}])), {code: 'FAMILY_LIST_UNCONFIRMED'});
  await assert.rejects(() => familyLibrary('token', account, sequence([noGroup, group()])), {code: 'FAMILY_LIST_CHANGED'});
});
test('wrong account, response owner and foreign or duplicate app owners fail closed', async () => {
  const wrong = group(); wrong.family_group.members = [{steamid: other, role: 1}];
  await assert.rejects(() => familyLibrary('token', account, sequence([wrong])), {code: 'ACCOUNT_MISMATCH'});
  await assert.rejects(() => familyLibrary('token', account, sequence([group(), {owner_steamid: other, apps: []}])), {code: 'ACCOUNT_MISMATCH'});
  for (const owners of [[], [other, other], ['76561198000000003'], [Number(other)]])
    await assert.rejects(() => familyLibrary('token', account, sequence([group(), list([app(1, owners)])])), {code: 'FAMILY_RESPONSE_INVALID'});
});
test('membership, role, ownership, exclusion and app type changes reject the entire observation', async () => {
  for (const field of [{owner_steamids: [account]}, {exclude_reason: 3}, {app_type: 4}, {appid: 2}])
    await assert.rejects(() => familyLibrary('token', account, sequence([group(), list([app(1)]), list([{...app(1), ...field}]), group()])), {code: 'FAMILY_LIST_CHANGED'});
  for (const change of [g => g.family_groupid = '124', g => g.family_group.members[1].role = 1,
    g => g.family_group.members.pop()]) {
    const after = group(); change(after);
    await assert.rejects(() => familyLibrary('token', account, sequence([group(), list([app()]), list([app()]), after])), {code: 'FAMILY_LIST_CHANGED'});
  }
});
test('truncation and malformed eligibility never become trusted empty or partial unions', async () => {
  for (const marker of [{has_more: true}, {truncated: true}, {next_cursor: '1'}, {next_page_token: 'next'}])
    await assert.rejects(() => familyLibrary('token', account, sequence([group(), {...list([]), ...marker}])), {code: 'FAMILY_LIST_TRUNCATED'});
  await assert.rejects(() => familyLibrary('token', account, sequence([group(), list(Array(MAX_APPS).fill(app()))])), {code: 'FAMILY_LIST_TRUNCATED'});
  for (const value of [{exclude_reason: undefined}, {exclude_reason: -1}, {app_type: 'game'}, {appid: 0}, {name: null}])
    await assert.rejects(() => familyLibrary('token', account, sequence([group(), list([{...app(), ...value}])])), {code: 'FAMILY_RESPONSE_INVALID'});
  await assert.rejects(() => familyLibrary('token', account, sequence([group(), list([app(), app()])])), {code: 'FAMILY_RESPONSE_INVALID'});
});
test('family networking failures expose safe codes and explicit disable performs no family requests', async () => {
  const accountId = Number(BigInt(account) - 76561197960265728n);
  const seen = [];
  const fetcher = async url => {seen.push(url); return {status: 200, headers: {get: () => null}, json: async () => ({response:
    url.includes('GetAllClientLogonInfo') ? {sessions: [{machine_name: 'desktop', client_instanceid: '1'}]} :
      {client_info: {machine_name: 'desktop', local_users: [accountId]}, apps: []}})};};
  const result = await collectWebSources('private-token', {machine: 'desktop', use_api: false, use_family: false}, account, fetcher);
  assert.equal(result.family, null);
  assert.equal(seen.some(url => url.includes('IFamilyGroupsService')), false);
  await assert.rejects(() => familyLibrary('private-token', account, async () => {throw Error('private-token');}, {sleep: async () => {}}),
    e => e.code === 'NETWORK_UNAVAILABLE' && !e.message.includes('private-token'));
});
test('family retry cooldown and exhausted total deadline stop without another request', async () => {
  let calls = 0;
  await assert.rejects(() => familyLibrary('token', account, async () => {
    calls++; return {status: 429, headers: {get: name => name === 'retry-after' ? '120' : null},
      body: {cancel: async () => {}}};
  }), {code: 'HTTP_429'});
  assert.equal(calls, 1);
  calls = 0;
  await assert.rejects(() => familyLibrary('token', account, async () => {calls++;}, {deadline: Date.now() - 1}),
    {code: 'SOURCE_DEADLINE_EXCEEDED'});
  assert.equal(calls, 0);
});
