const {chromium}=require(process.env.COMMUNITY_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const output=process.env.COMMUNITY_BROWSER_OUTPUT;
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.COMMUNITY_CHROMIUM_PATH||undefined,headless:true,args:['--no-sandbox']});
 try {
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  const base='http://127.0.0.1:8771/community-dictionaries';
  async function shot(name){await page.evaluate(()=>scrollTo(0,0));await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Horizontal overflow');await page.screenshot({path:output+'/'+name+'.png',fullPage:true});}
  await page.goto(base+'/login/');await page.locator('#id_username').fill('owner');await page.locator('#id_password').fill('local-test-only');await page.locator('button[type=submit]').click();await page.waitForURL(base+'/');
  await page.goto(base+'/1/settings/');await page.locator('#id_dictionary_name').fill('Our Swedish pictures');await page.getByRole('button',{name:'Save name',exact:true}).click();await shot('settings-390');
  await page.getByRole('link',{name:'Add missing sentences',exact:true}).click();
  await page.getByRole('button',{name:'Estimate sentence cost',exact:true}).click();
  assert((await page.locator('body').innerText()).includes('2 entries (2 sentences)'));await shot('quote-390');
  await page.locator('#id_approve').check();await page.getByRole('button',{name:'Approve and start sentences',exact:true}).click();await page.reload();
  const run=page.url();await page.getByRole('heading',{name:'2 ready to review · 0 saved in this run',exact:true}).waitFor();
  await page.getByRole('link',{name:'Continue reviewing and saving',exact:true}).click();
  assert.equal(await page.locator('#id_word').inputValue(),'Katten ligger på soffan.');
  await page.locator('img.entry-image').evaluate(i=>i.decode());await page.locator('audio').evaluate(a=>a.play());assert(await page.locator('audio').evaluate(a=>!a.paused));
  for(const width of [320,390,1280]){await page.setViewportSize({width,height:844});await shot('review-'+width);}
  await page.getByRole('button',{name:'Save and next',exact:true}).click();
  assert(page.url().includes('/entries/'));await page.getByRole('button',{name:'Save and next',exact:true}).click();
  await page.getByRole('heading',{name:'0 ready to review · 2 saved in this run',exact:true}).waitFor();
  await page.getByRole('link',{name:'Build vocabulary from accepted sentences',exact:true}).click();
  await page.getByRole('button',{name:'Estimate vocabulary cost',exact:true}).click();
  await page.locator('#id_approve').check();await page.getByRole('button',{name:'Approve and start vocabulary',exact:true}).click();await page.reload();
  const vocabularyRun=page.url();await page.getByRole('link',{name:'Continue reviewing and saving',exact:true}).click();
  assert.equal(await page.locator('#id_words-0-lemma').inputValue(),'katt');await page.locator('img.entry-image').evaluate(i=>i.decode());
  await page.getByRole('link',{name:'Open sentence and listen',exact:true}).getAttribute('href').then(href=>assert(href.includes('/1/entries/')));
  for(const width of [320,390,1280]){await page.setViewportSize({width,height:844});await shot('vocabulary-review-'+width);}
  await page.getByRole('button',{name:'Save words and next',exact:true}).click();
  await page.goto(vocabularyRun);await page.getByText('Accept all remaining suggestions (1)',{exact:true}).click();
  await page.locator('input[name=accept_all]').check();await page.getByRole('button',{name:'Accept all remaining suggestions',exact:true}).click();
  assert((await page.locator('body').innerText()).includes('Word audio: 2 ready'));
  await page.goto(base+'/1/?view=sentences');assert.equal(await page.locator('.entry-card').count(),2);
  await page.locator('.entry-card').first().click();await page.getByRole('heading',{name:'Katten ligger på soffan.',level:1,exact:true}).waitFor();
  for(const word of ['katt','soffa'])assert((await page.locator('body').innerText()).includes(word));
  await page.setViewportSize({width:390,height:844});await shot('sentence-390');
  await page.goto(base+'/');assert((await page.locator('.dictionary-counts').innerText()).includes('2 sentences · 2 words'));await shot('home-390');
  await page.goto(run);await page.getByRole('link',{name:'Estimate an update',exact:true}).click();await page.getByRole('button',{name:'Estimate sentence cost',exact:true}).click();
  assert((await page.locator('body').innerText()).includes('0 entries (0 sentences)'));
  await page.goto(vocabularyRun);await page.getByRole('link',{name:'Estimate an update',exact:true}).click();await page.getByRole('button',{name:'Estimate vocabulary cost',exact:true}).click();
  assert((await page.locator('body').innerText()).includes('0 entries (0 sentences) · 2 unchanged'));
  assert.deepEqual(errors,[]);console.log('Passed: rename; same-dictionary batch estimate/approval; accepted+pending images; sentence/audio review; Save and next; vocabulary review/bulk acceptance/shared audio; sentence gallery/counts; both stages incremental skip; 320/390/1280px.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
