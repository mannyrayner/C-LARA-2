const {chromium}=require(process.env.COMMUNITY_PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
const output=process.env.COMMUNITY_BROWSER_OUTPUT;
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.COMMUNITY_CHROMIUM_PATH||undefined,headless:true,args:['--no-sandbox']});
 try{
  let user=0;
  for(const community of [true,false])for(const width of [320,390,1280]){
   const context=await browser.newContext({viewport:{width,height:844}}),page=await context.newPage();
   const errors=[];page.on('pageerror',e=>errors.push(String(e)));
   const root='http://127.0.0.1:8772',base=root+(community?'/community-dictionaries':'/accounts'),label=(community?'community':'clara')+'-'+width;
   async function shot(suffix){await page.evaluate(()=>scrollTo(0,0));await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Horizontal overflow');await page.screenshot({path:output+'/'+label+'-'+suffix+'.png',fullPage:true});}
   await page.goto(base+'/login/');await page.getByRole('link',{name:'Forgotten password?',exact:true}).click();
   await shot('request');
   const email='learner'+user+'@example.org',file=output+'/'+email+'.json';
   if(fs.existsSync(file))fs.unlinkSync(file);
   await page.getByLabel('Email').fill(email);await page.getByRole('button',{name:'Send reset link',exact:true}).click();
   await page.getByRole('heading',{name:'Check your email',exact:true}).waitFor();await shot('sent');
   for(let tries=0;!fs.existsSync(file)&&tries<100;tries++)await new Promise(r=>setTimeout(r,100));
   const message=JSON.parse(fs.readFileSync(file,'utf8')),link=message.body.match(/http:\/\/127\.0\.0\.1:8772\S+/)[0];
   await page.goto(link);await page.getByRole('heading',{name:'Choose a new password',exact:true}).waitFor();
   const password='Recovery-demo-password-549';
   await page.locator('#id_new_password1').fill(password);await page.locator('#id_new_password2').fill('not-matching');
   await page.getByRole('button',{name:'Save new password',exact:true}).click();await page.locator('.errorlist').first().waitFor();await shot('validation');
   await page.locator('#id_new_password1').fill(password);await page.locator('#id_new_password2').fill(password);
   await page.getByRole('button',{name:'Save new password',exact:true}).click();await page.getByRole('heading',{name:'Your password has been changed',exact:true}).waitFor();await shot('complete');
   const destination=await page.getByRole('link',{name:'Log in',exact:true}).last().getAttribute('href');assert.equal(destination,community?'/community-dictionaries/login/':'/accounts/login/');
   await page.goto(root+destination);await page.locator('#id_username').fill('learner'+user);await page.locator('#id_password').fill(password);await page.locator('button[type=submit]').click();
   await page.waitForURL(u=>!u.pathname.includes('/login/'));
   const fresh=await browser.newPage();await fresh.goto(link);await fresh.getByRole('heading',{name:'This link cannot be used',exact:true}).waitFor();await fresh.close();
   assert.deepEqual(errors,[]);await context.close();user++;
  }
  console.log('Passed both recovery flows at 320/390/1280px: login link, async captured email, mismatch validation, reset, login and consumed-link rejection.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
