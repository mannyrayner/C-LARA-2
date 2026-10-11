const {chromium}=require(process.env.COMMUNITY_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const output=process.env.COMMUNITY_BROWSER_OUTPUT, root='http://127.0.0.1:8773/community-dictionaries';
(async()=>{
 const bundled=process.env.COMMUNITY_CHROMIUM_MODULE?(await import(process.env.COMMUNITY_CHROMIUM_MODULE)).default:null;
 const browser=await chromium.launch({executablePath:bundled?await bundled.executablePath():process.env.COMMUNITY_CHROMIUM_PATH||undefined,headless:true,args:bundled?bundled.args:['--no-sandbox']});
 try{
  const ownerContext=await browser.newContext({viewport:{width:390,height:844}}),owner=await ownerContext.newPage();
  const errors=[];owner.on('pageerror',e=>errors.push(String(e)));
  async function shot(page,name){
   await page.evaluate(()=>scrollTo(0,0));
   await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Horizontal overflow: '+name);
   await page.screenshot({path:output+'/'+name+'.png',fullPage:true});
  }
  await owner.goto(root+'/login/');
  await owner.locator('#id_username').fill('owner');await owner.locator('#id_password').fill('browser-test-password-948');
  await owner.getByRole('button',{name:'Log in',exact:true}).click();await owner.waitForURL(root+'/');
  await owner.goto(root+'/1/settings/');await shot(owner,'owner-disabled-390');
  await owner.getByRole('button',{name:'Make dictionary discoverable',exact:true}).click();
  await owner.locator('#id_permission').check();await owner.getByRole('button',{name:'Enable public browsing',exact:true}).click();
  await owner.getByRole('button',{name:'Turn off public browsing',exact:true}).waitFor();
  await shot(owner,'owner-enabled-390');assert.equal(await owner.locator('#public-link').inputValue(),root+'/browse/1/');
  let savedMedia;
  for(const width of [320,390,1280]){
   const context=await browser.newContext({viewport:{width,height:844}}),page=await context.newPage();
   page.on('pageerror',e=>errors.push(String(e)));
   await page.goto(root+'/login/');await page.getByRole('link',{name:'Browse without logging in',exact:true}).click();
   assert(!(await page.locator('body').innerText()).includes('PRIVATE-DICTIONARY'));
   await shot(page,'visitor-list-'+width);
   await page.getByRole('link',{name:'Browse',exact:true}).click();await shot(page,'visitor-pictures-'+width);
   await page.getByRole('link',{name:'Sentences',exact:true}).click();
   await page.getByRole('heading',{name:'En växt står på bordet.',exact:true}).click();
   await page.getByRole('heading',{name:'Words for this picture',exact:true}).waitFor();
   for(const forbidden of ['PRIVATE-DRAFT','PRIVATE-DISCUSSION','Describe this picture','Settings','Show more options'])
    assert(!(await page.locator('body').innerText()).includes(forbidden),forbidden);
   const row=page.locator('[data-word-row]').filter({has:page.getByRole('heading',{name:'växt',exact:true})});
   await row.getByText('Translation',{exact:true}).click();await row.getByText('plant',{exact:true}).waitFor();
   await row.getByRole('button',{name:'Listen to växt',exact:true}).click();
   await page.waitForFunction(()=>[...document.querySelectorAll('audio')].some(a=>a.currentTime>0));
   savedMedia=await row.locator('audio').getAttribute('src');await shot(page,'visitor-sentence-'+width);
   await row.getByRole('link',{name:'Word page →',exact:true}).click();
   await page.getByRole('heading',{name:'Pictures for this word',exact:true}).waitFor();
   await shot(page,'visitor-word-'+width);
   await page.getByRole('link',{name:'En växt står på bordet.',exact:true}).click();
   assert((await page.locator('h1').innerText()).includes('En växt'));
   await page.goto(root+'/browse/1/?view=words&q=plant');assert.equal(await page.locator('[data-word-row]').count(),1);
   const exportResponse=await page.request.get(root+'/1/export/');
   assert.equal(exportResponse.status(),200);
   assert(exportResponse.url().includes('/login/'),'Export must redirect to login');
   assert(exportResponse.headers()['content-type'].includes('text/html'));
   // Keep contexts alive until browser.close(); single-process Chromium can
   // terminate when an isolated context is closed while others are in use.
  }
  await owner.getByRole('button',{name:'Turn off public browsing',exact:true}).click();
  const guest=await browser.newPage();assert.equal((await guest.goto(root+'/browse/1/')).status(),404);
  assert.equal((await guest.request.get('http://127.0.0.1:8773'+savedMedia)).status(),404);
  await shot(guest,'visitor-revoked-1280');assert.deepEqual(errors,[]);
  console.log('Passed owner enable/revoke plus visitor search, translations, audio, word/sentence links and 320/390/1280px layouts.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
