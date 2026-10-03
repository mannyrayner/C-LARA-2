const {chromium} = require(process.env.COMMUNITY_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const base = 'http://127.0.0.1:8765/community-dictionaries/1';
const output = process.env.COMMUNITY_BROWSER_OUTPUT;
(async () => {
  const bundled = process.env.COMMUNITY_CHROMIUM_MODULE
    ? (await import(process.env.COMMUNITY_CHROMIUM_MODULE)).default : null;
  const executablePath = bundled ? await bundled.executablePath() : process.env.COMMUNITY_CHROMIUM_PATH || undefined;
  const browser = await chromium.launch({executablePath,
    headless: true, args: bundled ? bundled.args : ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']});
  try {
    const owner = await browser.newContext({viewport: {width: 390, height: 844}});
    const p = await owner.newPage(); const errors = [];
    p.on('pageerror', e => errors.push(String(e)));
    async function login(page, user) {
      await page.goto('http://127.0.0.1:8765/accounts/login/?next=/community-dictionaries/');
      await page.locator('[name=username]').fill(user);
      await page.locator('[name=password]').fill('local-browser-trial-only');
      await page.locator('button[type=submit],input[type=submit]').first().click();
      await page.waitForURL('**/community-dictionaries/');
    }
    async function screenshot(name) {
      assert(await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Horizontal overflow');
      await p.screenshot({path: `${output}/${name}.png`, fullPage: true});
    }
    await login(p, 'browser_owner');
    await p.goto(base + '/entries/1/');
    assert.equal(await p.getByRole('link', {name:'Generate a picture', exact:true}).count(), 0);
    await p.getByRole('link', {name:'Add a photo', exact:true}).click();
    assert.equal(await p.locator('[data-camera]').getAttribute('capture'), 'environment');
    await p.locator('[data-camera]').setInputFiles(output + '/browser-photo.png');
    await p.getByRole('button', {name:'Save picture', exact:true}).first().click();
    await p.waitForURL('**/entries/1/');
    const originalPhoto = await p.locator('.entry-image').getAttribute('src');
    await p.getByRole('link', {name:'Settings', exact:true}).click();
    await p.locator('[name=image_generation_enabled]').check();
    await p.getByRole('button', {name:'Save settings', exact:true}).click();
    await screenshot('dictionary-settings-mobile');
    await p.getByRole('link', {name:'Set up or view image style', exact:true}).click();
    await p.locator('[name=style_description]').fill('Clear watercolour pictures, warm natural colours, plain backgrounds.');
    await p.locator('[name=subject]').fill('A teapot');
    await p.locator('[name=ai_consent]').check();
    await screenshot('image-style-mobile');
    await p.getByRole('button', {name:'Generate style sample', exact:true}).click();
    await p.waitForURL(/\/image-preview\/[^/]+\/$/);
    await p.locator('img[alt="AI-generated preview"]').waitFor();
    await p.locator('[name=consent]').check();
    await p.getByRole('button', {name:'Approve this style', exact:true}).click();
    await p.waitForURL('**/image-style/');
    await p.goto(base + '/entries/1/');
    await p.getByRole('link', {name:'Generate a picture', exact:true}).click();
    await p.locator('[name=subject]').fill('A blue teapot on a kitchen table');
    await p.locator('[name=ai_consent]').check();
    await screenshot('image-entry-form-mobile');
    await p.getByRole('button', {name:'Generate picture preview', exact:true}).click();
    await p.waitForURL(/\/image-preview\/[^/]+\/$/);
    await screenshot('image-preview-mobile');
    await p.locator('[name=consent]').check();
    await p.getByRole('button', {name:'Save picture to entry', exact:true}).click();
    await p.waitForURL('**/entries/1/');
    assert((await p.locator('main').textContent()).includes('AI-generated picture'));
    assert.equal(await p.locator('.entry-image').getAttribute('src'), originalPhoto);
    assert(await p.locator('.entry-image').evaluate(img => img.complete && img.naturalWidth > 0));
    await screenshot('image-saved-mobile');
    await p.setViewportSize({width:1280,height:900});
    await screenshot('image-saved-desktop');
    // With AI enabled, create another text-only entry and add an ordinary upload.
    await p.setViewportSize({width:320,height:740});
    await p.getByRole('link', {name:'+ Contribute', exact:true}).click();
    await p.locator('[name=word]').fill('kaffekopp');
    await p.locator('[name=meaning]').fill('coffee cup');
    await p.getByRole('button', {name:'Save', exact:true}).first().click();
    await p.waitForURL(/\/entries\/\d+\/$/);
    const textEntryUrl=p.url();
    await screenshot('text-first-entry-320');
    await p.getByRole('link', {name:'Add a photo', exact:true}).click();
    await p.locator('input[name=photo]:not([data-camera])').setInputFiles(output + '/browser-photo.png');
    await screenshot('add-photo-320');
    await p.getByRole('button', {name:'Save picture', exact:true}).last().click();
    await p.waitForURL(textEntryUrl);
    assert.equal(await p.locator('h1').innerText(), 'kaffekopp');
    assert(await p.locator('.entry-image').evaluate(img => img.complete && img.naturalWidth > 0));
    const member = await browser.newContext({viewport:{width:390,height:844}});
    const m = await member.newPage(); await login(m, 'browser_member');
    await m.goto(base + '/entries/1/');
    assert.equal(await m.getByRole('link', {name:'Generate a picture', exact:true}).count(), 0);
    assert.equal(await m.getByRole('link', {name:'Settings', exact:true}).count(), 0);
    assert.equal(await m.getByRole('link', {name:'Add a photo', exact:true}).count(), 1);
    assert(await m.locator('.entry-image').evaluate(img => img.complete && img.naturalWidth > 0));
    assert.deepEqual(errors, []);
    console.log('PASS Settings, text-first camera/upload with AI off/on, preserved original picture, generated preview/save, member controls, 320px/390px/1280px layout; mocked provider');
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exit(1);});
