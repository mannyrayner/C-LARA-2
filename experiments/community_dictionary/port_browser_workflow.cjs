const {chromium}=require(process.env.COMMUNITY_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base='http://127.0.0.1:8765/community-dictionaries/1';
const output=process.env.COMMUNITY_BROWSER_OUTPUT;
(async()=>{
 const bundle=process.env.COMMUNITY_CHROMIUM_MODULE ? (await import(process.env.COMMUNITY_CHROMIUM_MODULE)).default:null;
 const browser=await chromium.launch({headless:true,executablePath:bundle?await bundle.executablePath():process.env.COMMUNITY_CHROMIUM_PATH||undefined,args:bundle?bundle.args:['--no-sandbox']});
 try {
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8765/community-dictionaries/login/');
  await page.locator('[name=username]').fill('browser_owner');
  await page.locator('[name=password]').fill('local-browser-trial-only');
  await page.locator('button[type=submit],input[type=submit]').first().click();
  await page.waitForURL('**/community-dictionaries/');
  await page.goto(base+'/settings/');
  await page.getByRole('link',{name:'Create a version in another language',exact:true}).click();
  await page.locator('[name=name]').fill('Italian practice');
  await page.locator('[name=language]').fill('Italian');
  await page.locator('[name=voice]').selectOption('cedar');
  await page.getByRole('button',{name:'Estimate cost',exact:true}).click();
  assert(await page.getByText('Estimate before starting',{exact:true}).count());
  assert(!fs.existsSync(output+'/queue-events.jsonl'),'An estimate must not call AI');
  await page.screenshot({path:output+'/port-quote-390.png',fullPage:true});
  await page.locator('[name=approve]').check();
  await page.getByRole('button',{name:'Approve and start porting',exact:true}).click();
  const runUrl=page.url();
  // Leave the job page while the real worker processes its queue.
  await page.goto(base+'/');
  for(let n=0;n<100;n++){
   await page.goto(runUrl);
   if(await page.getByText('Porting complete',{exact:true}).count())break;
   if(n===99)throw new Error('Queue did not finish');
   await page.waitForTimeout(500);
  }
  assert.equal(await page.getByRole('link',{name:'Review result',exact:true}).count(),8);
  await page.screenshot({path:output+'/port-complete-390.png',fullPage:true});
  await page.getByRole('link',{name:'Review result',exact:true}).first().click();
  await page.locator('img.entry-image').evaluate(i=>i.decode());
  assert(await page.locator('img.entry-image').evaluate(i=>i.complete&&i.naturalWidth>0));
  await page.locator('audio').evaluate(a=>a.play());
  assert(await page.locator('audio').evaluate(a=>!a.paused));
  await page.setViewportSize({width:320,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Review page overflows');
  await page.screenshot({path:output+'/port-review-320.png',fullPage:true});
  const word=await page.locator('[name=word]').inputValue();
  await page.getByRole('button',{name:'Save entry to Italian practice',exact:true}).click();
  assert((await page.locator('body').innerText()).includes('1 saved'));
  await page.getByRole('link',{name:'Open the new dictionary',exact:true}).click();
  assert((await page.locator('body').innerText()).includes(word));
  await page.goto(runUrl);
  await page.locator('section.panel').filter({has:page.getByRole('heading',{name:'tak → tetto · unclear',exact:true})}).getByRole('link',{name:'Review result',exact:true}).click();
  await page.locator('img.entry-image').evaluate(i=>i.decode());
  assert.equal(await page.locator('[name=word]').inputValue(),'tetto');
  assert.equal(await page.locator('audio').count(),0);
  assert(await page.getByText('You can accept a tentative translation or enter your own.',{exact:false}).count());
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Unclear review overflows');
  await page.screenshot({path:output+'/port-unclear-review-320.png',fullPage:true});
  await page.getByRole('button',{name:'Save entry to Italian practice',exact:true}).click();
  assert((await page.locator('body').innerText()).includes('2 saved'));
  assert((await page.locator('body').innerText()).includes('Use Create audio'));
  await page.getByRole('button',{name:'Cancel and discard unsaved results',exact:true}).click();
  await page.getByRole('link',{name:'Estimate an update',exact:true}).click();
  await page.getByRole('button',{name:'Estimate update cost',exact:true}).click();
  assert((await page.locator('body').innerText()).includes('6 entries · 2 unchanged'));
  assert.equal(errors.length,0,errors.join('\n'));
  const events=fs.readFileSync(output+'/queue-events.jsonl','utf8').trim().split('\n').map(JSON.parse);
  const active=new Set();let maximum=0;
  for(const e of events.sort((a,b)=>a.time-b.time)){const id=e.pid+':'+e.thread;if(e.event==='start')active.add(id);else active.delete(id);maximum=Math.max(maximum,active.size);}
  assert.equal(maximum,2,'Two concurrent tasks must overlap their AI calls');
  const processes=new Set(events.map(e=>e.pid)).size;
  if(process.env.COMMUNITY_PORT_BROWSER_QUEUE!=='stub')assert.equal(processes,2,'Two real queue processes are required');
  fs.writeFileSync(output+'/results.json',JSON.stringify({entries:8,max_concurrent_provider_calls:maximum,worker_processes:processes,browser_errors:errors,checks:['quote makes no calls','explicit approval','real ORM queue','leave page while processing','fan-in settles','audio preview','320px layout','review and save','uncertain translation override','incremental skip']},null,2));
  console.log(`Language-port browser/queue rehearsal passed; ${maximum} concurrent calls, ${processes} worker processes.`);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
