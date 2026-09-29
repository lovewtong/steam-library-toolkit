'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {clientLibrary, ownedGames, collectWebSources} = require('../tools/steam_web_sources.cjs');
const {decodePlaytime} = require('../tools/steam_playtime.cjs');
const schema = require('steam-user/protobufs/generated/_load.js');
const account = '76561198000000001';
const accountId = Number(BigInt(account) - 76561197960265728n);
const session = {sessions: [{machine_name: 'desktop', client_instanceid: '123'}]};
const list = ids => ({client_info: {machine_name: 'desktop', local_users: [accountId]},
  apps: ids.map(appid => ({appid, app: 'Game', app_type: 'game'}))});
function fetchSequence(items) {
  return async () => {
    const value = items.shift();
    if (value instanceof Error) throw value;
    assert.notEqual(value, undefined, 'unexpected extra request');
    return {status: 200, headers: {get: () => '1'}, json: async () => ({response: value})};
  };
}

test('API accepts shared absent/null/zero/positive time cases without losing other apps', async () => {
  const cases = require('./fixtures/api-time-values.json');
  for (const field of cases.fields) for (const example of cases.valid) {
    const row = {appid: 1, ...(example.present ? {[field]: example.value} : {})};
    const result = await ownedGames('fixture-key', account, true, fetchSequence([
      {game_count: 2, games: [row, {appid: 2, playtime_forever: 7}]}]));
    assert.equal(result.state, 'complete');
    assert.deepEqual(result.records, [{...row, name: ''}, {appid: 2, name: '', playtime_forever: 7}]);
  }
});

test('API rejects shared invalid time values rather than converting them to unknown', async () => {
  const cases = require('./fixtures/api-time-values.json');
  for (const field of cases.fields) for (const value of cases.invalid) {
    await assert.rejects(() => ownedGames('fixture-key', account, true, fetchSequence([
      {game_count: 1, games: [{appid: 1, [field]: value}]}])), {code: 'RESPONSE_INVALID'});
  }
});
test('only stable lists on the same authenticated desktop become complete', async () => {
  const r = await clientLibrary('secret', account, 'desktop', fetchSequence([session, list([10, 20]), list([20, 10]), session]));
  assert.equal(r.state, 'complete');
  assert.equal(r.completeness.semantic_completeness_proven, false);
  assert.equal(r.completeness.verified, true);
});
test('partial, absent, malformed and interrupted responses never become authoritative', async () => {
  const cases = [
    [session, list([10, 20]), list([10])],
    [session, {client_info: {machine_name: 'desktop', local_users: [accountId]}}],
    [session, list([10]), Error('secret URL')],
    [session, list([10, 10])],
    [session, list([10]), list([10]), {sessions: [{machine_name: 'desktop', client_instanceid: '456'}]}],
  ];
  for (const values of cases) await assert.rejects(() => clientLibrary('secret', account, 'desktop', fetchSequence(values)));
});
test('wrong account, wrong machine and ambiguous sessions fail closed', async () => {
  const wrong = list([10]); wrong.client_info.local_users = [999];
  await assert.rejects(() => clientLibrary('secret', account, 'desktop', fetchSequence([session, wrong])), {code: 'ACCOUNT_MISMATCH'});
  for (const sessions of [[], [{machine_name: 'elsewhere'}], [...session.sessions, ...session.sessions]])
    await assert.rejects(() => clientLibrary('secret', account, 'desktop', fetchSequence([{sessions}])));
});
test('explicit empty list and repeated matching confirmation are accepted', async () => {
  const r = await clientLibrary('secret', account, 'desktop', fetchSequence([session, list([]), list([]), session]));
  assert.deepEqual(r.records, []);
});
test('real protobuf decoding distinguishes absent, zero and positive time', () => {
  const type = schema.CPlayer_GetLastPlayedTimes_Response;
  const bytes = type.encode({games: [{appid: 10}, {appid: 20, playtime_forever: 0}, {appid: 30, playtime_forever: 3}]}).finish();
  assert.deepEqual(decodePlaytime(bytes, type).map(g => g.playtime_forever), [null, 0, 3]);
});
test('Web API count mismatch is partial and values are whitelisted', async () => {
  await assert.rejects(() => ownedGames('secret', account, true, fetchSequence([{game_count: 3, games: []}])), {state: 'partial'});
  const r = await ownedGames('secret', account, true, fetchSequence([{game_count: 1, games: [{appid: 10, name: 'Game', playtime_forever: 0, token: 'leak'}]}]));
  assert.equal(r.records[0].playtime_forever, 0);
  assert.equal(JSON.stringify(r).includes('leak'), false);
});
test('network errors expose stable codes without exception text or tokens', async () => {
  const r = await collectWebSources('private-token', {machine: 'desktop', use_api: false}, account, async () => {throw Error('private-token');});
  assert.equal(r.client.state, 'unavailable');
  assert.equal(JSON.stringify(r).includes('private-token'), false);
});

