// Disposable database and synthetic media: prominent return-to-original controls.
const {chromium, devices} = require(process.env.COMMUNITY_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const root = process.env.COMMUNITY_BROWSER_OUTPUT;
const base = 'http://127.0.0.1:8765/community-dictionaries/';
(async () => {
  const browser = await chromium.launch({executablePath:process.env.COMMUNITY_CHROMIUM_PATH || undefined,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
  try {
    const owner = await browser.newContext({...devices['Pixel 7']});
    const member = await browser.newContext({...devices['iPhone 13'],defaultBrowserType:undefined});
    const p=await owner.newPage(), m=await member.newPage(), errors=[], dialogs=[];
    for (const page of [p,m]) {page.setDefaultTimeout(15000);page.on('pageerror',e=>errors.push(String(e)));page.on('dialog',d=>{dialogs.push(d.message());d.accept();});}
    const login=async(page,name)=>{await page.goto(base+'login/');await page.locator('[name=username]').fill(name);await page.locator('[name=password]').fill('local-browser-trial-only');await page.getByRole('button',{name:'Log in',exact:true}).click();await page.waitForURL(base);};
    const ready=page=>page.waitForFunction(()=>!document.querySelector('[data-save-submit]').disabled);
    const noOverflow=async page=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    const ownOnly=async page=>assert.equal(await page.locator('.reference-component [name=contributions]').count(),0);
    await login(m,'browser_member');await login(p,'browser_owner');
    await m.goto(base+'1/new/');await ready(m);await m.locator('[data-camera]').setInputFiles(root+'/browser-photo.png');await m.locator('[name=meaning]').fill('sofa');
    await m.getByRole('button',{name:'Save',exact:true}).first().click();await m.waitForURL(/entries\/\d+\/$/);const entry=m.url();
    await p.goto(entry);
    for(let i=0;i<2;i++){await p.getByRole('button',{name:'Accept',exact:true}).first().click();await p.waitForURL(entry);}
    await p.getByRole('link',{name:'Edit words',exact:true}).click();await ready(p);await p.locator('[name=word]').fill('soffa');await p.locator('[name=category]').fill('Home');
    await p.getByRole('button',{name:'Save',exact:true}).first().click();await p.waitForURL(entry);
    await p.getByRole('link',{name:'Record audio',exact:true}).click();await ready(p);await p.locator('input[type=file][name=audio]').setInputFiles(root+'/microphone-tone.wav');
    await p.getByRole('button',{name:'Save audio',exact:true}).first().click();await p.waitForURL(entry);
    await m.goto(base+'my-contributions/');await noOverflow(m);await ownOnly(m);
    assert.equal(await m.locator('.collection-entry').count(),1);
    assert.equal(await m.locator('.collection-entry h2').innerText(),'soffa');
    assert.equal(await m.locator('[name=contributions]').count(),2);
    assert.equal(await m.locator('.reference-component').count(),3);
    const audio=m.locator('.reference-component audio');assert.equal(await audio.count(),1);
    await audio.evaluate(async el=>{await el.play();el.pause();});
    await m.screenshot({path:root+'/contributions-member-mobile.png',fullPage:true});
    await p.setViewportSize({width:1360,height:1000});await p.goto(base+'my-contributions/');await noOverflow(p);await ownOnly(p);
    assert.equal(await p.locator('[name=contributions]').count(),3);
    await p.screenshot({path:root+'/contributions-owner-desktop.png',fullPage:true});
    await m.locator('[name=kind]').selectOption('image');await m.getByRole('button',{name:'Show',exact:true}).click();
    assert.equal(await m.locator('[name=contributions]').count(),1);assert.equal(await m.locator('.collection-entry h2').innerText(),'soffa');
    await m.locator('[name=contributions]').check();await m.getByRole('button',{name:'Withdraw selected',exact:true}).first().click();await m.waitForURL(/view=private/);
    assert.equal(await m.locator('.collection-entry h2').innerText(),'soffa');await ownOnly(m);await noOverflow(m);
    assert.equal(await m.locator('[name=contributions]').count(),1);await m.screenshot({path:root+'/private-context-mobile.png',fullPage:true});
    const privateURL=await m.getByRole('link',{name:'Open private entry',exact:false}).getAttribute('href');
    dialogs.length=0;
    const restore=m.getByRole('button',{name:'Share back to the original dictionary',exact:true});
    assert.equal(await restore.evaluate(el=>el.form.querySelectorAll('[name=restore_snapshot]').length),1);
    assert.equal(await restore.evaluate(el=>el.form.querySelectorAll('[name=contributions]').length),0);
    // One click submits only this card, never the bulk-selection form.
    await restore.click();await m.waitForURL(entry);
    assert.deepEqual(dialogs,[]);
    assert((await m.locator('main > .notice[role=status]').innerText()).includes('Restored to the original entry'));
    assert(!(await m.locator('main > .notice[role=status]').innerText()).includes('review'));
    assert(await m.locator('.entry-image').evaluate(el=>el.complete && el.naturalWidth>0));
    await noOverflow(m);await m.screenshot({path:root+'/restored-entry-mobile.png',fullPage:true});
    await p.goto(entry);assert.equal(await p.getByRole('button',{name:'Accept',exact:true}).count(),0);
    assert(await p.locator('.entry-image').evaluate(el=>el.complete && el.naturalWidth>0));
    await m.goto(new URL(privateURL,base).href);
    assert.equal(await m.getByRole('button',{name:'Share back to the original dictionary',exact:true}).count(),0);
    assert.equal(await m.getByRole('link',{name:'Open original entry',exact:false}).count(),1);
    // Withdraw again, then exercise the button on the private entry itself.
    await m.goto(entry);
    const imagePanel=m.locator('details.contribution').filter({has:m.locator('img.candidate-image')});
    await imagePanel.locator('summary').click();
    await imagePanel.getByRole('button',{name:'Withdraw to my collection',exact:true}).click();await m.waitForURL(/view=private/);
    await m.getByRole('link',{name:'Open private entry',exact:false}).click();
    const prominent=m.getByRole('button',{name:'Share back to the original dictionary',exact:true});
    assert.equal(await prominent.count(),1);assert.equal(await prominent.evaluate(el=>!!el.closest('details')),false);
    await noOverflow(m);await m.screenshot({path:root+'/private-entry-restore-mobile.png',fullPage:true});
    dialogs.length=0;await prominent.click();await m.waitForURL(entry);assert.deepEqual(dialogs,[]);
    await p.goto(entry);assert.equal(await p.getByRole('button',{name:'Accept',exact:true}).count(),0);
    assert.equal(await p.locator('img.candidate-image').count(),1);
    // A page opened before membership revocation must not restore anything.
    await m.locator('details.contribution').filter({has:m.locator('img.candidate-image')}).locator('summary').click();
    await m.getByRole('button',{name:'Withdraw to my collection',exact:true}).first().click();await m.waitForURL(/view=private/);
    await p.goto(base+'1/people/');await p.getByRole('button',{name:'Make inactive',exact:true}).click();await p.waitForURL(base+'1/people/');
    await m.getByRole('button',{name:'Share back to the original dictionary',exact:true}).click();
    assert((await m.locator('main').innerText()).includes('Sharing back is unavailable'));
    assert(!(await m.locator('main').innerText()).includes('soffa'));
    await noOverflow(m);
    assert.deepEqual(errors,[]);console.log('PASS one-click restoration from collection and private entry; no confirmation dialogs; immediate acceptance visible to another member; retained private copies; repeated withdrawal/restoration; stale-page access revocation; correct form ownership and mobile/desktop layout.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
