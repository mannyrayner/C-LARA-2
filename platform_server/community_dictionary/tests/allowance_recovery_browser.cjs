/* Rendered practice form and production scripts; no network or providers. */
const assert = require('node:assert/strict');
const {JSDOM} = require('jsdom');
const payload = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
async function check(owner) {
  const dom = new JSDOM(payload.html, {url:'https://clara.example.org/community-dictionaries/1/practise/describe/', runScripts:'outside-only'});
  const w = dom.window, d = w.document, posts = [];
  w.URL.createObjectURL = () => 'blob:test'; w.URL.revokeObjectURL = () => {};
  w.fetch = async (_url, options) => {
    posts.push(options);
    return {ok:false, headers:{get:()=>'application/json'}, json:async()=>({
      code:'allowance_exhausted', error:'This dictionary’s daily allowance has been used up.',
      allowance:{proposed:owner ? 50 : null, extra:owner ? 40 : null, server_limit:false,
        url:owner ? '/community-dictionaries/1/settings/picture-allowance/' : ''}})};
  };
  try {
    const form = d.querySelector('[data-picture-practice]');
    const ready = new Promise(resolve => form.addEventListener('community-draft-ready', resolve, {once:true}));
    w.eval(payload.recorder); w.eval(payload.app); w.eval(payload.controller); await ready;
    form.elements.mode.value = 'voice'; form.dispatchEvent(new w.Event('change', {bubbles:true}));
    const audio = new w.File(['private test recording'], 'practice.wav', {type:'audio/wav'});
    const input = form.querySelector('input[name=audio]');
    Object.defineProperty(input, 'files', {value:[audio]});
    input.dispatchEvent(new w.Event('change', {bubbles:true}));
    form.elements.permission.checked = true;
    const button = form.querySelector('[data-save-submit]');
    for (let attempt=1; attempt<=2; attempt++) {
      button.click();
      for (let i=0; i<100 && (posts.length<attempt || button.disabled); i++)
        await new Promise(resolve=>setTimeout(resolve,5));
      assert.equal(posts.length, attempt, 'Only an explicit click submits again');
      const panel = d.querySelector('[data-allowance-offer]');
      assert.ok(panel); assert.equal(d.querySelectorAll('[data-allowance-offer]').length, 1);
      assert.equal(button.disabled, false); assert.equal(input.files[0], audio);
      assert.equal(posts.at(-1).body.get('audio').name, 'practice.wav');
      const cost = panel.querySelector('form');
      if (owner) {
        assert.equal(cost.method, 'post'); assert.equal(cost.target, '_blank');
        assert.equal(cost.elements.daily_limit.value, '50');
        assert.equal(cost.elements.action.value, 'preview');
        assert.equal(cost.elements.csrfmiddlewaretoken.value, form.elements.csrfmiddlewaretoken.value);
      } else {
        assert.equal(cost, null); assert.ok(panel.textContent.includes('Ask a dictionary owner'));
      }
    }
  } finally {w.close();}
}
(async()=>{await check(true); await check(false); console.log('Allowance recovery preserves audio and requires explicit resubmission.');})()
  .catch(error=>{console.error(error); process.exitCode=1;});
