/* Optional DOM regression: NODE_PATH=<jsdom installation> node this-file.cjs.
 * The Django test supplies real rendered pages and production scripts on stdin.
 * No provider requests or browser/network connection are made.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));

async function check(html, restored) {
  const dom = new JSDOM(html, {url: 'https://example.test/community-dictionaries/1/guided/', runScripts: 'outside-only'});
  const w = dom.window, d = w.document;
  const posts = [];
  if (restored) {
    // Asynchronous recovery must finish before inactive controls are disabled.
    w.indexedDB = {open() {
      const request = {};
      setTimeout(() => {
        request.result = {transaction() {
          const transaction = {};
          const perform = result => {
            setTimeout(() => transaction.oncomplete(), 0);
            return {result};
          };
          transaction.objectStore = () => ({get: () => perform(restored),
            put: () => perform(undefined), delete: () => perform(undefined)});
          return transaction;
        }};
        request.onsuccess();
      }, 0);
      return request;
    }};
  }
  w.fetch = async (_url, options) => {
    posts.push(options);
    // Keep the page open so the test can inspect data and restored controls.
    return {ok: false, headers: {get: () => 'application/json'},
      json: async () => ({saved: false, error: 'Test response; no paid processing.'})};
  };
  try {
    const form = d.querySelector('[data-guided-start]');
    const quote = form.elements.words_quote.value;
    const ready = new Promise(resolve => form.addEventListener('community-draft-ready', resolve, {once: true}));
    w.eval(payload.app);
    w.eval(payload.guided);
    await ready;
    if (restored) {
      assert.equal(form.elements.start_with.value, 'words');
      assert.equal(form.elements.words.value, 'Recovered words.');
      assert.equal(form.elements.words_permission.checked, false);
      assert.equal(form.elements.extra_image_allowance.checked, false);
      assert.equal(form.elements.words_quote.value, quote);
    }
    form.elements.start_with.value = 'words';
    form.elements.words_mode.value = 'text';
    form.elements.words_language.value = 'English';
    form.elements.words.value = 'A cat and a woman are watching a show.';
    form.elements.words_permission.checked = true;
    form.elements.extra_image_allowance.checked = true;
    form.dispatchEvent(new w.Event('change', {bubbles: true}));
    assert.equal(form.querySelector('[data-guided-picture]').disabled, true);
    assert.equal(form.elements.permission.required, true, 'picture permission remains required on its own route');
    assert.equal(form.elements.permission.willValidate, false, 'inactive permission must not block submission');
    assert.equal(form.checkValidity(), true);
    form.querySelector('[data-words-submit]').click();
    for (let i = 0; i < 100 && !posts.length; i++) await new Promise(resolve => setTimeout(resolve, 5));
    assert.equal(posts.length, 1, 'Generate picture must reach the POST handler');
    const data = posts[0].body;
    assert.equal(data.get('start_with'), 'words');
    assert.equal(data.get('words'), form.elements.words.value);
    assert.equal(data.get('extra_image_allowance'), 'on');
    assert.equal(data.has('permission'), false, 'picture-only permission must not be sent');
    assert.equal(data.has('photo'), false);
    await new Promise(resolve => setTimeout(resolve, 5));
    form.elements.start_with.value = 'picture';
    form.dispatchEvent(new w.Event('change', {bubbles: true}));
    assert.equal(form.elements.permission.willValidate, true);
    assert.equal(form.checkValidity(), false, 'picture mode still needs its own permission');
    form.elements.start_with.value = 'words';
    form.elements.words_mode.value = 'voice';
    form.dispatchEvent(new w.Event('change', {bubbles: true}));
    assert.equal(form.querySelector('[data-guided-type]').disabled, true);
    assert.equal(form.querySelector('[data-guided-speak]').disabled, false);
    form.elements.picture_style.value = 'custom';
    form.dispatchEvent(new w.Event('change', {bubbles: true}));
    assert.equal(form.querySelector('[data-guided-custom]').disabled, false);
  } finally { w.close(); }
}

(async () => {
  await check(payload.initial);
  await check(payload.sticky);
  await check(payload.initial, {values: [['start_with', 'words'], ['words_mode', 'text'],
    ['words', 'Recovered words.'], ['words_permission', true], ['extra_image_allowance', true], ['words_quote', 'stale']], files: {}});
  console.log('Generate-picture DOM submission passed: first use, sticky route, restored draft.');
})().catch(error => {console.error(error); process.exitCode = 1;});
