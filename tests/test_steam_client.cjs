'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const {EventEmitter} = require('node:events');
const code = fs.readFileSync(path.join(__dirname, '../tools/steam_client_collect.cjs'), 'utf8');

async function run(mode, request = {}) {
  const events = [], options = [], loginOptions = [], timers = [];
  const process = new EventEmitter();
  process.stdin = new EventEmitter();
  process.stdin.setEncoding = () => {};
  process.stdout = {write: line => events.push(JSON.parse(line))};
  process.exit = () => {};
  class User extends EventEmitter {
    constructor(opts) { super(); options.push(opts); this.steamID = {getSteamID64: () => '76561198000000001'}; }
    logOn() {
      queueMicrotask(() => {
        if (mode === 'cm-stalled') return;
        if (mode === 'auth-error') { this.emit('error', {eresult: 5, message: 'secret-refresh-token'}); return; }
        this.emit('loggedOn');
        if (mode !== 'web-stalled') this.emit('webSession', '', ['steamLoginSecure=76561198000000001%7C%7Cprivate-access']);
        if (mode !== 'licenses-stalled') this.emit('ownershipCached');
      });
    }
    logOff() {}
    getOwnedApps() { return [10]; }
    async getProductInfo() { return {apps: {10: {appinfo: {common: {name: 'Game', type: 'Game'}}}}}; }
    _send(header, bytes, callback) {
      if (mode === 'unsupported') throw Error('unsupported protocol');
      callback(Buffer.from('response'), {proto: {eresult: 1}});
    }
  }
  class LoginSession extends EventEmitter {
    constructor(platform, opts) {
      super(); loginOptions.push(opts);
      this.steamID = {getSteamID64: () => '76561198000000001'};
      this.refreshToken = 'secret-refresh-token';
    }
    async startWithQR() { queueMicrotask(() => this.emit('authenticated')); return {qrChallengeUrl: 'qr'}; }
    cancelLoginAttempt() {}
  }
  const schema = {
    CPlayer_GetLastPlayedTimes_Request: {encode: () => ({finish: () => Buffer.alloc(0)})},
    CPlayer_GetLastPlayedTimes_Response: {
      decode: () => { if (mode === 'bad-protobuf') throw Error('bad wire'); return {}; },
      toObject: () => ({games: [{appid: 10, playtime_forever: 5}]}),
    },
  };
  const dependencies = {'./steam_licenses.cjs': {licenseEvidence: () => ({byApp: new Map(), complete: true})},
    './steam_web_sources.cjs': {collectWebSources: async () => ({client: {state: 'complete', records: []}, api: null})},
    './steam_playtime.cjs': require('../tools/steam_playtime.cjs'), 'steam-user': User,
    'steam-session': {LoginSession, EAuthTokenPlatformType: {SteamClient: 1}},
    'qrcode-terminal': {generate: (url, opts, callback) => callback('qr')},
    crypto: require('node:crypto'), 'steam-user/protobufs/generated/_load.js': schema,
    'steam-user/enums/EMsg.js': {ServiceMethodCallFromClient: 151}};
  vm.runInNewContext(code, {process, Buffer, require: name => dependencies[name],
    setTimeout: (callback, ms) => {
      const timer = {callback, ms, active: true, unref() {}}; timers.push(timer); return timer;
    }, clearTimeout: timer => { timer.active = false; }});
  process.stdin.emit('data', JSON.stringify({refresh_token: 'secret-refresh-token', steam_id: '76561198000000001', ...request}));
  process.stdin.emit('end');
  await new Promise(resolve => setImmediate(resolve));
  return {events, options, loginOptions, timers, async fireTimeout(ms) {
    for (const timer of timers.filter(t => t.active && t.ms === ms)) { timer.active = false; timer.callback(); }
    await new Promise(resolve => setImmediate(resolve));
  }};
}

test('unavailable experimental playtime protocol still returns license membership', async () => {
  for (const mode of ['unsupported', 'bad-protobuf']) {
    const {events, options} = await run(mode);
    const result = events.find(e => e.event === 'result');
    assert.equal(result.license_status, 'ok');
    assert.equal(result.licenses[0].appid, 10);
    assert.equal(result.playtime_status, 'failed');
    assert.equal(result.playtimes.length, 0);
    assert.equal(Object.hasOwn(result, 'access_token'), false);
    assert.equal(options[0].dataDirectory, null);
    assert.equal(options[0].renewRefreshTokens, false);
  }
});

test('client playtime preserves missing fields as null', async () => {
  const {events} = await run('ok');
  const result = events.find(e => e.event === 'result');
  assert.equal(result.playtime_status, 'ok');
  assert.equal(result.playtimes[0].playtime_forever, 5);
  assert.equal(result.playtimes[0].playtime_2weeks, null);
});

test('authentication errors expose only an error code', async () => {
  const {events} = await run('auth-error');
  assert.deepEqual(events.filter(e => e.event === 'error'), [{event: 'error', code: 'CM_UNAVAILABLE', eresult: 5}]);
  assert.equal(JSON.stringify(events).includes('secret-refresh-token'), false);
});

test('configured proxy reaches CM and QR authentication without appearing in progress', async () => {
  const proxy = 'http://private-user:private-password@localhost:7890';
  for (const login of [false, true]) {
    const result = await run('ok', {https_proxy: proxy, login});
    assert.equal(result.options[0].httpProxy, proxy);
    if (login) assert.equal(result.loginOptions[0].httpProxy, proxy);
    assert.equal(JSON.stringify(result.events).includes(proxy), false);
  }
  assert.equal((await run('ok')).options[0].httpProxy, undefined);
});

test('stalled CM connection reports its stage then a bounded connection timeout', async () => {
  const result = await run('cm-stalled');
  assert.deepEqual(result.events, [{event: 'progress', stage: 'connecting_cm'}]);
  await result.fireTimeout(60000);
  assert.equal(result.events.at(-1).code, 'CM_CONNECT_TIMEOUT');
  assert.equal(result.events.some(e => e.event === 'result'), false);
});

test('connection timer is cancelled after authentication and missing web session is distinguished', async () => {
  const result = await run('web-stalled');
  await result.fireTimeout(60000);
  assert.equal(result.events.some(e => e.event === 'error'), false);
  await result.fireTimeout(110000);
  assert.equal(result.events.at(-1).code, 'WEB_SESSION_TIMEOUT');
});

test('stalled licenses do not block other sources past the collection deadline', async () => {
  const result = await run('licenses-stalled');
  await result.fireTimeout(110000);
  assert.equal(result.events.at(-1).event, 'result');
  assert.equal(result.events.at(-1).license_status, 'failed');
});
