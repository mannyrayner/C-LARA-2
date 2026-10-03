const {chromium} = require(process.env.COMMUNITY_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const base='http://127.0.0.1:8765/community-dictionaries/1';
const output=process.env.COMMUNITY_BROWSER_OUTPUT;
(async()=>{
  const bundled=process.env.COMMUNITY_CHROMIUM_MODULE ? (await import(process.env.COMMUNITY_CHROMIUM_MODULE)).default : null;
  const browser=await chromium.launch({executablePath:bundled ? await bundled.executablePath() : process.env.COMMUNITY_CHROMIUM_PATH || undefined, headless:true,args:bundled?bundled.args:['--no-sandbox']});
  try {
    const context=await browser.newContext({viewport:{width:390,height:844}});
    const p=await context.newPage(), errors=[];
    p.on('pageerror',e=>errors.push(String(e)));
    await p.goto('http://127.0.0.1:8765/community-dictionaries/login/');
    await p.locator('[name=username]').fill('browser_member');
    await p.locator('[name=password]').fill('local-browser-trial-only');
    await p.locator('button[type=submit],input[type=submit]').first().click();
    await p.waitForURL('**/community-dictionaries/');
    await p.goto(base+'/');
    await p.getByRole('link',{name:'Practise',exact:true}).click();
    async function shot(name){
      assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Page overflow');
      assert(await p.locator('.choice-marker').evaluateAll(nodes=>nodes.every(n=>n.getBoundingClientRect().bottom<=n.parentElement.getBoundingClientRect().bottom+1)),'Choice feedback overflows its tile');
      await p.screenshot({path:`${output}/${name}.png`,fullPage:true});
    }
    async function start(kind){
      const response=p.waitForResponse(r=>r.url().includes('/practise/data/?')&&r.url().includes(`game=${kind}`));
      await p.locator(`[data-start=${kind}]`).click();
      const data=await (await response).json();
      await p.locator('#practice-game').waitFor({state:'visible'});
      return data;
    }
    async function action(name){
      const response=p.waitForResponse(r=>r.url().includes('validate='));
      await p.getByRole('button',{name,exact:true}).click();await response;
      // Wait for the asynchronous action's DOM update/next animation frame.
      await p.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    }
    await shot('practice-menu-390');
    for(const [index,mode] of ['image-text','text-image','audio-text','text-audio','audio-image','image-audio'].entries()){
      await p.locator('#flashcard-mode').selectOption(mode);
      await p.setViewportSize({width:index%2?320:390,height:844});
      const deck=await start('flashcards');assert.equal(deck.style,'choice');
      const back=mode.split('-')[1],card=deck.cards[0];
      const correct=card.options.findIndex(o=>o.id===card.id),wrong=card.options.findIndex(o=>o.id!==card.id);
      const options=p.locator('.flashcard-choice');
      assert.equal(await options.count(),card.options.length);
      assert.equal(await p.locator('.practice-answer').count(),0);
      if(back==='audio'){
        await options.nth(0).locator('audio').evaluate(a=>a.play());
        assert.equal(await p.locator('.choice-correct').count(),0,'Listening is not an answer');
      }
      if(back==='image')assert(await options.nth(0).locator('img').evaluate(i=>i.complete&&i.naturalWidth>0));
      async function choose(i){
        const response=p.waitForResponse(r=>r.url().includes('validate='));
        await p.locator('.flashcard-choice').nth(i).locator('button').click();await response;
        await p.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      }
      await choose(wrong);
      assert.equal(await p.locator('.choice-wrong').count(),1);
      assert.equal(await p.locator('.choice-correct').count(),0);
      await choose(correct);
      assert.equal(await p.locator('.choice-correct').count(),1);
      assert((await p.locator('#game-progress').innerText()).includes('0 correct first time'));
      await shot(`choice-${mode}-${index%2?320:390}`);
      await action('Next card');
      if(mode==='image-text'){
        for(let n=1;n<deck.cards.length;n++){
          const item=deck.cards[n];await choose(item.options.findIndex(o=>o.id===item.id));await action('Next card');
        }
        assert.equal(await p.getByText('Session complete',{exact:true}).count(),1);
        assert((await p.locator('.practice-complete').innerText()).includes(`${deck.cards.length-1} of ${deck.cards.length} correct first time`));
      }else{
        await action('Show answer');
        assert((await p.locator('.practice-feedback').innerText()).includes('Answer shown'));
        await action('Next card');await action('Skip');
      }
      await p.getByRole('button',{name:'Choose another activity',exact:true}).click();
    }
    await p.setViewportSize({width:390,height:844});
    await p.locator('#flashcard-style').selectOption('recall');
    for(const mode of ['image-text','text-image','audio-text','text-audio','audio-image','image-audio']){
      await p.locator('#flashcard-mode').selectOption(mode);
      await start('flashcards');
      const prompt=mode.split('-')[0],answer=mode.split('-')[1];
      assert.equal(await p.locator('.practice-answer').count(),0);
      if(prompt==='audio'){
        const audio=p.locator('audio').first();
        await audio.evaluate(a=>a.play());
        assert(await audio.evaluate(a=>!a.paused));
      }
      await action('Show answer');
      assert.equal(await p.locator('.practice-answer').count(),1);
      if(answer==='text')assert(await p.locator('.practice-answer .practice-word').innerText());
      if(answer==='image')assert(await p.locator('.practice-answer img').evaluate(i=>i.complete&&i.naturalWidth>0));
      if(answer==='audio'){await p.locator('.practice-answer audio').evaluate(a=>a.play());}
      if(mode==='image-text'){
        assert.equal(await p.locator('.practice-answer details').getAttribute('open'),null);
        await p.locator('.practice-answer summary').click();
        await shot('flashcard-answer-390');
        await action('Again');
        assert((await p.locator('#game-progress').innerText()).includes('0 of 8'));
        for(let i=0;i<8;i++){await action('Show answer');await action('Got it');}
        assert.equal(await p.getByText('Well done!',{exact:true}).count(),1);
      }
      await p.getByRole('button',{name:'Choose another activity',exact:true}).click();
    }
    // Crossword: wrong answer, Unicode answer, clue navigation and completed grid.
    const crossword=await start('crossword');
    await p.locator('#crossword-answer').fill('WRONG');await action('Check answer');
    assert((await p.locator('.practice-feedback').innerText()).includes('Not quite'));
    await p.locator('#crossword-answer').fill(crossword.clues[0].text);await action('Check answer');
    assert((await p.locator('#game-progress').innerText()).includes('1 of'));
    await shot('crossword-390');
    for(let i=1;i<crossword.clues.length;i++){
      await action('Next clue');
      await p.locator('#crossword-answer').fill(crossword.clues[i].text);await action('Check answer');
    }
    assert.equal(await p.getByText('Puzzle complete',{exact:true}).count(),1);
    await p.setViewportSize({width:1280,height:900});await shot('crossword-1280');
    await p.getByRole('button',{name:'Choose another activity',exact:true}).click();
    await p.setViewportSize({width:320,height:740});
    const scramble=await start('scramble');
    await p.getByRole('button',{name:'Larger grid',exact:true}).click();
    assert(await p.locator('.practice-grid-wrap').evaluate(n=>n.scrollWidth>n.clientWidth));
    await p.getByRole('button',{name:'Fit grid',exact:true}).click();
    assert(await p.locator('.practice-grid-wrap').evaluate(n=>n.scrollWidth<=n.clientWidth+1));
    async function cell(pos){
      const response=p.waitForResponse(r=>r.url().includes('validate='));
      await p.locator(`[data-row="${pos.row}"][data-col="${pos.col}"]`).click();await response;
      await p.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
    }
    for(const clue of scramble.clues){await cell(clue.path.at(-1));await cell(clue.path[0]);}
    assert.equal(await p.getByText('Puzzle complete',{exact:true}).count(),1);
    await shot('word-scramble-320');
    await p.getByRole('button',{name:'Choose another activity',exact:true}).click();
    await shot('practice-menu-320');
    await p.locator('#flashcard-style').selectOption('choice');
    await start('flashcards');
    await p.route('**/practise/data/**',async route=>{
      if(route.request().url().includes('validate='))await route.fulfill({contentType:'application/json',body:'{"valid":false}'});
      else await route.continue();
    });
    await p.locator('.choice-select').first().click();
    await p.locator('#practice-choices').waitFor({state:'visible'});
    assert.equal(await p.locator('.flashcard-choice').count(),0);
    await p.unroute('**/practise/data/**');
    // Accessible category filter and a read-only member's practice route.
    await p.locator('#practice-category').selectOption('Home');
    await p.getByRole('button',{name:'Use category',exact:true}).click();
    await p.waitForURL('**/practise/?category=Home');
    await p.locator('#flashcard-style').selectOption('recall');
    const filtered=await start('flashcards');assert(filtered.cards.every(c=>c.category==='Home'));
    // An open game's next action must clear all material on invalidation.
    await p.route('**/practise/data/**',async route=>{
      if(route.request().url().includes('validate='))await route.fulfill({contentType:'application/json',body:'{"valid":false}'});
      else await route.continue();
    });
    await p.getByRole('button',{name:'Show answer',exact:true}).click();
    await p.locator('#practice-choices').waitFor({state:'visible'});
    assert.equal(await p.locator('#game-body img,#game-body audio').count(),0);
    assert((await p.locator('#practice-status').innerText()).includes('dictionary changed'));
    await p.unroute('**/practise/data/**');
    await start('flashcards');
    await p.route('**/practise/data/**',route=>route.abort('internetdisconnected'));
    await p.getByRole('button',{name:'Show answer',exact:true}).click();
    await p.locator('#practice-choices').waitFor({state:'visible'});
    assert.equal(await p.locator('#game-body img,#game-body audio').count(),0);
    await p.unroute('**/practise/data/**');
    assert.deepEqual(await p.evaluate(()=>Object.keys(localStorage).filter(k=>/practice/i.test(k))),[]);
    assert.deepEqual(errors,[]);
    console.log('PASS multiple-choice six directions, separate audio selection, wrong/right/show/skip/scoring/completion, invalidation, plus six recall flashcard directions, playback, reveal/again/completion, crossword Unicode input and completion, word search reverse endpoints, categories, invalidation, no local persistence, 320/390/1280px layouts. Synthetic media, no AI calls.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
