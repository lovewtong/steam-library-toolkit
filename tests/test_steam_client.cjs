'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const {EventEmitter} = require('node:events');
const code = fs.readFileSync(path.join(__dirname, '../tools/steam_client_collect.cjs'), 'utf8');

async function run(mode) {
  const events = [], options = [];
  const process = new EventEmitter();
  process.stdin = new EventEmitter();
  process.stdin.setEncoding = () => {};
  process.stdout = {write: line => events.push(JSON.parse(line))};
  process.exit = () => {};
  class User extends EventEmitter {
    constructor(opts) { super(); options.push(opts); this.steamID = {getSteamID64: () => '76561198000000001'}; }
    logOn() {
      queueMicrotask(() => {
        if (mode === 'auth-error') { this.emit('error', {eresult: 5, message: 'secret-refresh-token'}); return; }
        this.emit('loggedOn');
        this.emit('webSession', '', ['steamLoginSecure=76561198000000001%7C%7Cprivate-access']);
        this.emit('ownershipCached');
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
  const schema = {
    CPlayer_GetLastPlayedTimes_Request: {encode: () => ({finish: () => Buffer.alloc(0)})},
    CPlayer_GetLastPlayedTimes_Response: {
      decode: () => { if (mode === 'bad-protobuf') throw Error('bad wire'); return {}; },
      toObject: () => ({games: [{appid: 10, playtime_forever: 5}]}),
    },
  };
  const dependencies = {'steam-user': User, 'steam-session': {}, 'qrcode-terminal': {},
    crypto: require('node:crypto'), 'steam-user/protobufs/generated/_load.js': schema,
    'steam-user/enums/EMsg.js': {ServiceMethodCallFromClient: 151}};
  vm.runInNewContext(code, {process, Buffer, require: name => dependencies[name],
    setTimeout: () => ({unref() {}}), clearTimeout() {}});
  process.stdin.emit('data', JSON.stringify({refresh_token: 'secret-refresh-token', steam_id: '76561198000000001'}));
  process.stdin.emit('end');
  await new Promise(resolve => setImmediate(resolve));
  return {events, options};
}

test('unavailable experimental playtime protocol still returns license membership', async () => {
  for (const mode of ['unsupported', 'bad-protobuf']) {
    const {events, options} = await run(mode);
    const result = events.find(e => e.event === 'result');
    assert.equal(result.license_status, 'ok');
    assert.equal(result.licenses[0].appid, 10);
    assert.equal(result.playtime_status, 'failed');
    assert.equal(result.playtimes.length, 0);
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
  assert.deepEqual(events, [{event: 'error', code: 5}]);
  assert.equal(JSON.stringify(events).includes('secret-refresh-token'), false);
});
