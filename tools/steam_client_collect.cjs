// Private NDJSON bridge. Never log credentials, cookies, or raw exceptions.
'use strict';
const SteamUser = require('steam-user');
const {LoginSession, EAuthTokenPlatformType} = require('steam-session');
const qr = require('qrcode-terminal');
const crypto = require('crypto');

const emit = event => process.stdout.write(JSON.stringify(event) + '\n');
let user, loginSession, done = false;
function fail(error) {
  if (done) return;
  done = true;
  emit({event: 'error', code: Number.isInteger(error?.eresult) ? error.eresult : 'unavailable'});
  user?.logOff();
  loginSession?.cancelLoginAttempt();
  setTimeout(() => process.exit(1), 100);
}
process.on('uncaughtException', fail);
process.on('unhandledRejection', fail);
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', async () => {
  try {
    const request = JSON.parse(input);
    input = '';
    if (request.login) {
      loginSession = new LoginSession(EAuthTokenPlatformType.SteamClient);
      loginSession.loginTimeout = 120000;
      const ready = new Promise((resolve, reject) => {
        loginSession.once('authenticated', resolve);
        loginSession.once('error', reject);
        loginSession.once('timeout', () => reject(new Error('timeout')));
      });
      const result = await loginSession.startWithQR();
      qr.generate(result.qrChallengeUrl, {small: true}, text => emit({event: 'qr', qr: text}));
      await ready;
      const identity = loginSession.steamID.getSteamID64();
      if (request.steam_id && identity !== request.steam_id) throw new Error('account mismatch');
      request.refresh_token = loginSession.refreshToken;
      request.steam_id = identity;
      emit({event: 'credentials', steam_id: identity, refresh_token: request.refresh_token});
      loginSession.cancelLoginAttempt();
    }
    user = new SteamUser({dataDirectory: null, autoRelogin: false, enablePicsCache: true,
      picsCacheAll: false, saveAppTickets: false, renewRefreshTokens: false, webCompatibilityMode: true});
    let access, licenses, playtimes, playtimeStatus = 'pending';
    const finish = () => {
      if (done || !access || licenses === undefined || playtimes === undefined) return;
      done = true;
      emit({event: 'result', steam_id: user.steamID.getSteamID64(), access_token: access,
        licenses: licenses || [], license_status: licenses ? 'ok' : 'failed',
        playtimes, playtime_status: playtimeStatus});
      user.logOff();
      setTimeout(() => process.exit(0), 100);
    };
    user.on('error', fail);
    user.once('loggedOn', () => {
      if (request.steam_id && user.steamID.getSteamID64() !== request.steam_id) return fail({});
      emit({event: 'progress', stage: '已认证，正在读取账号许可与游玩记录'});
      const timer = setTimeout(() => {
        playtimes = []; playtimeStatus = 'failed'; finish();
      }, 15000);
      // Client protocol adapter: experimental, best effort, never blocks membership.
      try {
        // steam-user does not register this RPC in _sendUnified; encode/decode explicitly.
        const schema = require('steam-user/protobufs/generated/_load.js');
        const EMsg = require('steam-user/enums/EMsg.js');
        user._send({msg: EMsg.ServiceMethodCallFromClient,
          proto: {target_job_name: 'Player.ClientGetLastPlayedTimes#1'}},
        schema.CPlayer_GetLastPlayedTimes_Request.encode({min_last_played: 0}).finish(), (raw, header) => {
          clearTimeout(timer);
          if (playtimes !== undefined) return;
          try {
            const type = schema.CPlayer_GetLastPlayedTimes_Response;
            const body = type.toObject(type.decode(Buffer.isBuffer(raw) ? raw : raw.toBuffer()), {longs: String});
            playtimeStatus = header.proto?.eresult === 1 ? 'ok' : 'failed';
            playtimes = playtimeStatus === 'ok' ? (body.games || []).map(g => ({appid: g.appid,
              playtime_forever: g.playtime_forever ?? null, playtime_2weeks: g.playtime_2weeks ?? null,
              rtime_last_played: g.last_playtime ?? null})) : [];
          } catch (_) { playtimes = []; playtimeStatus = 'failed'; }
          finish();
        });
      } catch (_) {
        clearTimeout(timer); playtimes = []; playtimeStatus = 'failed'; finish();
      }
    });
    user.once('webSession', (sessionId, cookies) => {
      const cookie = cookies.find(c => c.startsWith('steamLoginSecure='));
      if (!cookie) return fail({});
      access = decodeURIComponent(cookie.split(';')[0].slice('steamLoginSecure='.length)).split('||')[1];
      finish();
    });
    user.once('ownershipCached', async () => {
      try {
        const own = new Set(user.getOwnedApps({excludeShared: true}));
        const ids = user.getOwnedApps({excludeShared: false}).filter(id => id > 0);
        const info = await user.getProductInfo(ids, [], true);
        licenses = ids.map(appid => {
          const common = info.apps[appid]?.appinfo?.common || {};
          return {appid, name: common.name || `Unknown App ${appid}`,
            app_type: (common.type || 'unknown').toLowerCase(), shared_only: !own.has(appid)};
        });
        finish();
      } catch (_) { licenses = null; finish(); }
    });
    // A distinct session ID avoids replacing the desktop session on the same IP.
    user.logOn({refreshToken: request.refresh_token, logonID: crypto.randomBytes(4).readUInt32LE(0),
      machineName: 'Steam Library Toolkit'});
    setTimeout(() => {
      licenses ??= null; playtimes ??= []; playtimeStatus = playtimeStatus === 'pending' ? 'failed' : playtimeStatus;
      if (access) finish(); else fail({});
    }, 110000).unref();
  } catch (error) { fail(error); }
});
