const {chromium}=require(process.env.COMMUNITY_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const output=process.env.COMMUNITY_BROWSER_OUTPUT, root='http://127.0.0.1:8773/community-dictionaries';
(async()=>{
 const bundled=process.env.COMMUNITY_CHROMIUM_MODULE?(await import(process.env.COMMUNITY_CHROMIUM_MODULE)).default:null;
 const browser=await chromium.launch({executablePath:bundled?await bundled.executablePath():undefined,headless:true,args:bundled?bundled.args:['--no-sandbox']});
 try{
  const errors=[];
  async function shot(page,name){
   await page.evaluate(()=>scrollTo(0,0));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Horizontal overflow: '+name);
   await page.screenshot({path:output+'/'+name+'.png',fullPage:true});
  }
  const owner=await (await browser.newContext({viewport:{width:390,height:844}})).newPage();
  owner.on('pageerror',e=>errors.push(String(e)));
  await owner.goto(root+'/login/');
  await owner.locator('#id_username').fill('owner');await owner.locator('#id_password').fill('browser-test-password-948');
  await owner.getByRole('button',{name:'Log in',exact:true}).click();await owner.waitForURL(root+'/');
  await owner.getByRole('link',{name:'3 pictures ready for sentences →',exact:true}).waitFor();
  await shot(owner,'owner-list-390');
  await owner.getByRole('link',{name:'3 pictures ready for sentences →',exact:true}).click();
  await owner.locator('#next-step').waitFor();
  for(const width of [320,390,1280]){
   await owner.setViewportSize({width,height:844});await shot(owner,'owner-approval-'+width);
  }
  await owner.getByRole('button',{name:'Approve and create sentences',exact:true}).click();
  await owner.waitForURL(/\/language-port\//);
  await owner.goto(root+'/');await owner.getByRole('link',{name:'Processing… →',exact:true}).waitFor();
  await owner.goto(root+'/1/settings/');
  await owner.getByRole('button',{name:'Turn off workflow suggestions',exact:true}).click();
  await owner.goto(root+'/');assert.equal(await owner.getByRole('link',{name:'Processing… →',exact:true}).count(),0);
  for(const width of [320,390,1280]){
   const page=await (await browser.newContext({viewport:{width,height:844}})).newPage();
   page.on('pageerror',e=>errors.push(String(e)));
   await page.goto(root+'/browse/1/');await page.getByRole('link',{name:'Practise',exact:true}).click();
   await shot(page,'public-practice-'+width);
   for(const mode of ['image-text','text-image','audio-text','text-audio','audio-image','image-audio']){
    await page.locator('#flashcard-mode').selectOption(mode);
    await page.getByRole('button',{name:'Start flashcards',exact:true}).click();
    await page.locator('.flashcard-choices').waitFor();
    await page.getByRole('button',{name:'Show answer',exact:true}).click();
    await page.getByRole('button',{name:'Next card',exact:true}).waitFor();
    if(mode==='image-text') await shot(page,'public-flashcards-'+width);
    await page.getByRole('button',{name:'Choose another activity',exact:true}).click();
   }
   await page.getByRole('button',{name:'Start crossword',exact:true}).click();
   await page.getByRole('group',{name:'Crossword grid',exact:true}).waitFor();
   await shot(page,'public-crossword-'+width);
   await page.getByRole('button',{name:'Choose another activity',exact:true}).click();
   await page.getByRole('button',{name:'Start word scramble',exact:true}).click();
   await page.getByRole('group',{name:'Word search grid',exact:true}).waitFor();
   await shot(page,'public-scramble-'+width);
   assert.equal(await page.locator('#next-step').count(),0);
   assert(!(await page.locator('body').innerText()).includes('PRIVATE-DRAFT'));
  }
  await owner.goto(root+'/1/settings/');
  await owner.getByRole('button',{name:'Turn off public browsing',exact:true}).click();
  const guest=await browser.newPage();assert.equal((await guest.goto(root+'/browse/1/practice/')).status(),404);
  assert.equal((await guest.request.get(root+'/browse/1/practice/data/')).status(),404);
  assert.deepEqual(errors,[]);
  console.log('Passed public six-mode flashcards, puzzles, revocation; owner card, exact-cost approval and preference at 320/390/1280px.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
