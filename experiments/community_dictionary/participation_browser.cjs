// Real HTTP/CSRF forms, disposable SQLite and synthetic media only.
const {chromium, devices} = require(process.env.COMMUNITY_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const root=process.env.COMMUNITY_BROWSER_OUTPUT, base='http://127.0.0.1:8765/community-dictionaries/';
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.COMMUNITY_CHROMIUM_PATH || undefined,headless:true,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 try{
  const owner=await browser.newContext({...devices['Pixel 7']}), member=await browser.newContext({...devices['iPhone 13'],defaultBrowserType:undefined});
  const p=await owner.newPage(),m=await member.newPage(),errors=[],dialogs=[];
  for(const page of [p,m]){page.setDefaultTimeout(15000);page.on('pageerror',e=>errors.push(String(e)));page.on('dialog',d=>{dialogs.push(d.message());d.accept();});}
  const login=async(page,user)=>{await page.goto(base+'login/');await page.locator('[name=username]').fill(user);await page.locator('[name=password]').fill('local-browser-trial-only');await page.getByRole('button',{name:'Log in',exact:true}).click();await page.waitForURL(base);};
  const ready=page=>page.waitForFunction(()=>!document.querySelector('[data-save-submit]').disabled);
  const noOverflow=async page=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await login(m,'browser_member');await login(p,'browser_owner');
  await m.goto(base+'1/new/');await ready(m);await m.locator('[data-camera]').setInputFiles(root+'/browser-photo.png');await m.locator('[name=meaning]').fill('sofa');
  await m.getByRole('button',{name:'Save',exact:true}).first().click();await m.waitForURL(/entries\/\d+\/$/);const entry=m.url();
  await p.goto(entry);for(let i=0;i<2;i++){await p.getByRole('button',{name:'Accept',exact:true}).first().click();await p.waitForURL(entry);}
  await p.getByRole('link',{name:'Edit words',exact:true}).click();await ready(p);await p.locator('[name=word]').fill('soffa');await p.locator('[name=category]').fill('Home');
  await p.getByRole('button',{name:'Save',exact:true}).first().click();await p.waitForURL(entry);
  await p.getByRole('link',{name:'Record audio',exact:true}).click();await ready(p);await p.locator('input[type=file][name=audio]').setInputFiles(root+'/microphone-tone.wav');
  await p.getByRole('button',{name:'Save audio',exact:true}).first().click();await p.waitForURL(entry);
  await m.goto(base+'1/');await noOverflow(m);await m.screenshot({path:root+'/participating-dictionary-mobile.png',fullPage:true});
  await m.getByRole('link',{name:'View my contributions',exact:true}).click();
  assert.equal(await m.locator('[name=contributions]').count(),0);assert.equal(await m.locator('.collection-entry').count(),1);
  assert((await m.locator('main').innerText()).includes('soffa'));assert.equal(await m.locator('.reference-component audio').count(),1);
  await m.screenshot({path:root+'/participating-content-mobile.png',fullPage:true});
  await m.getByRole('link',{name:'Withdraw my content',exact:true}).click();
  assert.equal(await m.getByRole('button',{name:'Confirm withdrawal',exact:true}).count(),1);
  await m.getByRole('link',{name:'Cancel',exact:true}).click();await m.waitForURL(base+'1/');
  assert.equal(await m.getByRole('button',{name:'Restore my content',exact:true}).count(),0);
  await m.getByRole('link',{name:'Withdraw my content',exact:true}).click();
  await noOverflow(m);await m.screenshot({path:root+'/withdraw-confirmation-mobile.png',fullPage:true});
  await m.getByRole('button',{name:'Confirm withdrawal',exact:true}).click();await m.waitForURL(base+'1/');
  assert((await m.locator('main').innerText()).includes('Your content is withdrawn'));
  assert(!(await m.locator('main').innerText()).includes('soffa'));assert.equal(await m.locator('.dictionary-nav').count(),0);
  await noOverflow(m);await m.screenshot({path:root+'/withdrawn-dictionary-mobile.png',fullPage:true});
  await p.goto(entry);assert.equal(await p.locator('.entry-image').count(),0);assert(!(await p.locator('main').innerText()).includes('>sofa<'));
  await m.getByRole('link',{name:'View my saved content',exact:true}).click();
  assert.equal(await m.locator('.reference-component').count(),0);assert.equal(await m.locator('[name=contributions]').count(),0);
  assert((await m.locator('main').innerText()).includes('sofa'));assert(!(await m.locator('main').innerText()).includes('soffa'));
  await noOverflow(m);await m.screenshot({path:root+'/saved-content-mobile.png',fullPage:true});
  assert.equal((await m.request.get(entry)).status(),404);assert.equal((await m.request.get(base+'1/new/')).status(),404);
  await m.goto(base);await noOverflow(m);await m.screenshot({path:root+'/withdrawn-home-mobile.png',fullPage:true});
  dialogs.length=0;await m.getByRole('button',{name:'Restore my content',exact:true}).click();await m.waitForURL(base+'1/');assert.deepEqual(dialogs,[]);
  await p.goto(entry);assert(await p.locator('.entry-image').evaluate(el=>el.complete&&el.naturalWidth>0));assert.equal(await p.getByRole('button',{name:'Accept',exact:true}).count(),0);
  // Repeat a full cycle. Return must move the same contribution, not add copies.
  await m.getByRole('link',{name:'Withdraw my content',exact:true}).click();await m.getByRole('button',{name:'Confirm withdrawal',exact:true}).click();await m.waitForURL(base+'1/');
  await m.getByRole('button',{name:'Restore my content',exact:true}).click();await m.waitForURL(base+'1/');
  await p.goto(entry);assert.equal(await p.locator('img.candidate-image').count(),1);
  // Owner hands over explicitly; returning must not take ownership back.
  await p.setViewportSize({width:1360,height:1000});await p.goto(base+'1/');await p.getByRole('link',{name:'Withdraw my content',exact:true}).click();
  await p.locator('[name=successor]').selectOption({label:'browser_member'});await noOverflow(p);
  await p.screenshot({path:root+'/owner-handover-desktop.png',fullPage:true});
  await p.getByRole('button',{name:'Confirm withdrawal',exact:true}).click();await p.waitForURL(base+'1/');
  await m.goto(base+'1/people/');assert((await m.locator('main').innerText()).includes('browser_member Owner'));
  await p.getByRole('button',{name:'Restore my content',exact:true}).click();await p.waitForURL(base+'1/');
  assert.equal((await p.request.get(base+'1/export/')).status(),404);
  await m.goto(base+'1/people/');assert((await m.locator('main').innerText()).includes('browser_member Owner'));
  assert.deepEqual(errors,[]);console.log('PASS dictionary-level withdraw/restore, confirmation/cancel, read-only private viewing, home status, access denial, immediate approval, repeat cycles without copies, ownership handover and responsive layouts.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