test('license evidence distinguishes overlapping own/shared/free packages', () => {
  const {licenseEvidence} = require('../tools/steam_licenses.cjs');
  const user = {picsCache: {packages: {1: {packageinfo: {appids: [10]}}, 2: {packageinfo: {appids: [10, 20]}}}},
    getOwnedPackages: f => f.excludeShared || f.excludeFree || f.excludeExpiring ? [1] : [1, 2]};
  const evidence = licenseEvidence(user);
  const app = evidence.byApp.get(10);
  assert.equal(app.own, true); assert.equal(app.shared, true); assert.equal(app.free, true);
  assert.deepEqual(app.package_ids, [1, 2]);
  delete user.picsCache.packages[2];
  assert.equal(licenseEvidence(user).complete, false);
});

test('429 retries honor Retry-After and stop at a bounded count', async () => {
  let calls = 0;
  const waits = [];
  const fetcher = async () => ++calls < 3
    ? {status: 429, headers: {get: name => name === 'retry-after' ? '2' : null}}
    : {status: 200, headers: {get: () => null}, json: async () => ({response: {game_count: 0, games: []}})};
  const result = await ownedGames('canary-private-token', account, true, fetcher, {sleep: async ms => waits.push(ms)});
  assert.equal(result.state, 'complete');
  assert.equal(calls, 3);
  assert.deepEqual(waits, [2000, 2000]);
});

test('auth failures are not retried and transient failures are exhausted safely', async () => {
  let calls = 0;
  await assert.rejects(() => ownedGames('canary-private-token', account, true, async () => {
    calls++; return {status: 403, headers: {get: () => null}};
  }), {code: 'HTTP_403'});
  assert.equal(calls, 1);
  calls = 0;
  await assert.rejects(() => ownedGames('canary-private-token', account, true, async () => {
    calls++; throw Error('canary-private-token');
  }, {sleep: async () => {}}), e => e.code === 'NETWORK_UNAVAILABLE' && e.attempts === 3 && !e.message.includes('canary'));
  assert.equal(calls, 3);
});

test('protocol shape recorder discards all response values and unknown keys', () => {
  const {shape} = require('../tools/steam_protocol_shapes.cjs');
  const value = shape({apps: [{appid: 123456789, app: 'private-name-canary', app_type: 1,
    access_token: 'private-token-canary', 'private-key-canary': 'private-value-canary'}]});
  const encoded = JSON.stringify(value);
  assert.equal(encoded.includes('canary'), false);
  assert.equal(encoded.includes('123456789'), false);
  assert.equal(value.properties.apps.item_shapes[0].properties.appid.type, 'integer');
  assert.equal(value.properties.apps.item_shapes[0].omitted_fields, 2);
});

test('live field-shape fixture records actual client and API presence without scalar values', () => {
  const fixture = require('./fixtures/protocol-shapes.windows.json');
  assert.equal(fixture.origin, 'live_windows_local_session');
  assert.equal(fixture.scope, 'allowlisted_field_types_only');
  const lists = fixture.observations.filter(o => o.method === 'GetClientAppList');
  assert.equal(lists.length, 2);
  assert.deepEqual(lists[0].response, lists[1].response);
  for (const observation of lists) {
    assert.equal(observation.response.properties.apps.type, 'array');
    assert.equal(observation.response.properties.client_info.properties.local_users.type, 'array');
  }
  const api = fixture.observations.find(o => o.method === 'GetOwnedGames');
  assert.equal(api.response.properties.game_count.type, 'integer');
  assert.equal(api.response.properties.games.type, 'array');
});

test('shape collection is explicit and does not change source reconciliation', async () => {
  const fetcher = async url => {
    const response = url.includes('GetAllClientLogonInfo') ? session :
      url.includes('GetClientAppList') ? list([10]) : {game_count: 0, games: []};
    return {status: 200, headers: {get: () => null}, json: async () => ({response})};
  };
  const regular = await collectWebSources('private-token-canary', {machine: 'desktop'}, account, fetcher);
  assert.equal(Object.hasOwn(regular, 'protocol_shapes'), false);
  const captured = await collectWebSources('private-token-canary', {machine: 'desktop', capture_protocol_shapes: true}, account, fetcher);
  assert.deepEqual(captured.client, regular.client);
  assert.deepEqual(captured.api, regular.api);
  assert.equal(captured.protocol_shapes.observations.length, 5);
  assert.equal(JSON.stringify(captured.protocol_shapes).includes('private-token-canary'), false);
});
