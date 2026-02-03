const fs = require('fs');
const data = JSON.parse(fs.readFileSync('steam_library.json', 'utf8'));
const out = {};

function classify(g) {
  const name = (g.name || '').toLowerCase();
  const genres = (g.genres || []).join(' ').toLowerCase();
  const all = name + ' ' + genres;

  // ---------- 非游戏/工具 ----------
  if (name.includes('3dmark')) return '性能基准 (显卡杀手)';
  if (name.includes('wallpaper engine') || name.includes('movavi') || name.includes('petz catz') || name.includes('jackbox megapicker')) return '其他/工具';

  // ========== 靠前：即时战略、战棋、全战 ==========
  // 即时战略 (RTS)
  if (name.includes('northgard') || name.includes('synergy')) return '即时战略 (RTS)';

  // 战棋/回合战术
  if (name.includes('xcom') || name.includes('chimera squad') || name.includes('metal slug tactics') || name.includes('lamplighters league') || name.includes('miasma chronicles') || name.includes('operation: polygon') || name.includes('warhammer age of sigmar') || name.includes('realms of ruin') || name.includes('invisible, inc')) return '战棋/回合战术';

  // 全战/大战略
  if (name.includes('total war') || name.includes('hearts of iron') || name.includes('victoria 3')) return '全战/大战略';

  // 4X策略
  if (name.includes('civilization') || name.includes('age of wonders')) return '4X策略';

  // 建造与生存策略
  if (name.includes('frostpunk') || name.includes('terraformers') || name.includes('mind over magic') || name.includes('anno 1800')) return '建造与生存策略';

  // 回合策略与卡牌策略（Gladius、SpellForce、Armello 等）
  if (name.includes('warhammer 40,000: gladius') || name.includes('gladius - relics of war') || name.includes('spellforce 3') || name.includes('spellforce: conquest') || name.includes('armello') || name.includes('griftlands') || name.includes('cobalt core') || name.includes('symphony of war') || name.includes('rungore') || name.includes('spin hero') || name.includes('beholder: conductor') || name.includes('castle of alchemists') || name.includes('beneath oresa') || name.includes('pegasus expedition') || name.includes('station to station') || name.includes('ecognomix')) return '回合策略/卡牌策略';

  // ---------- 模拟经营 ----------
  if (name.includes('euro truck') || name.includes('american truck') || name.includes('oxygen not included') || name.includes('sims') || name.includes('my time at portia') || name.includes('autonauts') || name.includes('snowtopia') || name.includes('wild terra 2') || name.includes('evil genius') || name.includes('mercury fallen') || name.includes('dungeon tycoon') || name.includes('pharaoh') || name.includes('chinese parents') || name.includes('settlement survival') || name.includes('smart factory') || name.includes('garden life') || name.includes('summerhouse') || name.includes('autonauts vs') || name.includes('servonauts') || name.includes('smart factory tycoon') || name.includes('dungeon tycoon') || name.includes('pharaoh: a new era') || name.includes('garden life:') || name.includes('snowtopia') || name.includes('wild terra 2') || name.includes('mercury fallen') || name.includes('evil genius 2')) return '模拟经营';

  // ---------- 硬核生存/生存建造 ----------
  if (name.includes('don\'t starve') && !name.includes('together')) return '硬核生存';
  if (name.includes('this war of mine') || name.includes('dead in vinland') || name.includes('chernobylite') || name.includes('metro 2033') || name.includes('metro: last light') || name.includes('metro exodus') || name.includes('don\'t starve together')) return '硬核生存';

  // ---------- CRPG/美式RPG ----------
  if (name.includes('baldur\'s gate') || name.includes('divinity: original sin') || name.includes('pathfinder') || name.includes('disco elysium') || name.includes('planescape') || name.includes('icewind dale') || name.includes('neverwinter nights') || name.includes('witcher 3') || name.includes('scroll of taiwu') || name.includes('etrian odyssey')) return 'CRPG/美式RPG';

  // ---------- 共斗/怪猎like ----------
  if (name.includes('monster hunter') || name.includes('remnant ii') || name.includes('tiny tina\'s wonderlands')) return '共斗/怪猎like';

  // ---------- 类银河城 ----------
  if (name.includes('blasphemous') || name.includes('valfaris') || name.includes('afterimage') || name.includes('nine sols') || name.includes('another crab\'s treasure') || name.includes('crypt of the necrodancer')) return '类银河城';

  // ---------- 魂系/高难度动作 ----------
  if (name.includes('ghostrunner 2')) return '魂系/高难度动作';

  // ---------- 竞技/合作射击 ----------
  if (name.includes('left 4 dead') || name.includes('back 4 blood') || name.includes('hunt: showdown') || name.includes('escape from tarkov')) return '竞技/合作射击';

  // ---------- 潜行/狙击 ----------
  if (name.includes('hitman') || name.includes('sniper elite') || name.includes('intravenous') || name.includes('mark of the ninja')) return '潜行/狙击';

  // ---------- FPS/主视角射击 ----------
  if (name.includes('bioshock') || name.includes('f.e.a.r.') || name.includes('metro ') || name.includes('postal ') || name.includes('one gun guy') || name.includes('bright memory') || name.includes('destroyer: the u-boat') || name.includes('zombie army') || name.includes('strange brigade') || name.includes('rollerdrome')) return 'FPS/主视角射击';
  if (name.includes('fashion police squad')) return 'FPS/主视角射击';

  // ---------- 互动电影/叙事 ----------
  if (name.includes('danganronpa') || name.includes('heavy rain') || name.includes('detroit: become human') || name.includes('beyond: two souls') || name.includes('fahrenheit') || name.includes('the quarry') || name.includes('martha is dead') || name.includes('ad infinitum') || name.includes('signifier') || name.includes('the vale') || name.includes('beyond a steel sky') || name.includes('lacuna') || name.includes('murders on the yangtze') || name.includes('sherlock holmes') || name.includes('brok the investigator') || name.includes('song of farca') || name.includes('the bookwalker') || name.includes('figment 2') || name.includes('between horizons') || name.includes('stray gods') || name.includes('who pressed mute') || name.includes('the deed:') || name.includes('immortality') || name.includes('botany manor')) return '互动电影/叙事';

  // ---------- 格斗/对战 ----------
  if (name.includes('for honor') || name.includes('mortal kombat') || name.includes('injustice') || name.includes('pocket bravery') || name.includes('crown champion') || name.includes('streets of rage 4')) return '格斗/对战';

  // ---------- 竞速 ----------
  if (name.includes('assetto corsa') || name.includes('grip: combat racing') || name.includes('barro gt') || (name.includes('lego') && name.includes('drive')) || name.includes('grid ranger') || name.includes('initial drift')) return '竞速';

  // ---------- 体育 ----------
  if (name.includes('topspin') || name.includes('wrestledunk') || name.includes('rollerdrome')) return '体育';

  // ---------- 合家欢/派对 ----------
  if (name.includes('fall guys') || name.includes('talisman') || name.includes('100% orange juice') || name.includes('drawful 2') || name.includes('bang-on balls') || name.includes('super lucky') || name.includes('gori: cuddly') || name.includes('hot lava') || name.includes('skillshot city') || name.includes('this means warp') || name.includes('karmazoo') || name.includes('ninjam!') || name.includes('death in unison') || name.includes('what the fog')) return '合家欢/派对';
  // ---------- 卡牌/自走棋 ----------
  if (name.includes('cardpocalypse') || name.includes('super bullet break')) return '卡牌/自走棋';

  // ---------- 视觉小说/恋爱 ----------
  if (name.includes('go! go! nippon') || name.includes('if my heart had wings') || name.includes('eden*') || name.includes('tricolour lovestory') || name.includes('expression amrilato') || name.includes('a sky full of stars') || name.includes('gal*gun')) return '视觉小说/恋爱';

  // ---------- 独立叙事/休闲小品 ----------
  if (name.includes('plants vs. zombies') || name.includes('eets munchies') || name.includes('broken age') || name.includes('chicory') || name.includes('a space for the unbound') || name.includes('just ignore them') || name.includes('needy streamer') || name.includes('sucker for love') || name.includes('caveman world') || name.includes('along the edge') || name.includes('paleo pines') || name.includes('shashingo') || name.includes('kind words 2') || name.includes('on your tail') || name.includes('everholm') || name.includes('ad fundum') || name.includes('little-known galaxy') || name.includes('man i just wanna go home') || name.includes('naiad') || name.includes('snufkin') || name.includes('endless monday') || name.includes('nice day for fishing') || name.includes('spirittea') || name.includes('gerda: a flame') || name.includes('i was a teenage exocolonist') || name.includes('godlike burger')) return '独立叙事/休闲小品';

  // ---------- 动作冒险（蝙蝠侠、中土、清版等）----------
  return '动作冒险';
}

