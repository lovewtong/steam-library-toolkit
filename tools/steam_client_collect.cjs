// Private NDJSON bridge. Never log credentials, cookies, or raw exceptions.
'use strict';
const SteamUser = require('steam-user');
const {LoginSession, EAuthTokenPlatformType} = require('steam-session');
const qr = require('qrcode-terminal');
const crypto = require('crypto');
const {collectWebSources} = require('./steam_web_sources.cjs');
const {decodePlaytime} = require('./steam_playtime.cjs');
const {licenseEvidence} = require('./steam_licenses.cjs');

const emit = event => process.stdout.write(JSON.stringify(event) + '\n');
let user, loginSession, done = false;
function fail(error) {
  if (done) return;
  done = true;
  const safeCodes = ['ACCOUNT_MISMATCH', 'CM_CONNECT_TIMEOUT', 'WEB_SESSION_TIMEOUT'];
  emit({event: 'error', code: safeCodes.includes(error?.code) ? error.code : 'CM_UNAVAILABLE',
    eresult: Number.isInteger(error?.eresult) ? error.eresult : null});
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
    const connectionOptions = request.https_proxy ? {httpProxy: request.https_proxy} : {};
    if (request.login) {
      emit({event: 'progress', stage: 'qr_login'});
      loginSession = new LoginSession(EAuthTokenPlatformType.SteamClient, connectionOptions);
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
      if (request.steam_id && identity !== request.steam_id) throw {code: 'ACCOUNT_MISMATCH'};
      request.refresh_token = loginSession.refreshToken;
      request.steam_id = identity;
      emit({event: 'credentials', steam_id: identity, refresh_token: request.refresh_token});
      loginSession.cancelLoginAttempt();
    }
    user = new SteamUser({dataDirectory: null, autoRelogin: false, enablePicsCache: true,
      picsCacheAll: false, saveAppTickets: false, renewRefreshTokens: false, webCompatibilityMode: true,
      ...connectionOptions});
    const connectTimer = setTimeout(() => fail({code: 'CM_CONNECT_TIMEOUT'}), 60000);
    let access, licenses, playtimes, playtimeStatus = 'pending', licenseStatus = 'failed';
    let finishing = false;
    const finish = async () => {
      if (done || finishing || !access || licenses === undefined || playtimes === undefined) return;
      finishing = true;
      try {
        emit({event: 'progress', stage: 'reading_web_sources'});
        const web = await collectWebSources(access, request, user.steamID.getSteamID64());
        if (done) return;
        done = true;
        access = null;
        emit({event: 'result', steam_id: user.steamID.getSteamID64(), ...web,
          licenses: licenses || [], license_status: licenses ? licenseStatus : 'failed',
          playtimes, playtime_status: playtimeStatus,
          overview_probe: {state: 'protocol_incompatible', error_code: 'APP_OVERVIEW_NOT_EXPOSED_BY_CLIENTCOMM'}});
        user.logOff();
        setTimeout(() => process.exit(0), 100);
      } catch (error) { fail(error); }
    };
    user.on('error', fail);
    user.once('loggedOn', () => {
      clearTimeout(connectTimer);
      if (request.steam_id && user.steamID.getSteamID64() !== request.steam_id) return fail({code: 'ACCOUNT_MISMATCH'});
      emit({event: 'progress', stage: 'authenticated'});
      setTimeout(() => {
        if (done) return;
        licenses ??= null; playtimes ??= [];
        playtimeStatus = playtimeStatus === 'pending' ? 'failed' : playtimeStatus;
        if (access) finish(); else fail({code: 'WEB_SESSION_TIMEOUT'});
      }, 110000).unref();
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
            playtimeStatus = header.proto?.eresult === 1 ? 'ok' : 'failed';
            playtimes = playtimeStatus === 'ok' ? decodePlaytime(raw, type) : [];
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
      emit({event: 'progress', stage: 'web_session_ready'});
      finish();
    });
    user.once('ownershipCached', async () => {
      emit({event: 'progress', stage: 'reading_licenses'});
      try {
        const own = new Set(user.getOwnedApps({excludeShared: true}));
        const nonFree = new Set(user.getOwnedApps({excludeFree: true}));
        const permanent = new Set(user.getOwnedApps({excludeExpiring: true}));
        const evidence = licenseEvidence(user);
        licenseStatus = evidence.complete ? 'ok' : 'partial';
        const ids = user.getOwnedApps({excludeShared: false}).filter(id => id > 0);
        const info = await user.getProductInfo(ids, [], true);
        licenses = ids.map(appid => {
          const common = info.apps[appid]?.appinfo?.common || {};
          return {appid, name: common.name || `Unknown App ${appid}`,
            app_type: common.type || 'unknown', shared_only: !own.has(appid),
            license_evidence: {own: own.has(appid), shared_only: !own.has(appid),
              free_only: evidence.complete ? !nonFree.has(appid) : null,
              expiring_only: evidence.complete ? !permanent.has(appid) : null,
              ...evidence.byApp.get(appid)}};
        });
        finish();
      } catch (_) { licenses = null; finish(); }
    });
    // A distinct session ID avoids replacing the desktop session on the same IP.
    emit({event: 'progress', stage: 'connecting_cm'});
    user.logOn({refreshToken: request.refresh_token, logonID: crypto.randomBytes(4).readUInt32LE(0),
      machineName: 'Steam Library Toolkit'});
  } catch (error) { fail(error); }
});
