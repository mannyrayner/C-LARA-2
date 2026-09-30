// Run through browser_rehearsal.main(probe=...). Disposable accounts/media only.
const {chromium, devices} = require(process.env.COMMUNITY_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const output = process.env.COMMUNITY_BROWSER_OUTPUT;
const base = 'http://127.0.0.1:8765';

(async () => {
  const browser = await chromium.launch({headless:true,
    executablePath:process.env.COMMUNITY_CHROMIUM_PATH || undefined,
    args:['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']});
  console.log('Chromium', await browser.version(), '(phone viewports; not physical phones)');
  for (const device of ['iPhone 13', 'Pixel 7']) {
    const context = await browser.newContext({...devices[device], defaultBrowserType:undefined});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    await page.goto(base + '/accounts/login/');
    await page.locator('[name=username]').fill('browser_owner');
    await page.locator('[name=password]').fill('local-browser-trial-only');
    await page.locator('button[type=submit]').click();
    const newURL = base + '/community-dictionaries/1/new/';
    const browseURL = base + '/community-dictionaries/1/';
    const save = () => page.getByRole('button', {name:'Save', exact:true});
    const browse = () => page.getByRole('link', {name:'Browse', exact:true}).click();
    const stored = () => page.waitForFunction(() => document.querySelector('[data-draft-status]').textContent.includes('recovery draft is stored'));
    const restored = () => page.waitForFunction(() => document.querySelector('[data-draft-status]').textContent.includes('Draft restored'));
    const overflow = async () => assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));

    await page.goto(newURL);
    await save().first().waitFor();
    assert.equal(await save().count(), 2);
    const box = await save().first().boundingBox();
    assert(box.y >= 0 && box.y + box.height < devices[device].viewport.height, 'Top Save visible without scrolling');
    await page.locator('[data-camera]').setInputFiles(output + '/browser-photo.png');
    await stored();
    await page.locator('[data-photo-preview]').waitFor({state:'visible'});
    const token = await page.locator('[name=submission_id]').inputValue();
    await browse();
    await page.locator('[data-leave-dialog]').waitFor({state:'visible'});
    await overflow();
    await page.screenshot({path:output+'/'+device.replace(' ','-')+'-leave-dialog.png'});
    await page.getByRole('button', {name:'Keep editing', exact:true}).click();
    assert.equal(page.url(), newURL);
    assert(await page.locator('[data-photo-preview]').isVisible());

    // Local persistence must not suppress the native reload/Back warning.
    let warned = false;
    page.once('dialog', async dialog => { warned = dialog.type() === 'beforeunload'; await dialog.accept(); });
    await page.reload();
    assert(warned, 'Unsaved persisted draft must trigger native warning');
    await restored();
    assert.equal(await page.locator('[name=submission_id]').inputValue(), token);
    assert(await page.locator('[data-photo-preview]').isVisible());
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({path:output+'/'+device.replace(' ','-')+'-top-save.png'});

    // Leave without server-saving retains a recoverable draft; return and save.
    await browse();
    await page.getByRole('button', {name:'Leave without saving', exact:true}).click();
    await page.waitForURL(browseURL);
    await page.getByRole('link', {name:'+ Add something', exact:true}).click();
    await restored();
    assert(await page.locator('[data-photo-preview]').isVisible());
    await page.locator('[name=word]').fill(device + ' saved picture');
    await browse();
    await page.getByRole('button', {name:'Save and leave', exact:true}).click();
    await page.waitForURL(browseURL);
    await page.getByRole('heading', {name:device + ' saved picture', exact:true}).click();
    await page.locator('.entry-image').waitFor({state:'visible'});
    console.log('PASS', device, 'photo recovery, native warning, Keep editing, Leave without saving, Save and leave');

    // Bottom Save with words only, no separate consent checkbox needed.
    await page.goto(newURL);
    await page.locator('[name=word]').fill(device + ' text first');
    await save().last().click();
    await page.waitForURL(/\/entries\/\d+\/$/);
    assert.equal(await page.locator('h1').textContent(), device + ' text first');

    // Lose a successful server response; keep the same token and retry once.
    await page.goto(newURL);
    await page.locator('[data-camera]').setInputFiles(output + '/browser-photo.png');
    await page.locator('[name=word]').fill(device + ' retry');
    let intercepted = false;
    await page.route(newURL, async route => {
      if (route.request().method() === 'POST' && !intercepted) {
        intercepted = true; await route.fetch(); await route.abort('failed');
      } else await route.continue();
    });
    await save().first().click();
    await page.locator('[data-submit-error]').waitFor({state:'visible'});
    assert.equal(page.url(), newURL);
    assert(await page.locator('[data-photo-preview]').isVisible());
    await browse();
    await page.getByRole('button', {name:'Keep editing', exact:true}).click();
    await save().first().click();
    await page.waitForURL(/\/entries\/\d+\/$/);
    assert.equal(await page.locator('details.contribution').count(), 2, 'Exactly one image and one text contribution');
    await page.unroute(newURL);
    console.log('PASS', device, 'top/bottom single-click Save, permission, text-first, failed confirmation and idempotent retry');

    // Click Save while image.decode is delayed: the original is already in the
    // recovery draft, and the saved upload must await the prepared image.
    await page.goto(newURL);
    await page.evaluate(() => {
      const decode = HTMLImageElement.prototype.decode;
      HTMLImageElement.prototype.decode = async function() {
        await new Promise(resolve => setTimeout(resolve, 900));
        return decode.call(this);
      };
    });
    await page.locator('[data-camera]').setInputFiles(output + '/browser-photo.png');
    await save().first().click();
    await page.waitForURL(/\/entries\/\d+\/$/);
    await page.locator('.entry-image').waitFor({state:'visible'});
    assert.equal(await page.locator('details.contribution').count(), 1);

    // A blocked local database still allows server saving and warning on exit.
    const blocked = await browser.newContext({...devices[device], defaultBrowserType:undefined, storageState:await context.storageState()});
    await blocked.addInitScript(() => { indexedDB.open = () => { throw new Error('Storage denied for rehearsal'); }; });
    const q = await blocked.newPage();
    await q.goto(newURL);
    await q.locator('[name=word]').fill(device + ' no local storage');
    await q.getByRole('link', {name:'Browse', exact:true}).click();
    await q.getByRole('button', {name:'Save and leave', exact:true}).click();
    await q.waitForURL(browseURL);
    assert(await q.getByRole('heading', {name:device + ' no local storage', exact:true}).isVisible());
    await blocked.close();

    await page.goto(base + '/community-dictionaries/1/people/');
    await page.getByText('Invite an account or change a role', {exact:true}).click();
    const invite = page.locator('form').filter({has:page.locator('input[name=action][value=invite]')});
    await invite.locator('[name=username]').selectOption('browser_member');
    await invite.locator('[name=role]').selectOption('editor');
    await invite.getByRole('button', {name:'Save invitation or role'}).click();
    await page.waitForURL('**/people/');
    assert((await page.locator('.request-row').first().textContent()).includes('Editor'));
    await overflow();
    assert.deepEqual(errors, []);
    console.log('PASS', device, 'save during photo preparation, storage-denied fallback, invitation picker, no overflow or JavaScript errors');
    await context.close();
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
