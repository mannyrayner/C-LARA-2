/* Rendered production form and scripts. Audio and network are simulated. */
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const payload = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
async function setup({recovered=false, missing=false, inflected=false}={}) {
  const dom = new JSDOM(inflected ? payload.inflected : missing ? payload.missing : payload.html, {
    url:'https://example.test/practise/describe/?image=1', runScripts:'outside-only'});
  const w = dom.window, d = w.document, plays = [], posts = [], writes = [];
  let rejectPlay = false;
  w.HTMLMediaElement.prototype.pause = function() {};
  w.HTMLMediaElement.prototype.play = function() {
    plays.push(this.src);
    if (rejectPlay) return Promise.reject(new Error('blocked playback'));
    this.dispatchEvent(new w.Event('playing'));
    return Promise.resolve();
  };
  w.URL.createObjectURL = () => 'blob:test'; w.URL.revokeObjectURL = () => {};
  w.indexedDB = {open() {
    const request = {};
    setTimeout(() => {
      request.result = {transaction() {
        const tx = {};
        const done = result => {setTimeout(() => tx.oncomplete(), 0); return {result};};
        tx.objectStore = () => ({get: () => done(recovered ? {values:[['mode','text'],
          ['description','Un gatto.'], ['hints_used','["words_text"]']], files:{}} : null),
          put: value => {writes.push(value); return done();}, delete: () => done()});
        return tx;
      }}; request.onsuccess();
    }, 0); return request;
  }};
  w.fetch = async (_url, options) => {
    posts.push(options);
    return {ok:false, headers:{get:()=>'application/json'}, json:async()=>({error:'Test only'})};
  };
  const form = d.querySelector('[data-picture-practice]');
  const ready = new Promise(resolve => form.addEventListener('community-draft-ready', resolve, {once:true}));
  w.eval(payload.recorder); w.eval(payload.app); w.eval(payload.controller); await ready;
  const hints = form.querySelector('[data-practice-hints]');
  assert.equal(hints.open, false);
  assert.equal(hints.parentElement.closest('details'), null, 'Hints must be outside More options');
  const options = [...form.querySelectorAll('summary')].find(el => el.textContent==='More options');
  assert.ok(hints.compareDocumentPosition(options) & w.Node.DOCUMENT_POSITION_FOLLOWING);
  hints.open = true; await tick();
  return {dom,w,d,form,hints,plays,posts,writes,
    usage:()=>JSON.parse(form.elements.hints_used.value),
    reveal:kind=>hints.querySelector(`[data-hint-reveal="${kind}"]`),
    listen:kind=>hints.querySelector(`[data-hint-listen="${kind}"]`),
    text:kind=>hints.querySelector(`[data-hint-text="${kind}"]`),
    player:hints.querySelector('[data-hint-player]'),
    reject: value => {rejectPlay=value;}};
}
async function controls() {
  const x = await setup();
  try {
    const initialStatus = x.form.querySelector('[data-draft-status]').textContent;
    assert.equal(x.text('words').hidden, true); assert.equal(x.text('sentence').hidden, true);
    x.listen('words').click(); await tick();
    assert.equal(x.text('words').hidden, true); assert.equal(x.text('sentence').hidden, true);
    assert.deepEqual(x.usage(), ['words_audio']);
    x.player.dispatchEvent(new x.w.Event('ended')); await tick();
    assert.equal(x.plays.length, 2, 'Words play sequentially using one player');
    x.player.dispatchEvent(new x.w.Event('ended')); await tick();
    assert.equal(x.plays.length, 2);
    x.listen('sentence').click(); await tick();
    assert.deepEqual(x.usage(), ['words_audio','sentence_audio']);
    assert.equal(x.text('sentence').hidden, true, 'Listening must not reveal the sentence');
    for (const kind of ['words','sentence']) {
      x.reveal(kind).click(); assert.equal(x.text(kind).hidden, false);
      assert.equal(x.reveal(kind).getAttribute('aria-expanded'), 'true');
      x.reveal(kind).click(); assert.equal(x.text(kind).hidden, true);
      x.reveal(kind).click();
    }
    assert.equal(x.usage().length, 4);
    assert.equal(x.posts.length, 0, 'Hint buttons must never submit the practice');
    assert.equal(x.writes.length, 0, 'Hints alone must not create an unsaved draft');
    assert.equal(x.form.querySelector('[data-draft-status]').textContent, initialStatus);
    x.hints.open = false; await tick();
    const before = x.plays.length;
    x.player.dispatchEvent(new x.w.Event('ended')); await tick();
    assert.equal(x.plays.length, before, 'Closing Hints stops the playlist');
    x.form.elements.mode.value='text'; x.form.elements.description.value='Un gatto.';
    x.form.dispatchEvent(new x.w.Event('change', {bubbles:true}));
    x.form.elements.permission.checked=true;
    x.form.querySelector('[data-save-submit]').click();
    for(let i=0;i<100&&!x.posts.length;i++) await new Promise(r=>setTimeout(r,5));
    assert.equal(x.posts.length,1);
    assert.deepEqual(JSON.parse(x.posts[0].body.get('hints_used')),x.usage());
  } finally {x.dom.window.close();}
}
async function recovery() {
  const x=await setup({recovered:true});
  try {
    assert.deepEqual(x.usage(),['words_text']);
    x.listen('sentence').click();
    for(let i=0;i<100&&!x.writes.length;i++) await new Promise(r=>setTimeout(r,5));
    assert.deepEqual(JSON.parse(x.writes.at(-1).values.find(([key])=>key==='hints_used')[1]),
      ['words_text','sentence_audio']);
  } finally {x.dom.window.close();}
}
async function playbackFailureAndRecording() {
  const x=await setup();
  try {
    x.reject(true); x.listen('words').click(); await tick();
    assert.deepEqual(x.usage(),[], 'Failed playback is not a spoken hint');
    assert.equal(x.hints.querySelector('[data-hint-status]').hidden,false);
    assert.equal(x.player.hidden,false,'Native controls remain available after a phone playback block');
    x.reject(false); await x.player.play();
    assert.deepEqual(x.usage(),['words_audio']);
    const before=x.plays.length;
    x.form.querySelector('[data-record]').classList.add('recording-now');
    x.listen('sentence').click(); await tick();
    assert.equal(x.plays.length,before,'Hint audio must not play into the learner recording');
    assert.match(x.hints.querySelector('[data-hint-status]').textContent,/Stop recording/);
  } finally {x.dom.window.close();}
}
async function missing() {
  const x=await setup({missing:true});
  try {
    assert.equal(x.listen('words'),null); assert.equal(x.listen('sentence'),null);
    assert.equal(x.reveal('sentence'),null); x.reveal('words').click();
    assert.equal(x.text('words').hidden,false); assert.deepEqual(x.usage(),['words_text']);
    assert.equal(x.posts.length,0);
  } finally {x.dom.window.close();}
}
async function contextual() {
  const x=await setup({inflected:true});
  try {
    const lemmas=x.hints.querySelector('[data-hint-lemmas]');
    assert.equal(x.text('words').hidden,true); assert.equal(lemmas.open,false);
    x.reveal('words').click();
    const primary=x.text('words').querySelector(':scope > ul');
    assert.match(primary.textContent,/gatti/); assert.match(primary.textContent,/dormono/);
    assert.doesNotMatch(primary.textContent,/dormire/);
    assert.equal(lemmas.open,false,'Dictionary forms stay collapsed after revealing words');
    lemmas.open=true; await tick();
    assert.ok(x.usage().includes('lemmas_text')); assert.match(lemmas.textContent,/dormire/);
    x.listen('words').click(); await tick();
    assert.equal(x.text('sentence').hidden,true);
    assert.ok(x.usage().includes('words_audio')); assert.equal(x.posts.length,0);
  } finally {x.dom.window.close();}
}
(async()=>{await controls();await recovery();await playbackFailureAndRecording();await missing();await contextual();
  console.log('Hints passed: independent text/audio, playlist, missing material, private usage and recovery.');
})().catch(error=>{console.error(error);process.exitCode=1;});
