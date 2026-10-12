const {chromium}=require(process.env.COMMUNITY_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const output=process.env.COMMUNITY_BROWSER_OUTPUT, root='http://127.0.0.1:8773/community-dictionaries';
(async()=>{
 const bundled=process.env.COMMUNITY_CHROMIUM_MODULE?(await import(process.env.COMMUNITY_CHROMIUM_MODULE)).default:null;
 const browser=await chromium.launch({executablePath:bundled?await bundled.executablePath():undefined,headless:true,args:bundled?bundled.args:['--no-sandbox']});
 try{
  const errors=[], page=await (await browser.newContext({viewport:{width:390,height:844}})).newPage();
  page.on('pageerror',e=>errors.push(String(e)));
  async function shot(name){
   await page.evaluate(()=>scrollTo(0,0));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Horizontal overflow: '+name);
   await page.screenshot({path:output+'/'+name+'.png',fullPage:true});
  }
  await page.goto(root+'/login/');await page.locator('#id_username').fill('owner');await page.locator('#id_password').fill('browser-test-password-948');
  await page.getByRole('button',{name:'Log in',exact:true}).click();await page.waitForURL(root+'/');
  for(const width of [320,390,1280]){
   await page.setViewportSize({width,height:844});await page.goto(root+'/');
   await page.getByRole('link',{name:'French version: 6 new sentences to translate →',exact:true}).waitFor();
   await shot('linked-cards-'+width);
   await page.getByRole('link',{name:'6 new sentences available from Everyday Swedish →',exact:true}).click();
   await page.locator('#next-step').waitFor();
   assert((await page.locator('#next-step').innerText()).includes('6 new · 0 changed'));
   assert((await page.locator('#next-step').innerText()).includes('Rough API estimate'));
   await shot('french-update-'+width);
   await page.goto(root+'/1/');
   await page.getByRole('button',{name:'Approve and update French version',exact:true}).waitFor();
   await shot('swedish-update-'+width);
  }
  await page.getByRole('button',{name:'Approve and update French version',exact:true}).click();
  await page.waitForURL(/\/language-port\//);const runURL=page.url();
  await page.goto(root+'/1/');
  await page.getByRole('link',{name:'View progress',exact:true}).click();assert.equal(page.url(),runURL);
  await page.goto(root+'/3/');
  await page.getByRole('link',{name:'View progress',exact:true}).click();assert.equal(page.url(),runURL);
  await page.goto(root+'/3/settings/');
  await page.getByRole('button',{name:'Turn off workflow suggestions',exact:true}).click();
  await page.goto(root+'/1/');assert.equal(await page.locator('#next-step').count(),0);
  assert.deepEqual(errors,[]);
  console.log('Passed linked source/destination cards, six-sentence scope/cost, shared approval/progress and destination opt-out at 320/390/1280px.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
