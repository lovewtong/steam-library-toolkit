const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'steam_picker.html'), 'utf8');
const elements = new Map();
const document = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, {value: '', addEventListener() {}});
    return elements.get(id);
  },
  createElement() {
    return {textContent: '', get innerHTML() {
      return String(this.textContent).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    }};
  },
};
const context = vm.createContext({document, fetch: () => new Promise(() => {})});
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);

test('first observation year and month intersect and unknown never becomes 1970', () => {
  const game = {first_seen_year: '2026', first_seen_month: '2026-10', first_seen_at: '2026-10-05T00:00:00+00:00'};
  assert.equal(context.matchesFirstSeen(game, '2026', '10'), true);
  assert.equal(context.matchesFirstSeen(game, '2025', '10'), false);
  assert.equal(context.matchesFirstSeen({}, 'unknown', ''), true);
  assert.equal(context.matchesFirstSeen({}, 'unknown', '01'), false);
  assert.ok(context.renderFirstSeen({}).includes('未知'));
  assert.ok(!context.renderFirstSeen({}).includes('1970'));
  assert.ok(context.renderFirstSeen(game).includes('2026-10-05'));
});

test('manufacturer filters preserve multiple names and separate unknown from empty and literal names', () => {
  assert.equal(context.matchesManufacturer(['A', 'B'], 'name:B'), true);
  assert.equal(context.matchesManufacturer(['A'], 'name:B'), false);
  assert.equal(context.matchesManufacturer(null, 'unknown'), true);
  assert.equal(context.matchesManufacturer([], 'unknown'), false);
  assert.equal(context.matchesManufacturer([], 'empty'), true);
  assert.equal(context.matchesManufacturer(['unknown'], 'name:unknown'), true);
});

test('manufacturer rendering escapes names and evidence and tolerates old data', () => {
  const result = context.renderManufacturers({developers: ['<img src=x onerror=alert(1)>'], publishers: [],
    manufacturer_evidence: {developers: {source: 'appid_override', reason: '<script>', fetched_at: 'bad'}}});
  assert.ok(result.includes('&lt;img'));
  assert.ok(result.includes('&lt;script&gt;'));
  assert.ok(!result.includes('<img'));
  assert.ok(result.includes('人工校正'));
  assert.ok(result.includes('明确未列出'));
  assert.ok(context.renderManufacturers({}).includes('开发商：未知'));
});

test('picker intersects manufacturer selections with existing filters and shows correct count', () => {
  vm.runInContext(`data = [
    {appid:'1', name:'First', developers:['A','B'], publishers:['P'], analysis:{primary:'Action'}},
    {appid:'2', name:'Second', developers:['B'], publishers:['Q'], analysis:{primary:'Action'}}];`, context);
  elements.get('developers').value = 'name:B';
  elements.get('publishers').value = 'name:P';
  elements.get('primary').value = 'Action';
  context.filter();
  assert.equal(elements.get('count').textContent, '1 款');
  assert.ok(elements.get('list').innerHTML.includes('First'));
  assert.ok(!elements.get('list').innerHTML.includes('Second'));
  elements.get('publishers').value = 'name:Missing';
  context.filter();
  assert.equal(elements.get('count').textContent, '0 款');
});

test('picker distinguishes reviewed, inferred, unknown and generated fields', () => {
  const rendered = context.renderEvidence({classification_evidence: {fields: {
    primary: {state: 'reviewed', source: 'appid_override'},
    sub: {state: 'inferred', source: 'known_name'},
    vibe: {state: 'unknown', source: 'reset', reason: 'primary_changed'},
    slogan: {state: 'generated', source: 'template'},
  }}});
  for (const label of ['主类：人工确认', '子类：规则推断', '氛围：待核对', '推荐语：模板生成', '强度：未记录依据']) {
    assert.ok(rendered.includes(label), label);
  }
  assert.ok(context.renderEvidence({}).includes('主类：未记录依据'));
});

test('picker escapes override reasons and references without creating executable links', () => {
  const rendered = context.renderEvidence({classification_evidence: {fields: {
    primary: {state: 'reviewed', reason: '<img src=x onerror=alert(1)>', reference: 'javascript:alert(1)'},
  }}});
  assert.ok(rendered.includes('&lt;img'));
  assert.ok(!rendered.includes('<img'));
  assert.ok(!rendered.includes('href='));
});