data.forEach(g => {
  const cat = classify(g);
  if (!out[cat]) out[cat] = [];
  out[cat].push(g.appid);
});

// 输出顺序：即时战略、战棋、全战 靠前，总分类数 ≤50
const ORDER = [
  '即时战略 (RTS)',
  '战棋/回合战术',
  '全战/大战略',
  '4X策略',
  '建造与生存策略',
  '回合策略/卡牌策略',
  '模拟经营',
  '硬核生存',
  'CRPG/美式RPG',
  '共斗/怪猎like',
  '类银河城',
  '魂系/高难度动作',
  '竞技/合作射击',
  '潜行/狙击',
  'FPS/主视角射击',
  '动作冒险',
  '互动电影/叙事',
  '格斗/对战',
  '竞速',
  '体育',
  '合家欢/派对',
  '卡牌/自走棋',
  '独立叙事/休闲小品',
  '视觉小说/恋爱',
  '性能基准 (显卡杀手)',
  '其他/工具'
];

const sorted = {};
ORDER.forEach(k => { if (out[k] && out[k].length) sorted[k] = out[k]; });
Object.keys(out).filter(k => !ORDER.includes(k)).forEach(k => sorted[k] = out[k]);

if (Object.keys(sorted).length > 50) console.error('分类数超过50:', Object.keys(sorted).length);

const result = JSON.stringify(sorted, null, 2);
fs.writeFileSync('steam_collections_result.json', result, 'utf8');
console.log(result);
