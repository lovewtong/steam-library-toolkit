const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

let SteamCategories;
try {
  SteamCategories = require('steam-categories');
} catch (err) {
  console.error('缺少依赖 steam-categories，请先执行: npm install steam-categories');
  process.exit(1);
}

const STEAM_ID_32 = '886001714';
const SCRIPT_DIR = __dirname;
const INPUT_JSON = path.join(SCRIPT_DIR, 'steam_collections_result.json');

function getLocalAppData() {
  return process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
}

function getInstallPathFromConfig() {
  const cfgPath = path.join(SCRIPT_DIR, 'config_local.json');
  if (!fs.existsSync(cfgPath)) return '';
  try {
    const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
    return String(cfg.steam_install_path || '').trim();
  } catch (err) {
    return '';
  }
}

function normalizeInstallPath(rawPath) {
  const cleaned = String(rawPath || '').trim().replace(/^"+|"+$/g, '');
  if (!cleaned) return '';
  if (cleaned.toLowerCase().endsWith('steam.exe')) {
    return path.dirname(cleaned);
  }
  return cleaned;
}

function getSteamInstallPath() {
  const fromConfig = normalizeInstallPath(getInstallPathFromConfig());
  if (fromConfig) return fromConfig;
  const fromEnv = normalizeInstallPath(process.env.STEAM_PATH || process.env.STEAM_EXE || '');
  if (fromEnv) return fromEnv;
  return '';
}

function getLevelDbCandidates() {
  const base = path.join(getLocalAppData(), 'Steam', 'htmlcache');
  const candidates = [
    path.join(base, 'Default', 'Local Storage', 'leveldb'),
    path.join(base, 'Local Storage', 'leveldb'),
    path.join(base, 'Default', 'Sync Data', 'LevelDB'),
  ];

  const installPath = getSteamInstallPath();
  if (installPath) {
    candidates.push(path.join(installPath, 'config', 'htmlcache', 'Local Storage', 'leveldb'));
    candidates.push(path.join(installPath, 'htmlcache', 'Local Storage', 'leveldb'));
    candidates.push(
      path.join(installPath, 'userdata', STEAM_ID_32, 'config', 'htmlcache', 'Local Storage', 'leveldb')
    );
  }

  return [...new Set(candidates)];
}

function findLevelDbPath() {
  const candidates = getLevelDbCandidates();
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return candidates[0];
}

function loadClassicLevel() {
  try {
    const pkg = require('classic-level');
    return pkg.ClassicLevel || pkg;
  } catch (err) {
    return null;
  }
}

async function detectSteam3Ids(levelDbPath) {
  const ClassicLevel = loadClassicLevel();
  if (!ClassicLevel) return [];
  const db = new ClassicLevel(levelDbPath, { keyEncoding: 'utf8', valueEncoding: 'utf8' });
  const ids = new Set();
  try {
    for await (const [key] of db.iterator()) {
      if (!key || typeof key !== 'string') continue;
      if (!key.includes('cloud-storage-namespace')) continue;
      const match = key.match(/U(\d+)-cloud-storage-namespace/);
      if (match && match[1]) ids.add(match[1]);
    }
  } catch (err) {
    return [];
  } finally {
    await db.close();
  }
  return [...ids];
}

async function findBestLevelDbPath() {
  const candidates = getLevelDbCandidates();
  let firstExisting = '';
  for (const p of candidates) {
    if (!fs.existsSync(p)) continue;
    if (!firstExisting) firstExisting = p;
    const ids = await detectSteam3Ids(p);
    if (ids.length > 0) return { levelDbPath: p, detectedIds: ids };
  }
  return { levelDbPath: firstExisting || candidates[0], detectedIds: [] };
}

async function safeCloseCats(cats) {
  if (cats && cats.db && cats.isOpen && cats.isOpen()) {
    await cats.close();
  }
}

async function readWithDiagnostics(cats, levelDbPath, detectedIds) {
  try {
    await cats.read();
  } catch (err) {
    const message = String(err && err.message ? err.message : err);
    await safeCloseCats(cats);
    if (message.includes('Key not found in database')) {
      const ids = detectedIds && detectedIds.length ? detectedIds : await detectSteam3Ids(levelDbPath);
      if (ids.length === 0) {
        return { ok: false, reason: 'no-namespace' };
      }
      if (!ids.includes(STEAM_ID_32)) {
        throw new Error(
          `当前 LevelDB 中检测到的 Steam3 ID: ${ids.join(', ')}。请确认脚本中的 STEAM_ID_32 是否正确，或使用该账号登录并创建收藏。`
        );
      }
    }
    throw new Error(message);
  }
  return { ok: true };
}

function getSteamId64() {
  const raw = String(STEAM_ID_32 || '').trim();
  if (!raw) return '';
  if (/^\d{16,17}$/.test(raw)) return raw;
  try {
    return (BigInt('76561197960265728') + BigInt(raw)).toString();
  } catch (err) {
    return '';
  }
}

