/* Real rendered form + production scripts; no network or paid requests. */
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const payload = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
async function check(restored, mode) {
  const dom = new JSDOM(payload.html, {url: 'https://example.test/practise/describe/?image=1', runScripts: 'outside-only'});
  const w = dom.window, d = w.document, posts = [];
  w.URL.createObjectURL = () => 'blob:test';
  w.URL.revokeObjectURL = () => {};
  const recovered = {values: [['mode', mode], ['description', 'Un gatto.'],
    ['permission', true], ['quote', 'stale'], ['image', '999']],
    files: {audio: new w.File(['fake audio'], 'sample.wav', {type:'audio/wav'})}};
  if (restored) w.indexedDB = {open() {
    const request = {};
    setTimeout(() => {
      request.result = {transaction() {
        const tx = {};
        const done = result => {setTimeout(() => tx.oncomplete(), 0); return {result};};
        tx.objectStore = () => ({get: () => done(recovered), put: () => done(), delete: () => done()});
        return tx;
      }};
      request.onsuccess();
    }, 0);
    return request;
  }};
  w.fetch = async (_url, options) => {
    posts.push(options);
    return {ok:false, headers:{get: () => 'application/json'}, json:async () => ({error:'Test; no provider call.'})};
  };
  try {
    const form = d.querySelector('[data-picture-practice]');
    const quote = form.elements.quote.value, image = form.elements.image.value;
    const ready = new Promise(resolve => form.addEventListener('community-draft-ready', resolve, {once:true}));
    w.eval(payload.app); w.eval(payload.controller); await ready;
    if (restored) {
      assert.equal(form.elements.permission.checked, false);
      assert.equal(form.elements.quote.value, quote);
      assert.equal(form.elements.image.value, image);
      assert.equal(form.elements.mode.value, mode);
    }
    form.elements.mode.value = mode;
    form.elements.description.value = 'Un gatto.';
    form.dispatchEvent(new w.Event('change', {bubbles:true}));
    assert.equal(form.querySelector('[data-practice-type]').disabled, mode === 'voice');
    assert.equal(form.querySelector('[data-practice-speak]').disabled, mode === 'text');
    form.elements.permission.checked = true;
    assert.equal(form.checkValidity(), true);
    form.querySelector('[data-save-submit]').click();
    for (let i=0; i<100 && !posts.length; i++) await new Promise(resolve => setTimeout(resolve, 5));
    assert.equal(posts.length, 1, 'The visible button must reach POST');
    const data = posts[0].body;
    assert.equal(data.get('mode'), mode);
    assert.equal(data.has('audio'), mode === 'voice');
    assert.equal(data.has('description'), mode === 'text');
    assert.equal(data.get('image'), image);
  } finally {w.close();}
}
(async () => {
  await check(false, 'text');
  await check(true, 'text');
  await check(true, 'voice');
  console.log('Picture practice real-button submit passed: typed, recovered typed and recovered audio.');
})().catch(error => {console.error(error); process.exitCode=1;});
