/**
 * 通过 Steam 的 LevelDB 直接写入收藏（Steam 必须完全关闭）。
 * 读取 steam_collections_result.json，合并进 LevelDB 中 Steam 使用的 key，
 * 启动 Steam 后应能看到新收藏。
 *
 * 依赖: npm install classic-level
 * 使用: node steam_sync_leveldb.js [--dry-run]
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const SCRIPT_DIR = __dirname;
const CONFIG_PATH = path.join(SCRIPT_DIR, 'config_local.json');
const RESULT_JSON = path.join(SCRIPT_DIR, 'steam_collections_result.json');
const STEAM_LOOPBACK = 'https://steamloopback.host';
const STEAM_NAMESPACE_SUFFIX = '-cloud-storage-namespace';

function loadConfig() {
  if (!fs.existsSync(CONFIG_PATH)) {
    throw new Error('未找到 config_local.json，请配置 steam_id 和 steam_install_path');
  }
  const cfg = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
  const steamId = (cfg.steam_id || process.env.STEAM_ID || '').trim();
  const steamPath = (cfg.steam_install_path || process.env.STEAM_PATH || '').trim();
  if (!steamId) throw new Error('请在 config_local.json 中填写 steam_id');
  if (!steamPath || !fs.existsSync(steamPath)) throw new Error('请正确配置 steam_install_path 且目录存在');
  return { steamId, steamPath };
}

/** 候选 LevelDB 路径（Windows 可能与 Linux 不同，或目录名大小写不同） */
function getLevelDBCandidates(steamPath, steamId) {
  return [
    path.join(steamPath, 'config', 'htmlcache', 'Local Storage', 'leveldb'),
    path.join(steamPath, 'config', 'Htmlcache', 'Local Storage', 'leveldb'),
    path.join(steamPath, 'config', 'HTML Cache', 'Local Storage', 'leveldb'),
    path.join(steamPath, 'userdata', steamId, 'config', 'htmlcache', 'Local Storage', 'leveldb'),
  ];
}

function findLevelDBPath(steamPath, steamId) {
  const candidates = getLevelDBCandidates(steamPath, steamId);
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return candidates[0]; // 默认返回第一个，用于报错提示
}

function loadCollections() {
  if (!fs.existsSync(RESULT_JSON)) {
    throw new Error('未找到 steam_collections_result.json，请先运行 node classify_steam.js');
  }
  const data = JSON.parse(fs.readFileSync(RESULT_JSON, 'utf8'));
  if (typeof data !== 'object' || data === null) throw new Error('steam_collections_result.json 格式应为 分类名 -> [appid]');
  const out = {};
  for (const [name, appids] of Object.entries(data)) {
    if (!Array.isArray(appids)) continue;
    const ids = appids
      .map((a) => (typeof a === 'number' ? a : parseInt(String(a), 10)))
      .filter((n) => Number.isInteger(n) && n > 0);
    if (ids.length) out[String(name).trim() || '未命名'] = [...new Set(ids)].sort((a, b) => a - b);
  }
  return out;
}

function generateUcId() {
  return 'uc-' + crypto.randomBytes(6).toString('hex');
}

function makeSteamEntry(cid, name, addedAppids) {
  const key = 'user-collections.' + cid;
  const value = JSON.stringify({
    id: cid,
    name,
    added: addedAppids,
    removed: [],
  });
  return [
    key,
    {
      key,
      timestamp: Math.floor(Date.now() / 1000),
      value,
      conflictResolutionMethod: 'custom',
      strMethodId: 'union-collections',
      version: '3086',
    },
  ];
}

function mergeCollectionsIntoData(existingData, ourCollections) {
  const entries = Array.isArray(existingData) ? [...existingData] : [];
  for (const [name, appids] of Object.entries(ourCollections)) {
    if (!appids.length) continue;
    const cid = generateUcId();
    entries.push(makeSteamEntry(cid, name, appids));
  }
  return entries;
}

