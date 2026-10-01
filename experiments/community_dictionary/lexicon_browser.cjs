// Disposable database and synthetic media only; run with browser_rehearsal.py.
const {chromium, devices} = require(process.env.COMMUNITY_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const root = process.env.COMMUNITY_BROWSER_OUTPUT;
assert(root, 'Run through browser_rehearsal.py');
const base = 'http://127.0.0.1:8765';
const browse = base + '/community-dictionaries/1/';
(async () => {
  const browser = await chromium.launch({executablePath: process.env.COMMUNITY_CHROMIUM_PATH || undefined,
    headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']});
  try {
    const owner = await browser.newContext({...devices['Pixel 7']});
    const member = await browser.newContext({...devices['iPhone 13'], defaultBrowserType: undefined});
    const p = await owner.newPage(), m = await member.newPage(), errors = [];
    for (const page of [p,m]) {page.setDefaultTimeout(15000); page.on('pageerror', e => errors.push(String(e)));}
    const login = async (page, name) => {
      await page.goto(base + '/community-dictionaries/login/');
      await page.locator('[name=username]').fill(name);
      await page.locator('[name=password]').fill('local-browser-trial-only');
      await page.getByRole('button', {name:'Log in',exact:true}).click();
      await page.waitForURL(base + '/community-dictionaries/');
    };
    const ready = page => page.waitForFunction(() => !document.querySelector('[data-save-submit]').disabled);
    const noOverflow = async page => assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    const wordRow = (page, word) => page.locator('[data-word-row]').filter({has:page.getByRole('heading', {name:word,exact:true})});
    async function create(word, meaning, photo=true) {
      await p.goto(browse + 'new/'); await ready(p);
      await p.locator('[name=word]').fill(word);
      await p.locator('[name=meaning]').fill(meaning);
      if (photo) await p.locator('[data-camera]').setInputFiles(root + '/browser-photo.png');
      await p.locator('[name=audio]').setInputFiles(root + '/microphone-tone.wav');
      await p.getByRole('button', {name:'Save',exact:true}).first().click();
      await p.waitForURL(/\/entries\/\d+\/$/);
      return {url:p.url(), id:p.url().match(/entries\/(\d+)/)[1], image:photo ? await p.locator('.entry-image').getAttribute('src') : null};
    }
    async function link(wordId, entryURL) {
      await p.goto(entryURL); await ready(p);
      await p.locator('.link-words-editor>summary').click();
      await p.locator('[name=word_entry]').first().selectOption(wordId);
      await p.getByRole('button', {name:'Link word',exact:true}).click();
      await p.waitForURL(/\?picture=\d+#picture-words$/);
    }
    await login(p, 'browser_owner');
    const sofa = await create('soffa', 'sofa');
    const cat = await create('katt', 'cat');
    const sleep = await create('sova', 'sleep', false);
    await link(cat.id, sofa.url);
    await link(sleep.id, sofa.url);
    await link(sleep.id, cat.url);
    await p.goto(sofa.url);
    assert.equal(await p.locator('.entry-image').getAttribute('src'), sofa.image);
    assert.equal(await p.locator('h1').innerText(), 'soffa');
    assert.equal(await p.locator('.picture-words [data-word-row]').count(), 2);
    await noOverflow(p);
    const katt = wordRow(p,'katt'), sova = wordRow(p,'sova');
    assert.equal(await katt.locator('.word-translation p').isVisible(), false);
    const sameURL = p.url();
    await katt.getByText('Translation',{exact:true}).click();
    assert.equal(await katt.locator('.word-translation p').innerText(), 'cat');
    assert.equal(p.url(), sameURL);
    await katt.getByRole('button', {name:'Listen to katt',exact:true}).click();
    await p.waitForFunction(() => document.querySelector('.picture-words audio').currentTime > 0);
    await sova.getByRole('button', {name:'Listen to sova',exact:true}).click();
    assert(await katt.locator('audio').evaluate(a => a.paused));
    assert.equal(p.url(),sameURL);
    await p.waitForFunction(() => [...document.querySelectorAll('.picture-words audio')].some(a => a.currentTime > 0 && !a.paused));
    await p.locator('.audio-item audio').evaluate(a=>a.play());
    assert(await sova.locator('audio').evaluate(a=>a.paused));
    await p.locator('.audio-item audio').evaluate(a=>a.pause());
    await p.locator('#picture-words').scrollIntoViewIfNeeded();
    await p.screenshot({path:root+'/picture-linked-words-mobile.png'});
    await katt.getByRole('link', {name:'Word page →',exact:true}).click();
    await p.waitForURL(browse+'words/'+cat.id+'/');
    assert.equal(await p.locator('.entry-card').count(),2);
    await noOverflow(p);
    await p.screenshot({path:root+'/word-pictures-mobile.png',fullPage:true});
    await p.locator('.entry-card').filter({hasText:'soffa'}).click();
    await p.waitForURL(new RegExp('/entries/'+sofa.id+'/\\?picture=\\d+$'));
    assert.equal(await p.locator('.entry-image').getAttribute('src'),sofa.image);
    console.log('PASS manual many-to-many links; translation stays on picture; inline playback and one voice at a time; word gallery returns to exact picture.');

    // A link operation must protect unsaved discussion just like navigation does.
    await ready(p); await p.locator('[name=body]').fill('Remember this picture');
    await p.locator('.link-words-editor>summary').click();
    await p.getByRole('button',{name:'Remove link to katt',exact:true}).click();
    await p.getByRole('button',{name:'Keep editing',exact:true}).click();
    assert.equal(await p.locator('[name=body]').inputValue(),'Remember this picture');
    await p.getByRole('button',{name:'Remove link to katt',exact:true}).click();
    await p.getByRole('button',{name:'Save and leave',exact:true}).click();
    await p.waitForURL(/#picture-words$/);
    assert.equal(await wordRow(p,'katt').count(),0);
    assert.equal(await wordRow(p,'sova').count(),1);
    assert.equal(await p.locator('.note').filter({hasText:'Remember this picture'}).count(),1);
    await link(cat.id,sofa.url);
    await p.goto(browse);
    await p.getByRole('navigation',{name:'Browse by'}).getByRole('link',{name:'Words',exact:true}).click();
    await p.waitForURL(/view=words/);
    assert.equal(await p.locator('[data-word-row]').count(),3);
    assert.equal(await p.locator('.word-translation[open]').count(),0);
    await p.locator('[name=q]').fill('cat');
    await p.getByRole('button',{name:'Search',exact:true}).click();
    await p.waitForURL(/q=cat/);
    assert.equal(await p.locator('[data-word-row]').count(),1);
    await p.getByRole('navigation',{name:'Browse by'}).getByRole('link',{name:'Pictures',exact:true}).click();
    await p.waitForURL(/view=pictures/);
    assert.equal(await p.locator('.entry-card').count(),2);
    await p.goto(browse+'?view=words');
    await p.screenshot({path:root+'/words-mobile.png',fullPage:true});
    console.log('PASS save discussion before unlink; other links/media retained; Words/Pictures toggles retain search and find extra labels.');

    await login(m,'browser_member'); await m.goto(sofa.url);
    assert.equal(await m.locator('.link-words-editor').count(),0);
    await wordRow(m,'katt').getByRole('button',{name:'Listen to katt',exact:true}).click();
    await m.waitForFunction(()=>document.querySelector('.picture-words audio').currentTime>0);
    await noOverflow(m);
    await member.setOffline(true);
    await wordRow(m,'sova').getByRole('button',{name:'Listen to sova',exact:true}).click();
    await wordRow(m,'sova').locator('[data-word-playback-status]').waitFor({state:'visible'});
    await member.setOffline(false);
    // No-JS users keep native playback and disclosure controls.
    const plain = await browser.newContext({javaScriptEnabled:false,storageState:await owner.storageState(),viewport:{width:390,height:844}});
    const fallback = await plain.newPage(); await fallback.goto(sofa.url);
    assert(await wordRow(fallback,'katt').locator('audio').isVisible());
    assert.equal(await wordRow(fallback,'katt').locator('[data-word-listen]').isVisible(),false);
    await wordRow(fallback,'katt').getByText('Translation',{exact:true}).click();
    assert(await wordRow(fallback,'katt').locator('.word-translation p').isVisible());
    await p.setViewportSize({width:1280,height:900}); await p.goto(browse+'?view=words');
    await noOverflow(p); await p.screenshot({path:root+'/words-desktop.png',fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('PASS member view, playback failure feedback, no-JS fallback, phone/desktop overflow checks; Chromium viewports only, not physical phones.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
