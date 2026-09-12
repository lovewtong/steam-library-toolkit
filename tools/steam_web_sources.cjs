'use strict';
// Access tokens remain in this process. Only whitelisted response fields leave it.
class SourceError extends Error {
  constructor(code, state = 'unavailable') { super(code); this.code = code; this.state = state; }
}
const failed = e => ({state: e instanceof SourceError ? e.state : 'unavailable',
  error_code: e instanceof SourceError ? e.code : 'NETWORK_UNAVAILABLE', records: []});
async function call(service, method, token, params, fetcher = fetch, policy = {}) {
  const sleep = policy.sleep || (ms => new Promise(resolve => setTimeout(resolve, ms)));
  const deadline = Date.now() + 35000;
  let response, error;
  for (let attempt = 1; attempt <= 3; attempt++) {
    if (policy.stats) policy.stats.attempts++;
    let retryAfter = 0;
    try {
      response = await fetcher(`https://api.steampowered.com/${service}/${method}/v1/?` +
        new URLSearchParams({access_token: token, ...params}),
        {redirect: 'error', signal: AbortSignal.timeout(Math.max(1, deadline - Date.now()))});
      if (response.status === 200) break;
      error = new SourceError(`HTTP_${response.status}`);
      if (![408, 429, 500, 502, 503, 504].includes(response.status)) throw error;
      const header = response.headers.get('retry-after');
      if (header) retryAfter = /^\d+$/.test(header) ? Number(header) * 1000 : Math.max(0, Date.parse(header) - Date.now()) || 0;
      await response.body?.cancel();
    } catch (e) {
      if (e instanceof SourceError) throw e;
      error = new SourceError('NETWORK_UNAVAILABLE');
    }
    error.attempts = attempt;
    const delay = Math.max(retryAfter, 250 * 2 ** (attempt - 1) * (0.75 + Math.random() * 0.5));
    if (attempt === 3 || delay >= deadline - Date.now()) throw error;
    await sleep(delay);
  }
  if (!['1', null].includes(response.headers.get('x-eresult'))) throw new SourceError('STEAM_REQUEST_FAILED');
  let body;
  try { body = (await response.json()).response; } catch (_) { throw new SourceError('RESPONSE_INVALID', 'invalid'); }
  if (!body || typeof body !== 'object' || Array.isArray(body)) throw new SourceError('RESPONSE_INVALID', 'invalid');
  if (policy.shapes) policy.shapes.push({method, response: require('./steam_protocol_shapes.cjs').shape(body)});
  return body;
}
function records(raw, client = false) {
  if (!Array.isArray(raw)) throw new SourceError('RESPONSE_INVALID', 'invalid');
  const ids = new Set();
  return raw.map(g => {
    if (!g || !Number.isInteger(g.appid) || g.appid <= 0 || g.appid > 0xffffffff || ids.has(g.appid))
      throw new SourceError('RESPONSE_INVALID', 'invalid');
    ids.add(g.appid);
    const name = client ? g.app : g.name;
    if (name != null && typeof name !== 'string') throw new SourceError('RESPONSE_INVALID', 'invalid');
    const row = {appid: g.appid, name: name || ''};
    if (client) row.app_type = g.app_type ?? 'unknown';
    else for (const field of ['playtime_forever', 'playtime_2weeks', 'rtime_last_played']) {
      if (Object.hasOwn(g, field)) {
        if (!Number.isInteger(g[field]) || g[field] < 0 || g[field] > 0xffffffff)
          throw new SourceError('RESPONSE_INVALID', 'invalid');
        row[field] = g[field];
      }
    }
    return row;
  });
}
async function clientLibrary(token, account, machine, fetcher, policy) {
  const getSessions = async () => {
    const body = await call('IClientCommService', 'GetAllClientLogonInfo', token, {}, fetcher, policy);
    if (!Array.isArray(body.sessions)) throw new SourceError('STEAM_CLIENT_NOT_RUNNING');
    const found = body.sessions.filter(s => typeof s?.machine_name === 'string' &&
      s.machine_name.toLowerCase() === machine.toLowerCase());
    if (found.length !== 1 || !/^\d+$/.test(String(found[0].client_instanceid)))
      throw new SourceError('CLIENT_SESSION_AMBIGUOUS');
    return found[0];
  };
  const session = await getSessions();
  const read = async () => {
    const body = await call('IClientCommService', 'GetClientAppList', token,
      {client_instanceid: session.client_instanceid, fields: 'games', include_client_info: 'true', language: 'schinese'}, fetcher, policy);
    const info = body.client_info;
    if (!info || typeof info.machine_name !== 'string' || info.machine_name.toLowerCase() !== machine.toLowerCase())
      throw new SourceError('CLIENT_RESPONSE_UNCONFIRMED', 'invalid');
    const accountId = Number(BigInt(account) - 76561197960265728n);
    if (!Array.isArray(info.local_users) || !info.local_users.includes(accountId))
      throw new SourceError('ACCOUNT_MISMATCH', 'account_mismatch');
    // An absent list is not proof of an empty account, even when client_info exists.
    if (!Object.hasOwn(body, 'apps')) throw new SourceError('CLIENT_LIST_UNCONFIRMED', 'partial');
    return records(body.apps, true);
  };
  const first = await read();
  const second = await read();
  const fingerprint = rows => rows.map(r => r.appid).sort((a, b) => a - b).join(',');
  if (fingerprint(first) !== fingerprint(second)) throw new SourceError('CLIENT_LIST_CHANGED', 'partial');
  if (String((await getSessions()).client_instanceid) !== String(session.client_instanceid))
    throw new SourceError('CLIENT_SESSION_CHANGED', 'partial');
  return {state: 'complete', records: second, completeness: {verified: true,
    method: 'two_consistent_rpc_responses', reads: 2, account_checked: true, session_checked: true,
    protocol_completion_marker: false, semantic_completeness_proven: false}};
}
async function ownedGames(token, account, expanded, fetcher, policy) {
  const body = await call('IPlayerService', 'GetOwnedGames', token, {steamid: account, include_appinfo: 'true',
    include_played_free_games: String(expanded), include_free_sub: String(expanded), skip_unvetted_apps: String(!expanded)}, fetcher, policy);
  if (!Object.hasOwn(body, 'games') && !Object.hasOwn(body, 'game_count')) throw new SourceError('WEB_API_PRIVATE', 'invalid');
  const games = records(body.games ?? []);
  if (Object.hasOwn(body, 'game_count') && body.game_count !== games.length) throw new SourceError('WEB_API_COUNT_MISMATCH', 'partial');
  return {state: 'complete', records: games};
}
async function collectWebSources(token, request, account, fetcher) {
  let proxy;
  if (!fetcher && request.https_proxy) {
    const {fetch: proxyFetch, ProxyAgent} = require('undici');
    try { proxy = new ProxyAgent(request.https_proxy); }
    catch (_) { throw new SourceError('PROXY_CONFIGURATION_INVALID'); }
    fetcher = (url, options) => proxyFetch(url, {...options, dispatcher: proxy});
  }
  try {
    const shapes = request.capture_protocol_shapes ? [] : null;
    const safe = async fn => { const policy = {stats: {attempts: 0}, shapes}; let result; try { result = await fn(policy); } catch (e) { result = failed(e); } return {...result, attempts: policy.stats.attempts}; };
    const [client, api] = await Promise.all([
      safe(policy => clientLibrary(token, account, request.machine, fetcher, policy)),
      request.use_api === false ? Promise.resolve(null) : safe(policy => ownedGames(token, account, request.expanded !== false, fetcher, policy)),
    ]);
    if (client.error_code === 'ACCOUNT_MISMATCH') throw new SourceError('ACCOUNT_MISMATCH', 'account_mismatch');
    return {client, api, ...(shapes ? {protocol_shapes: {schema_version: 1,
      scope: 'allowlisted_field_types_only', observations: shapes}} : {})};
  } finally { if (proxy) await proxy.close(); }
}
module.exports = {SourceError, clientLibrary, ownedGames, collectWebSources};
