// Run against browser_rehearsal.py's disposable database and synthetic media.
const {chromium, devices} = require(process.env.COMMUNITY_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const root = process.env.COMMUNITY_BROWSER_OUTPUT;
const base = 'http://127.0.0.1:8765/community-dictionaries/';
(async () => {
  const browser = await chromium.launch({executablePath:process.env.COMMUNITY_CHROMIUM_PATH || undefined,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
  try {
    const owner = await browser.newContext({...devices['Pixel 7']});
    const member = await browser.newContext({...devices['iPhone 13'],defaultBrowserType:undefined});
    const p=await owner.newPage(), m=await member.newPage(), errors=[];
    for (const page of [p,m]) { page.setDefaultTimeout(15000); page.on('pageerror', e=>errors.push(String(e))); page.on('dialog', d=>d.accept()); }
    const login = async(page,name) => {await page.goto(base+'login/'); await page.locator('[name=username]').fill(name); await page.locator('[name=password]').fill('local-browser-trial-only'); await page.getByRole('button',{name:'Log in',exact:true}).click(); await page.waitForURL(base);};
    const ready = page=>page.waitForFunction(()=>!document.querySelector('[data-save-submit]').disabled);
    const noOverflow = async page=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await login(m,'browser_member'); await login(p,'browser_owner');
    await m.goto(base+'1/new/'); await ready(m); await m.locator('[data-camera]').setInputFiles(root+'/browser-photo.png'); await m.locator('[name=meaning]').fill('sofa');
    await m.getByRole('button',{name:'Save',exact:true}).first().click(); await m.waitForURL(/entries\/\d+\/$/); const entry=m.url();
    await p.goto(entry);
    for(let i=0;i<2;i++){await p.getByRole('button',{name:'Accept',exact:true}).first().click();await p.waitForURL(entry);}
    await p.getByRole('link',{name:'Edit words',exact:true}).click();await ready(p);await p.locator('[name=word]').fill('soffa');await p.locator('[name=category]').fill('Home');
    await p.getByRole('button',{name:'Save',exact:true}).first().click();await p.waitForURL(entry);
    assert.equal(await p.locator('h1').innerText(),'soffa');
    assert(await p.locator('details.contribution>summary').filter({hasText:'Translation or explanation · browser_member'}).count());
    await noOverflow(p);await p.screenshot({path:root+'/entry-provenance-mobile.png',fullPage:true});
    await p.goto(base+'1/people/');await p.getByRole('button',{name:'Make inactive',exact:true}).click();await p.waitForURL(base+'1/people/');
    assert.equal((await m.goto(entry)).status(),404);
    await m.goto(base+'my-contributions/');await noOverflow(m);
    await m.locator('[name=dictionary]').selectOption('1');await m.locator('[name=kind]').selectOption('text');await m.getByRole('button',{name:'Show',exact:true}).click();
    await m.getByRole('button',{name:'Withdraw all matching material',exact:true}).click();await m.waitForURL(/view=private/);
    assert(await m.locator('.contribution-grid').innerText().then(s=>s.includes('sofa')));await noOverflow(m);
    await m.screenshot({path:root+'/private-collection-mobile.png',fullPage:true});
    await p.goto(entry);assert.equal(await p.locator('.meaning').count(),0);assert.equal(await p.locator('h1').innerText(),'soffa');
    await p.goto(base+'1/people/');await p.getByRole('button',{name:'Reactivate membership',exact:true}).click();await p.waitForURL(base+'1/people/');
    await m.goto(base+'my-contributions/?view=private');await m.locator('[name=contributions]').first().check();await m.getByRole('button',{name:'Share selected…',exact:true}).first().click();
    await m.locator('[name=target_dictionary]').selectOption('1');await m.getByRole('button',{name:"Show this dictionary's entries",exact:true}).click();
    await m.locator('[name=target_entry]').selectOption(entry.match(/entries\/(\d+)/)[1]);await m.locator('[name=consent]').check();await noOverflow(m);await m.screenshot({path:root+'/share-from-collection-mobile.png',fullPage:true});
    await m.getByRole('button',{name:'Share for review',exact:true}).click();await m.waitForURL(entry);
    await p.goto(entry);await p.getByRole('button',{name:'Accept',exact:true}).click();await p.waitForURL(entry);assert.equal(await p.locator('.meaning').innerText(),'sofa');
    await p.setViewportSize({width:1360,height:1000});await p.goto(base+'1/people/');await noOverflow(p);await p.screenshot({path:root+'/membership-desktop.png',fullPage:true});
    assert.deepEqual(errors,[]);console.log('PASS independent attribution, phone layout, inactive-member withdrawal, reactivation, explicit resharing and review.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
