const {chromium}=require(process.env.COMMUNITY_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const output=process.env.COMMUNITY_BROWSER_OUTPUT, root='http://127.0.0.1:8773/community-dictionaries';
(async()=>{
 const bundled=process.env.COMMUNITY_CHROMIUM_MODULE?(await import(process.env.COMMUNITY_CHROMIUM_MODULE)).default:null;
 const browser=await chromium.launch({executablePath:bundled?await bundled.executablePath():process.env.COMMUNITY_CHROMIUM_PATH||undefined,headless:true,args:bundled?bundled.args:['--no-sandbox']});
 const errors=[];
 async function page(width){
  const context=await browser.newContext({viewport:{width,height:844}}), p=await context.newPage();
  p.on('pageerror',e=>errors.push(String(e)));return p;
 }
 async function login(p,user){
  await p.goto(root+'/login/');await p.locator('#id_username').fill(user);
  await p.locator('#id_password').fill('browser-test-password-948');
  await p.getByRole('button',{name:'Log in',exact:true}).click();await p.waitForURL(root+'/');
 }
 async function shot(p,name){
  await p.evaluate(()=>scrollTo(0,0));
  assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Horizontal overflow: '+name);
  await p.screenshot({path:output+'/'+name+'.png',fullPage:true});
 }
 try{
  const owner=await page(390);await login(owner,'owner');
  await owner.goto(root+'/1/settings/');
  await owner.getByRole('button',{name:'Make dictionary discoverable',exact:true}).click();
  await owner.getByRole('button',{name:'Turn off discoverability',exact:true}).waitFor();
  await shot(owner,'discovery-settings-390');
  await owner.getByRole('link',{name:'Profile',exact:true}).click();
  await owner.locator('#id_public_name').fill('Swedish picture team');
  await owner.locator('#id_introduction').fill('We collect pictures and words from everyday life.');
  await owner.locator('#id_list_as_contributor').check();
  await owner.getByRole('button',{name:'Save contributor listing',exact:true}).click();
  await owner.getByRole('link',{name:'View my public contributor page',exact:true}).waitFor();
  await shot(owner,'profile-390');
  for(const width of [320,390,1280]){
   const visitor=await page(width);
   await visitor.goto(root+'/browse/');
   assert(!(await visitor.locator('body').innerText()).includes('PRIVATE-DICTIONARY'));
   assert.equal(await visitor.locator('img').count(),0);
   await shot(visitor,'discovery-list-'+width);
   await visitor.getByRole('link',{name:'Everyday Swedish',exact:true}).click();
   await visitor.getByRole('link',{name:'Log in to request membership',exact:true}).waitFor();
   assert(!(await visitor.locator('body').innerText()).includes('En växt står'));
   assert.equal((await visitor.request.get(root+'/browse/1/')).status(),404);
   await shot(visitor,'discovery-detail-'+width);
   await visitor.getByRole('link',{name:'About',exact:true}).click();
   await visitor.getByRole('link',{name:'Swedish picture team',exact:true}).waitFor();
   await shot(visitor,'about-'+width);
   await visitor.getByRole('link',{name:'Swedish picture team',exact:true}).click();
   await visitor.getByRole('link',{name:'Everyday Swedish',exact:true}).waitFor();
   assert(!(await visitor.locator('body').innerText()).includes('owner@example.org'));
   await shot(visitor,'contributor-'+width);
  }
  const learner=await page(390);await login(learner,'learner');
  await learner.goto(root+'/discover/1/');
  await learner.locator('#id_message').fill('I would like to contribute pictures.');
  await learner.getByRole('button',{name:'Request membership',exact:true}).click();
  await learner.getByRole('link',{name:'View or cancel your request',exact:true}).waitFor();
  await shot(learner,'request-pending-390');
  await owner.goto(root+'/');
  await owner.getByRole('link',{name:'Pending membership requests (1)',exact:true}).click();
  await shot(owner,'owner-requests-390');
  await owner.getByRole('button',{name:'Approve membership',exact:true}).click();
  await learner.goto(root+'/profile/');
  assert((await learner.locator('body').innerText()).includes('Approved'));
  await learner.goto(root+'/1/');
  await learner.getByRole('link',{name:'+ Contribute',exact:true}).waitFor();
  await owner.goto(root+'/profile/');await owner.locator('#id_list_as_contributor').uncheck();
  await owner.getByRole('button',{name:'Save contributor listing',exact:true}).click();
  const visitor=await page(390);await visitor.goto(root+'/about/');
  assert(!(await visitor.locator('body').innerText()).includes('Swedish picture team'));
  assert.equal((await visitor.goto(root+'/contributors/1/')).status(),404);
  await owner.goto(root+'/1/settings/');await owner.getByRole('button',{name:'Turn off discoverability',exact:true}).click();
  await visitor.goto(root+'/browse/');assert(!(await visitor.locator('body').innerText()).includes('Everyday Swedish'));
  assert.deepEqual(errors,[]);
  console.log('Passed private discovery, contributor opt-in/out, owner approval and 320/390/1280px layouts.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