async function main() {
  const dryRun = process.argv.includes('--dry-run');
  const config = loadConfig();
  const collections = loadCollections();
  const dbPath = findLevelDBPath(config.steamPath, config.steamId);

  console.log('Steam 目录:', config.steamPath);
  console.log('LevelDB 路径:', dbPath);
  console.log('Steam 用户 ID (userdata):', config.steamId);
  console.log('将写入收藏数:', Object.keys(collections).length);
  Object.entries(collections).forEach(([name, appids]) => {
    console.log('  -', name + ':', appids.length, '款');
  });

  if (!fs.existsSync(dbPath)) {
    const candidates = getLevelDBCandidates(config.steamPath, config.steamId);
    if (dryRun) {
      console.log('\nLevelDB 目录不存在（已尝试 ' + candidates.length + ' 个候选路径）。实际执行时请确认 Steam 安装路径正确，且曾至少启动过一次 Steam。');
    } else {
      console.error('\nLevelDB 目录不存在。已尝试以下路径：');
      candidates.forEach((p, i) => console.error('  ' + (i + 1) + '. ' + p));
      const configDir = path.join(config.steamPath, 'config');
      if (fs.existsSync(configDir)) {
        try {
          const entries = fs.readdirSync(configDir, { withFileTypes: true });
          const dirs = entries.filter((e) => e.isDirectory()).map((e) => e.name);
          console.error('\n你的 Steam config 目录下现有文件夹: ' + dirs.join(', ') + '。');
          if (!dirs.includes('htmlcache') && !dirs.some((d) => d.toLowerCase() === 'htmlcache')) {
            console.error('未找到 htmlcache，可能是 Steam 版本或安装方式不同。请先启动 Steam 并进入一次「库」再完全退出后重试。');
          }
        } catch (e) {}
      }
      console.error('\n请确认 config_local.json 中 steam_install_path 为实际 Steam 安装目录（例如 C:\\Program Files (x86)\\Steam）。');
      process.exit(1);
    }
  }

  if (dryRun) {
    console.log('\n--dry-run：未打开 LevelDB，未写入。若要实际写入，请先完全关闭 Steam 后运行: node steam_sync_leveldb.js');
    return;
  }

  let ClassicLevel;
  try {
    const pkg = require('classic-level');
    ClassicLevel = pkg.ClassicLevel || pkg;
  } catch (e) {
    console.error('请先安装依赖: npm install classic-level');
    process.exit(1);
  }

  const keyPart1 = STEAM_LOOPBACK;
  const keyPart2 = 'U' + config.steamId + STEAM_NAMESPACE_SUFFIX;

  const db = new ClassicLevel(dbPath, { keyEncoding: 'utf8', valueEncoding: 'utf8' });

  try {
    let found = false;
    for await (const [key, value] of db.iterator()) {
      if (key.includes(keyPart1) && key.includes(keyPart2)) {
        found = true;
        const idx = value.indexOf('[');
        const prefix = idx >= 0 ? value.slice(0, idx) : '';
        const jsonStr = idx >= 0 ? value.slice(idx) : '[]';
        let data;
        try {
          data = JSON.parse(jsonStr);
        } catch (e) {
          console.error('无法解析 LevelDB 中的 JSON，请勿继续写入。');
          throw e;
        }
        const merged = mergeCollectionsIntoData(data, collections);
        const newValue = prefix + JSON.stringify(merged);
        await db.put(key, newValue);
        console.log('\n已写入 LevelDB。请启动 Steam 查看库内收藏是否出现。');
        break;
      }
    }
    if (!found) {
      console.error('未在 LevelDB 中找到包含收藏数据的 key（steamloopback.host + U' + config.steamId + '-cloud-storage-namespace）。');
      console.error('请确认 steam_id 与 userdata 下文件夹名一致（如 886001714）。');
    }
  } finally {
    await db.close();
  }
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
