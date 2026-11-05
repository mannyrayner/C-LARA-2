// Run with: node --test platform_server/community_dictionary/tests/test_audio_review_navigation.cjs
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {runInNewContext} = require('node:vm');
const {test} = require('node:test');
const source = readFileSync(join(__dirname, '../static/community_dictionary/audio_review.js'), 'utf8');

function page(pending = 3) {
  const handlers = {};
  const state = {confirm: false, prompts: 0, reloads: 0};
  const listen = (name, handler) => { (handlers[name] ||= []).push(handler); };
  const location = new URL('https://example.test/review/123/?page=1');
  location.reload = () => { state.reloads++; state.reloadWarned = fire('beforeunload').defaultPrevented; };
  const document = {
    querySelectorAll: () => [],
    querySelector: () => pending === null ? null : {dataset: {pendingReplacements: String(pending), leaveMessage: 'Leave?'}},
    addEventListener: listen,
  };
  const window = {addEventListener: listen, confirm: () => { state.prompts++; return state.confirm; }};
  runInNewContext(source, {document, window, location, URL, queueMicrotask});
  function fire(name, overrides = {}) {
    const event = {defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...overrides};
    for (const handler of handlers[name] || []) handler(event);
    return event;
  }
  function click(href, attributes = [], overrides = {}) {
    const link = {href: new URL(href, location).href, target: '', hasAttribute: name => attributes.includes(name)};
    return fire('click', {button: 0, target: {closest: () => link}, ...overrides});
  }
  return {state, fire, click};
}

test('unapplied previews warn before leaving; completed and other reviews do not', () => {
  assert.equal(page().fire('beforeunload').defaultPrevented, true);
  assert.equal(page(0).fire('beforeunload').defaultPrevented, false);
  assert.equal(page(null).fire('beforeunload').defaultPrevented, false);
});

test('cancelling navigation stays in review, confirming does not prompt twice', () => {
  const p = page();
  assert.equal(p.click('/dictionary/').defaultPrevented, true);
  assert.equal(p.fire('beforeunload').defaultPrevented, true);
  p.state.confirm = true;
  assert.equal(p.click('/dictionary/').defaultPrevented, false);
  assert.equal(p.state.prompts, 2);
  assert.equal(p.fire('beforeunload').defaultPrevented, false);
});

test('pagination, filters and explicit postponement leave without prompts', async () => {
  for (const [url, attributes] of [['?page=2', []], ['/tools/', ['data-audio-leave-later']]]) {
    const p = page();
    p.click(url, attributes);
    assert.equal(p.state.prompts, 0);
    assert.equal(p.fire('beforeunload').defaultPrevented, false);
  }
  const p = page();
  p.fire('submit', {target: {action: 'https://example.test/review/123/'}});
  await Promise.resolve();
  assert.equal(p.state.prompts, 0);
  assert.equal(p.fire('beforeunload').defaultPrevented, false);
});

test('downloads, anchors and opening another tab preserve the leave warning', () => {
  for (const [url, attributes, overrides] of [
    ['/export.csv', ['download'], {}], ['/export.json', ['data-audio-download'], {}],
    ['#word-2', [], {}], ['/dictionary/', [], {ctrlKey: true}],
  ]) {
    const p = page();
    p.click(url, attributes, overrides);
    assert.equal(p.state.prompts, 0);
    assert.equal(p.fire('beforeunload').defaultPrevented, true);
  }
});

test('a cancelled submission does not disable the warning', async () => {
  const p = page();
  const event = p.fire('submit', {target: {action: 'https://example.test/review/123/'}});
  event.preventDefault();
  await Promise.resolve();
  assert.equal(p.fire('beforeunload').defaultPrevented, true);
});

test('browser Back refreshes saved decisions without an extra leave warning', () => {
  const p = page();
  p.fire('pageshow', {persisted: true});
  assert.equal(p.state.reloads, 1);
  assert.equal(p.state.reloadWarned, false);
});