function getCloudStorageCandidates() {
  const installPath = getSteamInstallPath();
  if (!installPath) return [];
  const id64 = getSteamId64();
  const ids = new Set([id64, STEAM_ID_32].filter(Boolean));
  const out = [];
  for (const id of ids) {
    out.push(path.join(installPath, 'userdata', id, 'config', 'cloudstorage', 'cloud-storage-namespace-1.json'));
  }
  return out;
}

function readCloudStorage(filePath) {
  if (!fs.existsSync(filePath)) {
    return { raw: null, format: 'unknown' };
  }
  let raw;
  try {
    raw = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (err) {
    return { raw: null, format: 'unknown' };
  }
  if (Array.isArray(raw)) return { raw, format: 'list_of_entries' };
  if (raw && typeof raw === 'object') {
    const keys = Object.keys(raw);
    if (keys.length === 1 && Array.isArray(raw[keys[0]])) {
      return { raw, format: 'single_key_list' };
    }
    for (const value of Object.values(raw)) {
      if (value && typeof value === 'object' && 'value' in value) {
        return { raw, format: 'object_with_value_strings' };
      }
      if (Array.isArray(value)) {
        return { raw, format: 'single_key_list' };
      }
    }
    return { raw, format: 'object_with_value_strings' };
  }
  return { raw, format: 'unknown' };
}

function makeCloudEntry(collectionId, name, appids, timestamp) {
  const entry = {
    id: collectionId,
    name,
    added: appids,
    removed: [],
  };
  const key = `user-collections.${collectionId}`;
  return [
    key,
    {
      key,
      timestamp,
      value: JSON.stringify(entry),
      conflictResolutionMethod: 'custom',
      strMethodId: 'union-collections',
      version: '1',
    },
  ];
}

function collectExistingKeys(raw, format) {
  const keys = new Set();
  if (!raw) return keys;
  if (format === 'list_of_entries' && Array.isArray(raw)) {
    for (const item of raw) {
      if (Array.isArray(item) && typeof item[0] === 'string') keys.add(item[0]);
    }
  } else if (format === 'single_key_list' && typeof raw === 'object') {
    const k = Object.keys(raw)[0];
    const list = Array.isArray(raw[k]) ? raw[k] : [];
    for (const item of list) {
      if (Array.isArray(item) && typeof item[0] === 'string') keys.add(item[0]);
    }
  } else if (format === 'object_with_value_strings' && typeof raw === 'object') {
    for (const k of Object.keys(raw)) keys.add(k);
  }
  return keys;
}

function mergeIntoCloud(raw, format, collections, timestamp) {
  const existingKeys = collectExistingKeys(raw, format);
  const results = [];
  const entriesToAdd = [];
  for (const [name, appids] of Object.entries(collections)) {
    const id = generateCollectionId(name);
    const key = `user-collections.${id}`;
    if (existingKeys.has(key)) {
      results.push({ name, id, count: appids.length, status: 'skipped' });
      continue;
    }
    entriesToAdd.push(makeCloudEntry(id, name, appids, timestamp));
    results.push({ name, id, count: appids.length, status: 'added' });
  }

  if (format === 'list_of_entries') {
    const out = Array.isArray(raw) ? [...raw] : [];
    for (const entry of entriesToAdd) out.push(entry);
    return { merged: out, results };
  }
  if (format === 'single_key_list' && raw && typeof raw === 'object') {
    const key = Object.keys(raw)[0];
    const outList = Array.isArray(raw[key]) ? [...raw[key]] : [];
    for (const entry of entriesToAdd) outList.push(entry);
    return { merged: { [key]: outList }, results };
  }
  if (format === 'object_with_value_strings' && raw && typeof raw === 'object') {
    const out = { ...raw };
    for (const entry of entriesToAdd) {
      out[entry[0]] = entry[1];
    }
    return { merged: out, results };
  }
  return { merged: null, results };
}

function writeCloudStorage(filePath, merged) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  if (fs.existsSync(filePath)) {
    const backupPath = `${filePath}.bak`;
    fs.copyFileSync(filePath, backupPath);
  }
  fs.writeFileSync(filePath, JSON.stringify(merged), 'utf8');
}

function isSteamRunningWindows() {
  try {
    const output = execFileSync(
      'tasklist',
      ['/FI', 'IMAGENAME eq steam.exe', '/FO', 'CSV', '/NH'],
      { encoding: 'utf8', windowsHide: true }
    );
    if (!output) return false;
    return output.toLowerCase().includes('steam.exe');
  } catch (err) {
    throw new Error('无法检查 steam.exe 进程，请在普通终端中运行脚本。');
  }
}

function assertSteamClosed() {
  if (process.platform === 'win32' && isSteamRunningWindows()) {
    throw new Error('检测到 steam.exe 正在运行，请完全退出 Steam（含托盘）后重试。');
  }
}

