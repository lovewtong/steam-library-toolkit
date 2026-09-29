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
