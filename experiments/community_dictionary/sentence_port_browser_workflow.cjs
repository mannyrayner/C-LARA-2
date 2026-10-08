const {chromium}=require(process.env.COMMUNITY_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const output=process.env.COMMUNITY_BROWSER_OUTPUT;
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.COMMUNITY_CHROMIUM_PATH||undefined,headless:true,args:['--no-sandbox']});
 try {
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  const base='http://127.0.0.1:8771/community-dictionaries';
  async function shot(name){assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Horizontal overflow');await page.screenshot({path:output+'/'+name+'.png',fullPage:true});}
  await page.goto(base+'/login/');await page.locator('#id_username').fill('owner');await page.locator('#id_password').fill('local-test-only');await page.locator('button[type=submit]').click();await page.waitForURL(base+'/');
  await page.goto(base+'/1/settings/');await page.getByRole('link',{name:'Create a version in another language',exact:true}).click();
  await page.locator('#id_name').fill('French sentences');await page.locator('#id_language').fill('French');
  await page.getByRole('button',{name:'Estimate cost',exact:true}).click();
  assert((await page.locator('body').innerText()).includes('5 entries (1 sentence)'));await shot('quote-390');
  await page.locator('#id_approve').check();await page.getByRole('button',{name:'Approve and start porting',exact:true}).click();await page.reload();
  const run=page.url();await page.getByRole('heading',{name:'5 ready to review · 0 saved in this run',exact:true}).waitFor();await shot('ready-390');
  await page.getByRole('link',{name:'Open the new dictionary',exact:true}).click();const dest=page.url();
  assert.equal(await page.locator('.entry-card').count(),0);await page.getByRole('link',{name:'Review and save language results',exact:true}).click();
  await page.getByRole('link',{name:'Continue reviewing and saving',exact:true}).click();
  assert.equal(await page.locator('#id_word').inputValue(),'Le chat est couché sur le canapé.');
  await page.locator('img.entry-image').evaluate(i=>i.decode());await page.locator('audio').evaluate(a=>a.play());assert(await page.locator('audio').evaluate(a=>!a.paused));
  for(const width of [320,390,1280]){await page.setViewportSize({width,height:844});await shot('review-'+width);}
  for(let i=0;i<5;i++)await page.getByRole('button',{name:'Save and next',exact:true}).click();
  await page.getByRole('heading',{name:'0 ready to review · 5 saved in this run',exact:true}).waitFor();
  await page.goto(dest);assert.equal(await page.locator('.entry-card').count(),1);await page.locator('.entry-card').click();
  await page.getByRole('heading',{name:'Le chat est couché sur le canapé.',level:1,exact:true}).waitFor();
  for(const word of ['chat','être couché','sur','canapé'])assert((await page.locator('body').innerText()).includes(word));
  await page.setViewportSize({width:390,height:844});await shot('sentence-390');
  await page.goto(dest+'?view=words');assert.equal(await page.locator('.word-list .word-row').count(),4);
  await page.goto(dest+'?view=sentences');assert.equal(await page.locator('.entry-card').count(),1);
  await page.goto(run);await page.getByRole('link',{name:'Estimate an update',exact:true}).click();await page.getByRole('button',{name:'Estimate update cost',exact:true}).click();
  assert((await page.locator('body').innerText()).includes('0 entries (0 sentences) · 5 unchanged'));
  assert.deepEqual(errors,[]);console.log('Passed: quote/approve, empty destination recovery, sentence/audio preview, Save and next, linked vocabulary, gallery, incremental skip; 320/390/1280px.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