function normalizeAppIds(appids) {
  const normalized = [];
  for (const raw of appids) {
    const num = typeof raw === 'number' ? raw : parseInt(String(raw), 10);
    if (Number.isInteger(num) && num > 0) normalized.push(num);
  }
  return [...new Set(normalized)].sort((a, b) => a - b);
}

function loadCollections(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error('未找到 steam_collections_result.json');
  }
  const raw = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new Error('steam_collections_result.json 格式应为 { "分类名": [appid] }');
  }

  const collections = {};
  for (const [name, appids] of Object.entries(raw)) {
    if (!Array.isArray(appids)) continue;
    const normalized = normalizeAppIds(appids);
    if (normalized.length === 0) continue;
    const cleanName = String(name || '').trim() || 'Unnamed';
    collections[cleanName] = normalized;
  }
  return collections;
}

function generateCollectionId(name) {
  const seed = `${STEAM_ID_32}:${name}`;
  const hash = crypto.createHash('sha1').update(seed).digest('hex').slice(0, 20);
  return `uc-v1-${hash}`;
}

async function main() {
  assertSteamClosed();

  const { levelDbPath, detectedIds } = await findBestLevelDbPath();
  if (!fs.existsSync(levelDbPath)) {
    const tried = getLevelDbCandidates().join('\n- ');
    throw new Error(`未找到 LevelDB 目录，已尝试:\n- ${tried}`);
  }

  const collections = loadCollections(INPUT_JSON);
  const categoryNames = Object.keys(collections);
  if (categoryNames.length === 0) {
    throw new Error('未发现可导入的分类');
  }

  console.log('LevelDB 路径:', levelDbPath);
  console.log('Steam ID (32位):', STEAM_ID_32);
  console.log('待导入分类数:', categoryNames.length);

  const cats = new SteamCategories(levelDbPath, STEAM_ID_32);
  const results = [];
  const now = Math.floor(Date.now() / 1000);

  try {
    const readResult = await readWithDiagnostics(cats, levelDbPath, detectedIds);
    if (!readResult.ok && readResult.reason === 'no-namespace') {
      await safeCloseCats(cats);
      const cloudCandidates = getCloudStorageCandidates();
      if (!cloudCandidates.length) {
        throw new Error('未找到 Steam 安装路径，无法使用 cloud-storage 兜底方案。请设置 config_local.json 的 steam_install_path。');
      }
      const cloudPath = cloudCandidates.find((p) => fs.existsSync(p)) || cloudCandidates[0];
      const { raw, format } = readCloudStorage(cloudPath);
      if (!raw || format === 'unknown') {
        throw new Error(
          `未能识别 cloud-storage-namespace-1.json 格式，路径: ${cloudPath}。请确认该账号已有收藏夹。`
        );
      }
      const { merged, results: cloudResults } = mergeIntoCloud(raw, format, collections, now);
      if (!merged) {
        throw new Error(
          `cloud-storage-namespace-1.json 格式不兼容，路径: ${cloudPath}。`
        );
      }
      writeCloudStorage(cloudPath, merged);

      console.log('\n导入结果（cloud-storage 兜底）：');
      for (const row of cloudResults) {
        const statusLabel = row.status === 'added' ? 'OK' : 'SKIP';
        console.log(`- ${statusLabel} | ${row.name} | ${row.count} appids`);
      }
      const addedCount = cloudResults.filter((r) => r.status === 'added').length;
      const skippedCount = cloudResults.filter((r) => r.status === 'skipped').length;
      console.log(`\n完成：新增 ${addedCount}，跳过 ${skippedCount}`);
      console.log('请在 Steam「库」-「收藏夹」核对分类与数量。');
      console.log('如未显示，完全退出 Steam 后重试。');
      return;
    }

    if (!cats.collections || Object.keys(cats.collections).length === 0) {
      throw new Error('未找到收藏命名空间。请在 Steam 新建一个收藏夹后重试。');
    }

    for (const [name, appids] of Object.entries(collections)) {
      const id = generateCollectionId(name);
      if (cats.get(id)) {
        results.push({ name, id, count: appids.length, status: 'skipped' });
        continue;
      }
      const entry = cats.add(id, { name, added: appids, removed: [] });
      entry.timestamp = now;
      results.push({ name, id, count: appids.length, status: 'added' });
    }

    await cats.save();
  } finally {
    await safeCloseCats(cats);
  }

  console.log('\n导入结果：');
  for (const row of results) {
    const statusLabel = row.status === 'added' ? 'OK' : 'SKIP';
    console.log(`- ${statusLabel} | ${row.name} | ${row.count} appids`);
  }

  const addedCount = results.filter((r) => r.status === 'added').length;
  const skippedCount = results.filter((r) => r.status === 'skipped').length;
  console.log(`\n完成：新增 ${addedCount}，跳过 ${skippedCount}`);
  console.log('请在 Steam「库」-「收藏夹」核对分类与数量。');
  console.log('如未显示，完全退出 Steam 后重试。');
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
