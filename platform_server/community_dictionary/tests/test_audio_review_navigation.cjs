// Run with: node --test platform_server/community_dictionary/tests/test_audio_review_navigation.cjs
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const {runInNewContext} = require('node:vm');
const {test} = require('node:test');
const source = readFileSync(join(__dirname, '../static/community_dictionary/audio_review.js'), 'utf8');

function form(action = null, controlValue = 'accept_all') {
  return {
    // A real button named "action" shadows HTMLFormElement.action.
    action: {name: 'action', value: controlValue, toString: () => '[object HTMLButtonElement]'},
    getAttribute: name => name === 'action' ? action : null,
    hasAttribute: () => false,
  };
}

function bulkForm(action = null) {
  const target = form(action);
  const attributes = {};
  const button = {
    name: 'action', value: 'accept_all', disabled: false,
    textContent: 'Use all usable replacements',
    dataset: {busyLabel: 'Applying replacements…'},
    getAttribute: name => attributes[name] ?? null,
    setAttribute: (name, value) => { attributes[name] = value; },
    toString: () => '[object HTMLButtonElement]',
  };
  const status = {hidden: true};
  target.action = button;
  target.hasAttribute = name => name === 'data-audio-apply-form';
  target.querySelector = selector => selector === '[data-audio-apply-status]' ? status : button;
  return {target, button, status};
}

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
  p.fire('submit', {target: form('https://example.test/review/123/')});
  await Promise.resolve();
  assert.equal(p.state.prompts, 0);
  assert.equal(p.fire('beforeunload').defaultPrevented, false);
});

test('review submissions ignore the button named action', async () => {
  for (const action of [null, '', '/review/123/?page=2']) {
    for (const choice of ['accept_all', 'accept', 'reject', 'note']) {
      const p = page();
      const event = p.fire('submit', {target: form(action, choice)});
      await Promise.resolve();
      assert.equal(event.defaultPrevented, false);
      assert.equal(p.state.prompts, 0);
      assert.equal(p.fire('beforeunload').defaultPrevented, false);
    }
  }
});

test('external form submissions can be cancelled or confirmed', async () => {
  const p = page();
  const cancelled = p.fire('submit', {target: form('/dictionary/')});
  await Promise.resolve();
  assert.equal(cancelled.defaultPrevented, true);
  assert.equal(p.state.prompts, 1);
  assert.equal(p.fire('beforeunload').defaultPrevented, true);
  p.state.confirm = true;
  const confirmed = p.fire('submit', {target: form('/dictionary/')});
  await Promise.resolve();
  assert.equal(confirmed.defaultPrevented, false);
  assert.equal(p.state.prompts, 2);
  assert.equal(p.fire('beforeunload').defaultPrevented, false);
});

test('the submitting button can override the form destination', async () => {
  for (const [action, formaction, warns] of [
    ['/dictionary/', '/review/123/', false],
    ['/review/123/', '/dictionary/', true],
    ['/dictionary/', '', false],
    ['/dictionary/', null, true],
  ]) {
    const p = page();
    const event = p.fire('submit', {
      target: form(action),
      submitter: {getAttribute: name => name === 'formaction' ? formaction : null},
    });
    await Promise.resolve();
    assert.equal(event.defaultPrevented, warns);
    assert.equal(p.state.prompts, warns ? 1 : 0);
    assert.equal(p.fire('beforeunload').defaultPrevented, warns);
  }
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
  const event = p.fire('submit', {target: form('https://example.test/review/123/')});
  event.preventDefault();
  await Promise.resolve();
  assert.equal(p.fire('beforeunload').defaultPrevented, true);
});

test('bulk apply immediately shows feedback and preserves the submitted action', async () => {
  const p = page();
  const {target, button, status} = bulkForm();
  const event = p.fire('submit', {target, submitter: button});
  await Promise.resolve();
  assert.equal(event.defaultPrevented, false);
  assert.equal(p.state.prompts, 0);
  assert.equal(status.hidden, false);
  assert.equal(button.textContent, 'Applying replacements…');
  assert.equal(button.getAttribute('aria-disabled'), 'true');
  assert.equal(button.getAttribute('aria-busy'), 'true');
  assert.equal(button.disabled, false);
  assert.equal(button.name, 'action');
  assert.equal(button.value, 'accept_all');
  assert.equal(p.fire('beforeunload').defaultPrevented, false);
});

test('bulk apply blocks repeated mouse and Enter submissions while awaiting the response', async () => {
  const p = page();
  const {target, button} = bulkForm();
  p.fire('submit', {target, submitter: button});
  await Promise.resolve();
  assert.equal(p.fire('submit', {target, submitter: button}).defaultPrevented, true);
  assert.equal(p.fire('submit', {target}).defaultPrevented, true);
  assert.equal(p.state.prompts, 0);
});

test('cancelled bulk submissions preserve the normal UI and allow a later attempt', async () => {
  for (const alreadyCancelled of [false, true]) {
    const p = page();
    const {target, button, status} = bulkForm();
    const event = p.fire('submit', {target, submitter: button, defaultPrevented: alreadyCancelled});
    event.preventDefault();
    await Promise.resolve();
    assert.equal(status.hidden, true);
    assert.equal(button.textContent, 'Use all usable replacements');
    assert.equal(button.getAttribute('aria-disabled'), null);
    assert.equal(p.fire('beforeunload').defaultPrevented, true);
    const retry = p.fire('submit', {target, submitter: button});
    await Promise.resolve();
    assert.equal(retry.defaultPrevented, false);
    assert.equal(status.hidden, false);
  }
});

test('cancelled navigation from a bulk form does not activate feedback', async () => {
  const p = page();
  const {target, button, status} = bulkForm('/dictionary/');
  const event = p.fire('submit', {target, submitter: button});
  await Promise.resolve();
  assert.equal(event.defaultPrevented, true);
  assert.equal(p.state.prompts, 1);
  assert.equal(status.hidden, true);
  assert.equal(button.getAttribute('aria-disabled'), null);
  assert.equal(p.fire('beforeunload').defaultPrevented, true);
});

test('genuine navigation away still warns while bulk apply is pending', async () => {
  const p = page();
  const {target, button} = bulkForm();
  p.fire('submit', {target, submitter: button});
  await Promise.resolve();
  assert.equal(p.click('/dictionary/').defaultPrevented, true);
  assert.equal(p.state.prompts, 1);
});

test('browser Back refreshes saved decisions without an extra leave warning', () => {
  const p = page();
  p.fire('pageshow', {persisted: true});
  assert.equal(p.state.reloads, 1);
  assert.equal(p.state.reloadWarned, false);
});
