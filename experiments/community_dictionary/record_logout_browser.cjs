// Synthetic users/media only; run through browser_rehearsal.py.
const {chromium, devices} = require(process.env.COMMUNITY_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const root = process.env.COMMUNITY_BROWSER_OUTPUT;
assert(root, 'Run through browser_rehearsal.py');
const base = 'http://127.0.0.1:8765';

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.COMMUNITY_CHROMIUM_PATH || undefined,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu',
      '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
      `--use-file-for-fake-audio-capture=${root}/microphone-tone.wav`],
  });
  try {
    const owner = await browser.newContext({...devices['Pixel 7'], permissions: ['microphone']});
    const member = await browser.newContext({...devices['iPhone 13'], defaultBrowserType: undefined});
    const p = await owner.newPage(), m = await member.newPage();
    const errors = [];
    for (const page of [p, m]) {
      page.setDefaultTimeout(15000);
      page.on('pageerror', e => errors.push(String(e)));
    }
    const login = async (page, name) => {
      await page.goto(base + '/community-dictionaries/login/');
      await page.locator('[name=username]').fill(name);
      await page.locator('[name=password]').fill('local-browser-trial-only');
      await page.getByRole('button', {name: 'Log in', exact: true}).click();
      await page.waitForURL(base + '/community-dictionaries/');
    };
    const ready = page => page.waitForFunction(() => !document.querySelector('[data-save-submit]').disabled);
    const draftSaved = page => page.waitForFunction(() => document.querySelector('[data-draft-status]').textContent.includes('recovery draft is stored'));
    const noOverflow = async page => assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    async function record(page) {
      await ready(page);
      await page.locator('[data-record]').click();
      await page.waitForFunction(() => document.querySelector('[data-record-state]').textContent.includes('Recording… 1'));
      // Logout during live capture must not discard the microphone take.
      await page.getByRole('button', {name: 'Logout', exact: true}).click();
      await page.locator('[data-submit-error]').filter({hasText: 'Finish recording'}).waitFor();
      await page.locator('[data-record]').click();
      await page.locator('[data-audio-preview]').waitFor({state: 'visible'});
      await page.waitForFunction(() => !document.querySelector('[data-record]').disabled);
      await draftSaved(page);
    }
    async function assertSound(locator) {
      const peak = await locator.evaluate(async audio => {
        const context = new AudioContext();
        try {
          const bytes = await (await fetch(audio.src)).arrayBuffer();
          const buffer = await context.decodeAudioData(bytes);
          let max = 0;
          for (const value of buffer.getChannelData(0)) max = Math.max(max, Math.abs(value));
          return max;
        } finally { await context.close(); }
      });
      assert(peak > .001, 'Saved audio contains the synthetic microphone signal');
    }
    await login(m, 'browser_member');
    await m.goto(base + '/community-dictionaries/1/new/');
    await ready(m);
    await m.locator('[data-camera]').setInputFiles(root + '/browser-photo.png');
    await m.locator('[name=meaning]').fill('cat');
    await m.getByRole('button', {name: 'Save', exact: true}).first().click();
    await m.waitForURL(/\/entries\/\d+\/$/);
    const entry = m.url();

    await login(p, 'browser_owner');
    await p.goto(entry);
    while (await p.getByRole('button', {name: 'Accept', exact: true}).count()) {
      await Promise.all([p.waitForNavigation(), p.getByRole('button', {name: 'Accept', exact: true}).first().click()]);
    }
    const originalImage = await p.locator('.entry-image').getAttribute('src');
    await p.getByRole('link', {name: 'Edit words', exact: true}).click();
    await ready(p);
    assert.equal(await p.locator('[name=meaning]').inputValue(), 'cat');
    await p.locator('[name=word]').fill('katt');
    await p.getByRole('button', {name: 'Save', exact: true}).first().click();
    await p.waitForURL(entry);
    assert.equal(await p.locator('h1').innerText(), 'katt');
    assert.equal(await p.locator('[data-record]').isVisible(), false, 'Discussion microphone is folded behind its explicit label');
    await p.getByRole('link', {name: 'Record audio', exact: true}).click();
    await p.waitForURL(/\/record\/$/);
    const recordingURL = p.url();
    await record(p);
    await assertSound(p.locator('[data-audio-preview]'));
    await noOverflow(p);
    await p.evaluate(() => scrollTo(0, 0));
    await p.screenshot({path: root + '/record-audio-mobile.png', fullPage: true});
    await p.getByRole('button', {name: 'Save audio', exact: true}).last().click();
    await p.waitForURL(entry);
    await assertSound(p.locator('.audio-item audio'));
    assert.equal(await p.locator('.note audio').count(), 0);
    assert.equal(await p.locator('.entry-image').getAttribute('src'), originalImage);
    assert.equal(await p.locator('h1').innerText(), 'katt');
    await p.locator('.audio-item audio').evaluate(a => a.play());
    await p.waitForFunction(() => document.querySelector('.audio-item audio').currentTime > 0);
    await p.locator('.audio-item audio').evaluate(a => a.pause());
    await p.screenshot({path: root + '/entry-with-recording-mobile.png', fullPage: true});
    console.log('PASS member photo/English → editor review/Swedish → Record audio → Save audio → entry playback.');

    await p.getByRole('link', {name: 'Record audio', exact: true}).click();
    await p.waitForURL(/\/record\/$/);
    await ready(p);
    await p.locator('[name=audio]').setInputFiles(root + '/microphone-tone.wav');
    await draftSaved(p);
    await p.getByRole('button', {name: 'Logout', exact: true}).click();
    await p.getByRole('button', {name: 'Keep editing', exact: true}).click();
    assert.equal(p.url(), recordingURL);
    assert(await p.locator('[data-audio-preview]').isVisible());
    let failed = false;
    await p.route(recordingURL, async route => {
      if (route.request().method() === 'POST' && !failed) { failed = true; await route.abort('failed'); }
      else await route.continue();
    });
    await p.getByRole('button', {name: 'Logout', exact: true}).click();
    await p.getByRole('button', {name: 'Save and leave', exact: true}).click();
    await p.locator('[data-submit-error]').waitFor({state: 'visible'});
    assert.equal(p.url(), recordingURL);
    assert(await p.locator('[data-audio-preview]').isVisible());
    assert(await p.getByRole('button', {name: 'Logout', exact: true}).isVisible());
    await p.getByRole('button', {name: 'Logout', exact: true}).click();
    await p.getByRole('button', {name: 'Save and leave', exact: true}).click();
    await p.waitForURL(base + '/community-dictionaries/login/');
    await noOverflow(p);
    await p.screenshot({path: root + '/dictionary-login-mobile.png', fullPage: true});
    await login(p, 'browser_owner');
    await p.goto(entry);
    assert.equal(await p.locator('.audio-item audio').count(), 2);
    console.log('PASS logout Keep editing; failed save preserves session/audio; retry saves before POST logout.');

    await p.getByRole('link', {name: 'Record audio', exact: true}).click();
    await p.waitForURL(/\/record\/$/);
    await ready(p);
    await p.locator('[name=audio]').setInputFiles(root + '/microphone-tone.wav');
    await draftSaved(p);
    await p.getByRole('button', {name: 'Logout', exact: true}).click();
    await p.getByRole('button', {name: 'Leave without saving', exact: true}).click();
    await p.waitForURL(base + '/community-dictionaries/login/');
    await login(p, 'browser_owner');
    await p.goto(recordingURL);
    await p.waitForFunction(() => document.querySelector('[data-draft-status]').textContent.includes('restored'));
    assert(await p.locator('[data-audio-preview]').isVisible());
    await p.getByRole('button', {name: 'Save audio', exact: true}).first().click();
    await p.waitForURL(entry);
    assert.equal(await p.locator('.audio-item audio').count(), 3);

    await p.locator('[data-recorded-comment] summary').click();
    await p.locator('[name=audio]').setInputFiles(root + '/microphone-tone.wav');
    await p.locator('[name=body]').fill('A spoken discussion comment');
    await draftSaved(p);
    const commentDraftKey = await p.evaluate(() => `${document.body.dataset.user}:${new URL(document.querySelector('[data-draft-form]').action).pathname}:${location.search}`);
    await p.getByRole('button', {name: 'Logout', exact: true}).click();
    await p.getByRole('button', {name: 'Leave without saving', exact: true}).click();
    await p.waitForURL(base + '/community-dictionaries/login/');
    // Older versions stored an unchecked consent checkbox; it must not overwrite
    // the new Save comment button's explicit permission value during recovery.
    // Seed it while logged out so pagehide draft persistence cannot overwrite it.
    await p.evaluate(async key => {
      const db = await new Promise((resolve, reject) => { const r = indexedDB.open('clara-community-drafts', 1); r.onsuccess = () => resolve(r.result); r.onerror = () => reject(r.error); });
      await new Promise((resolve, reject) => {
        const t = db.transaction('drafts', 'readwrite'), store = t.objectStore('drafts'), r = store.get(key);
        r.onsuccess = () => { r.result.values.push(['consent', false]); store.put(r.result, key); };
        t.oncomplete = resolve; t.onerror = () => reject(t.error);
      });
    }, commentDraftKey);
    await login(p, 'browser_owner');
    await p.goto(entry);
    await p.waitForFunction(() => document.querySelector('[data-draft-status]').textContent.includes('restored'));
    assert(await p.locator('[data-audio-preview]').isVisible());
    assert.equal(await p.locator('[data-save-submit]').getAttribute('value'), 'on');
    await p.getByRole('button', {name: 'Save comment', exact: true}).click();
    await p.waitForFunction(() => document.querySelector('.note')?.textContent.includes('A spoken discussion comment'));
    assert.equal(await p.locator('.audio-item audio').count(), 3);
    assert.equal(await p.locator('.note audio').count(), 1);
    await noOverflow(p);
    console.log('PASS logout without saving retains recoverable draft; spoken comment stays separate and legacy consent draft restores safely.');
    await p.getByRole('button', {name: 'Logout', exact: true}).click();
    await p.waitForURL(base + '/community-dictionaries/login/');
    assert.deepEqual(errors, []);
    console.log('PASS clean logout; no uncaught browser errors; Chromium phone viewports only, not physical devices.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
