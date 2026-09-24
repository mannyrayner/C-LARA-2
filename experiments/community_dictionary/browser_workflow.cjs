const {chromium, devices} = require(process.env.COMMUNITY_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const root = process.env.COMMUNITY_BROWSER_OUTPUT;
assert(root, 'Run this probe through browser_rehearsal.py');
const base = 'http://127.0.0.1:8765';

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.COMMUNITY_CHROMIUM_PATH || undefined,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu',
      '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
      `--use-file-for-fake-audio-capture=${root}/microphone-tone.wav`],
  });
  console.log('Browser', await browser.version());
  const owner = await browser.newContext({...devices['iPhone 13'], defaultBrowserType: undefined, permissions: ['microphone']});
  const member = await browser.newContext({...devices['Pixel 7'], defaultBrowserType: undefined, permissions: ['microphone']});
  // Keep native capture, MediaRecorder and Web Audio. Only inject denial or mute the native track.
  await member.addInitScript(() => {
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    window.microphoneProbe = {mode: 'normal', streams: [], constraints: []};
    navigator.mediaDevices.getUserMedia = async constraints => {
      const probe = window.microphoneProbe;
      probe.constraints.push(constraints);
      if (probe.mode === 'denied') throw new DOMException('Simulated permission denial', 'NotAllowedError');
      const stream = await original(constraints);
      if (probe.mode === 'silent') stream.getAudioTracks().forEach(track => { track.enabled = false; });
      probe.streams.push(stream);
      return stream;
    };
  });
  const p = await owner.newPage(), m = await member.newPage();
  const errors = [];
  for (const page of [p, m]) page.on('pageerror', e => errors.push(String(e)));
  async function login(page, name) {
    await page.goto(base + '/accounts/login/?next=/community-dictionaries/');
    await page.locator('[name=username]').fill(name);
    await page.locator('[name=password]').fill('local-browser-trial-only');
    await page.locator('button[type=submit],input[type=submit]').first().click();
    await page.waitForURL('**/community-dictionaries/');
  }
  async function draftSaved(page) {
    await page.waitForFunction(() => document.querySelector('[data-draft-status]').textContent.includes('Draft saved'));
  }
  async function noOverflow(page) {
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Horizontal overflow at ' + page.url());
  }
  async function audioInfo(locator) {
    return locator.evaluate(async element => {
      const blob = await (await fetch(element.src)).blob();
      const bytes = await blob.arrayBuffer();
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))).join(',');
      const context = new AudioContext();
      try {
        const buffer = await context.decodeAudioData(bytes);
        let peak = 0;
        for (let c = 0; c < buffer.numberOfChannels; c++) {
          for (const value of buffer.getChannelData(c)) peak = Math.max(peak, Math.abs(value));
        }
        return {peak, duration: buffer.duration, mime: blob.type, size: blob.size, digest};
      } finally { await context.close(); }
    });
  }
  async function recordTake(page) {
    await page.locator('[data-record]').click();
    await page.waitForFunction(() => document.querySelector('[data-record-state]').textContent.includes('Recording… 1'));
    await page.locator('[data-record]').click();
    await page.waitForFunction(() => !document.querySelector('[data-record]').disabled);
  }
  await login(p, 'browser_owner'); await login(m, 'browser_member');
  await p.goto(base + '/community-dictionaries/1/new/');
  for (const name of ['word', 'meaning', 'category']) assert(await p.locator(`[name=${name}]`).isVisible());
  assert.equal(await p.getByLabel('Word or phrase in Swedish (optional)').count(), 1);
  assert.equal(await p.getByLabel('Meaning or translation in English (optional)').count(), 1);
  await p.locator('[data-camera]').setInputFiles(root + '/browser-photo.png');
  await p.locator('[name=consent]').check(); await draftSaved(p);
  const token = await p.locator('[name=submission_id]').inputValue();
  await p.reload(); await p.waitForFunction(() => document.querySelector('[data-draft-status]').textContent.includes('restored'));
  assert.equal(await p.locator('[name=submission_id]').inputValue(), token);
  assert(await p.locator('[name=consent]').isChecked()); assert(await p.locator('[data-photo-preview]').isVisible());
  await noOverflow(p); await p.evaluate(() => scrollTo(0, 0));
  await p.screenshot({path: root + '/community-contribute-mobile.png', fullPage: true});
  let intercepted = false;
  await p.route('**/community-dictionaries/1/new/', async route => {
    if (route.request().method() === 'POST' && !intercepted) {
      intercepted = true; await route.fetch(); await route.abort('failed');
    } else await route.continue();
  });
  await p.getByRole('button', {name: 'Share contribution', exact: true}).click();
  await p.locator('[data-submit-error]').waitFor({state: 'visible'});
  assert((await p.locator('[data-draft-status]').textContent()).includes('Not confirmed'));
  await p.getByRole('button', {name: 'Share contribution', exact: true}).click();
  await p.waitForURL(/\/entries\/\d+\/$/);
  const entryUrl = p.url(); assert.equal(await p.locator('details.contribution').count(), 1);
  console.log('PASS optional visible words, photo draft restore and lost-confirmation retry');
  await p.getByRole('link', {name: 'Ask partners', exact: true}).click();
  await p.locator('[name=partnership]').selectOption({label: 'Everyday Swedish'});
  await p.locator('[name=kind]').selectOption('audio'); await p.locator('[name=note]').fill('Vad heter detta?');
  await p.getByRole('button', {name: 'Send request to group', exact: true}).click(); await p.waitForURL(entryUrl);
  await m.goto(base + '/community-dictionaries/1/requests/');
  await m.locator('.queue-card').filter({has: m.locator('a[href="' + new URL(entryUrl).pathname + '"]')}).getByRole('link', {name: 'Add recording', exact: true}).click();

  await m.evaluate(() => { microphoneProbe.mode = 'denied'; });
  await m.locator('[data-check-mic]').click();
  await m.waitForFunction(() => document.querySelector('[data-record-notice]').textContent.includes('not allowed'));
  assert(await m.locator('[data-record]').isEnabled());
  await m.evaluate(() => { microphoneProbe.mode = 'normal'; });
  await m.waitForFunction(() => document.querySelector('[data-microphone]').options.length > 1);
  const deviceId = await m.locator('[data-microphone] option').last().getAttribute('value');
  await m.locator('[data-microphone]').selectOption(deviceId);
  await m.locator('[data-check-mic]').click();
  await m.waitForFunction(() => document.querySelector('[data-mic-level]').value > 0);
  assert.equal(await m.evaluate(() => microphoneProbe.constraints.at(-1).audio.deviceId.exact), deviceId);
  assert((await m.locator('[data-microphone-name]').textContent()).includes('Using:'));
  await noOverflow(m); await m.screenshot({path: root + '/community-microphone-mobile.png', fullPage: true});
  await m.locator('[data-check-mic]').click();
  await m.waitForFunction(() => !document.querySelector('[data-record]').disabled);
  assert(await m.evaluate(() => microphoneProbe.streams.every(stream => stream.getTracks().every(track => track.readyState === 'ended'))));
  await recordTake(m);
  await m.locator('[data-audio-preview]').waitFor({state: 'visible'});
  const first = await audioInfo(m.locator('[data-audio-preview]'));
  assert(first.peak > 0.001 && first.duration > 0.5, 'Recorded audio must contain sound');
  console.log('PASS denial recovery, selected device, moving meter, stopped tracks; recorded', {mime: first.mime, peak: first.peak, duration: first.duration});

  await m.evaluate(() => { microphoneProbe.mode = 'silent'; });
  await recordTake(m);
  assert((await m.locator('[data-record-state]').textContent()).includes('Silent recording'));
  assert.equal((await audioInfo(m.locator('[data-audio-preview]'))).digest, first.digest, 'Silent retake must preserve the previous file');
  await m.locator('[name=consent]').check(); await draftSaved(m);
  await m.reload(); await m.waitForFunction(() => document.querySelector('[data-draft-status]').textContent.includes('restored'));
  assert.equal((await audioInfo(m.locator('[data-audio-preview]'))).digest, first.digest);
  console.log('PASS silent take rejected and previous audible take preserved through reload');
  await m.getByRole('button', {name: 'Share contribution', exact: true}).click(); await m.waitForURL(entryUrl); await noOverflow(m);
  await m.locator('[name=body]').fill('Är det samma ord i din dialekt?');
  await m.getByRole('button', {name: 'Add comment', exact: true}).click();
  await m.waitForFunction(() => document.querySelector('.note')?.textContent.includes('din dialekt'));
  await p.goto(entryUrl); await p.getByRole('button', {name: 'Accept', exact: true}).click();
  await p.waitForFunction(() => document.querySelector('.request-row')?.textContent.includes('complete'));
  const player = p.locator('.audio-item audio');
  assert.equal((await audioInfo(player)).digest, first.digest);
  await player.evaluate(a => a.play()); await p.waitForFunction(() => document.querySelector('.audio-item audio').currentTime > 0);
  await player.evaluate(a => a.pause());
  console.log('PASS group request, audio draft recovery, discussion, acceptance and saved audio playback');

  const imageUrl = await p.locator('.entry-image').getAttribute('src');
  const audioUrl = await player.getAttribute('src');
  await p.getByRole('link', {name: 'Add words', exact: true}).click();
  await p.locator('[name=word]').fill('katt'); await p.locator('[name=meaning]').fill('cat');
  await p.locator('[name=category]').fill('Animals');
  await p.getByRole('button', {name: 'Save words', exact: true}).click(); await p.waitForURL(entryUrl);
  assert.equal(await p.locator('h1').textContent(), 'katt');
  assert.equal(await p.locator('.entry-image').getAttribute('src'), imageUrl);
  assert.equal(await p.locator('.audio-item audio').getAttribute('src'), audioUrl);
  await noOverflow(p); await p.evaluate(() => scrollTo(0, 0));
  await p.screenshot({path: root + '/community-entry-mobile.png', fullPage: true});
  for (const q of ['katt', 'cat']) {
    await p.goto(base + '/community-dictionaries/1/?q=' + q + '&category=Animals');
    assert.equal(await p.locator('.entry-card').count(), 1);
    assert((await p.locator('.entry-card').textContent()).includes('katt'));
  }
  console.log('PASS adding Swedish word, English translation and category preserves media; either language finds the entry');
  await m.goto(base + '/community-dictionaries/1/requests/?show=history');
  await noOverflow(m); await m.evaluate(() => scrollTo(0, 0));
  await m.screenshot({path: root + '/community-queue-mobile.png', fullPage: true});
  await p.setViewportSize({width: 1440, height: 1000}); await p.goto(base + '/community-dictionaries/1/');
  await noOverflow(p); await p.evaluate(() => scrollTo(0, 0));
  await p.screenshot({path: root + '/community-browse-desktop.png', fullPage: true});
  assert.deepEqual(errors, []); console.log('PASS no uncaught JavaScript errors and no horizontal overflow on checked pages');
  await browser.close();
})().catch(error => {console.error(error); process.exit(1);});
