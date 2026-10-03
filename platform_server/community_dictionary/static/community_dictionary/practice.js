/* Page-local practice. No content, recordings or scores enter browser storage. */
(() => {
  'use strict';
  const root = document.getElementById('practice');
  if (!root) return;
  const choices = document.getElementById('practice-choices');
  const game = document.getElementById('practice-game');
  const body = document.getElementById('game-body');
  const status = document.getElementById('practice-status');
  const title = document.getElementById('game-title');
  const progress = document.getElementById('game-progress');
  let data = null, queue = [], total = 0, learned = 0, current = 0, revealed = false;
  let solved = new Map(), startCell = null, busy = false, epoch = 0, enlarged = false;
  let mcWrong = new Set(), mcOutcome = '', mcFirst = 0;
  const el = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  };
  const button = (text, fn, cls='secondary') => {
    const n = el('button', text, cls); n.type = 'button';
    n.addEventListener('click', fn); return n;
  };
  function stopAudio() { body.querySelectorAll('audio').forEach(a => { a.pause(); a.removeAttribute('src'); a.load(); }); }
  function clear(message='') {
    epoch++; stopAudio(); data=null; queue=[]; solved.clear(); startCell=null; busy=false;
    body.replaceChildren(); game.hidden=true; choices.hidden=false; status.textContent=message;
    document.body.classList.remove('practice-active');
  }
  async function fetchData(params) {
    const url = new URL(root.dataset.url, location.origin);
    url.search = new URLSearchParams({category:root.dataset.category, ...params});
    const controller=new AbortController(), timeout=setTimeout(()=>controller.abort(),15000);
    let response;
    try { response=await fetch(url, {credentials:'same-origin', cache:'no-store', headers:{Accept:'application/json'}, signal:controller.signal}); }
    catch(e) { throw new Error(e.name==='AbortError' ? 'The connection is taking too long. Please try again.' : 'Unable to reach the dictionary. Reconnect and start a new activity.'); }
    finally { clearTimeout(timeout); }
    if (response.redirected || [401,403,404].includes(response.status)) throw new Error('This dictionary is no longer available. Return to My dictionaries.');
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Unable to check the dictionary. Please try again when connected.');
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Unable to start this activity. Please try again.');
    return payload;
  }
  async function valid() {
    if (!data) return false;
    const expected=epoch;
    try {
      const result=await fetchData({validate:data.revision});
      if (expected!==epoch || !data) return false;
      if (!result.valid) { clear('The dictionary changed. Choose an activity to practise with the current shared content.'); return false; }
      if (!document.hidden) game.hidden=false;
      return true;
    } catch (e) {
      if (expected===epoch) clear(e.name==='AbortError' ? 'The connection is taking too long. Reconnect and start a new activity.' : e.message || 'Connection lost. Reconnect and start a new activity.');
      return false;
    }
  }
  async function guarded(action) {
    if (busy) return;
    busy=true;
    try { if (await valid()) action(); } finally { busy=false; }
  }
  function media(row, kind, parent) {
    if (kind==='text') { parent.append(el('p',row.text,'practice-word')); return; }
    if (kind==='image') {
      const image=el('img',undefined,'practice-picture'); image.src=row.image;
      image.alt='Dictionary picture'; parent.append(image);
      if (row.image_generated) parent.append(el('p','AI-generated picture','practice-picture-label'));
      image.addEventListener('error',()=>{ status.textContent='This picture could not be loaded. You can skip it or start another activity.'; });
    } else {
      const audio=el('audio'); audio.controls=true; audio.preload='none'; audio.src=row.audio;
      audio.setAttribute('aria-label','Dictionary recording'); parent.append(audio);
      audio.addEventListener('play',()=>body.querySelectorAll('audio').forEach(other=>{if(other!==audio)other.pause();}));
      audio.addEventListener('error',()=>{status.textContent='This recording could not be played. You can skip it or try another browser.';});
      if (row.audio_synthetic) parent.append(el('p','Synthetic voice','practice-picture-label'));
    }
  }
  function translation(row, parent) {
    if (!row.meaning) return;
    const details=el('details'); details.append(el('summary','Translation'),el('p',row.meaning)); parent.append(details);
  }
  function wordLink(row, parent) {
    const a=el('a',row.text ? 'Visit word page' : 'Visit entry'); a.href=row.word_url || row.entry_url; parent.append(a);
  }
  function renderFlashcard() {
    if (data.style==='choice') { renderChoices(); return; }
    stopAudio(); body.replaceChildren();
    progress.textContent=`${learned} of ${total} remembered · ${queue.length} left`;
    if (!queue.length) {
      const finished=el('div',undefined,'practice-complete'); finished.append(el('h3','Well done!'),el('p',`You recalled ${total} cards.`),button('Practise again',()=>start('flashcards'))); body.append(finished); return;
    }
    const row=queue[0], [front,back]=data.mode.split('-');
    const card=el('div',undefined,'practice-card');
    card.append(el('p',`Recall the ${back==='text'?'word or phrase':back==='image'?'picture':'pronunciation'}.`,'practice-label'));
    const prompt=el('div'); media(row,front,prompt); card.append(prompt);
    const actions=el('div',undefined,'actions');
    if (!revealed) {
      actions.append(button('Show answer',()=>guarded(()=>{revealed=true;renderFlashcard();}),''));
    } else {
      const answer=el('div',undefined,'practice-answer'); media(row,back,answer); translation(row,answer); wordLink(row,answer); card.append(answer);
      actions.append(button('Again',()=>guarded(()=>{queue.push(queue.shift());revealed=false;renderFlashcard();})),button('Got it',()=>guarded(()=>{queue.shift();learned++;revealed=false;renderFlashcard();}),''));
    }
    actions.append(button('Skip',()=>guarded(()=>{queue.shift();total--;revealed=false;renderFlashcard();}),'quiet'));
    card.append(actions); body.append(card);
  }
  function nextChoice() {
    queue.shift();mcWrong=new Set();mcOutcome='';renderFlashcard();
  }
  function renderChoices() {
    stopAudio();body.replaceChildren();
    const completed=total-queue.length+(mcOutcome?1:0);
    progress.textContent=`${completed} of ${total} completed · ${mcFirst} correct first time`;
    if(!queue.length) {
      const done=el('div',undefined,'practice-complete');
      done.append(el('h3','Session complete'),el('p',`${mcFirst} of ${total} correct first time.`),button('Practise again',()=>start('flashcards')));
      body.append(done);return;
    }
    const row=queue[0], [front,back]=data.mode.split('-');
    const card=el('div',undefined,'practice-card practice-multiple-choice');
    card.append(el('p',`Choose the matching ${back==='text'?'word or phrase':back==='image'?'picture':'recording'}.`,'practice-label'));
    const prompt=el('div',undefined,'choice-prompt');media(row,front,prompt);card.append(prompt);
    const feedback=el('p',mcOutcome==='correct'?'Correct!':mcOutcome==='shown'?'Answer shown.':mcWrong.size?'Not this one. Try another, or show the answer.':'','practice-feedback');
    feedback.setAttribute('role','status');card.append(feedback);
    const options=el('div',undefined,'flashcard-choices');options.setAttribute('role','group');options.setAttribute('aria-label','Answer choices');
    row.options.forEach((option,index)=>{
      const label=String.fromCharCode(65+index), correct=option.id===row.id;
      const tile=el('div',undefined,'flashcard-choice');tile.dataset.option=label;
      if(mcOutcome&&correct)tile.classList.add('choice-correct');
      if(mcWrong.has(option.id))tile.classList.add('choice-wrong');
      const choose=()=>guarded(()=>{
        if(mcOutcome || mcWrong.has(option.id))return;
        if(correct){if(!mcWrong.size)mcFirst++;mcOutcome='correct';}
        else mcWrong.add(option.id);
        renderChoices();
      });
      let select;
      if(back==='text') {
        select=button(`${label}. ${option.text}`,choose,'secondary choice-select');
      }else if(back==='image') {
        select=button('',choose,'secondary choice-select choice-picture');
        select.setAttribute('aria-label',`Choose picture ${label}`);
        media(option,'image',select);select.append(el('span',`Choose ${label}`));
      }else {
        tile.append(el('p',`Recording ${label}`,'practice-label'));
        media(option,'audio',tile);
        select=button(`Choose recording ${label}`,choose,'secondary choice-select');
      }
      select.disabled=!!mcOutcome || mcWrong.has(option.id);
      tile.append(select);
      if(mcOutcome&&correct)tile.append(el('p','✓ Matching answer','choice-marker'));
      else if(mcWrong.has(option.id))tile.append(el('p','Try another answer','choice-marker'));
      options.append(tile);
    });
    card.append(options);
    const actions=el('div',undefined,'actions');
    if(mcOutcome) {
      const answer=el('div',undefined,'practice-answer');
      // Correct text/translation becomes available only after answering/revealing.
      if(back!=='text'&&row.text)answer.append(el('p',row.text,'practice-word'));
      translation(row,answer);wordLink(row,answer);card.append(answer);
      actions.append(button('Next card',()=>guarded(nextChoice),''));
    }else{
      actions.append(button('Show answer',()=>guarded(()=>{mcOutcome='shown';renderChoices();}),'quiet'),button('Skip',()=>guarded(nextChoice),'quiet'));
    }
    card.append(actions);body.append(card);
  }
  const key = p => `${p.row},${p.col}`;
  function normalize(value) { return value.normalize('NFC').toUpperCase().replace(/[\s\-'’‐‑]/gu,''); }
  function renderPuzzle(feedback='') {
    stopAudio(); body.replaceChildren();
    const crossword=data.game==='crossword', clue=data.clues[current];
    const remembered=[...solved.values()].filter(x=>x==='correct').length;
    progress.textContent=`${solved.size} of ${data.clues.length} completed · ${remembered} solved without showing the answer`;
    const layout=el('div',undefined,'practice-puzzle');
    const gridWrap=el('div',undefined,'practice-grid-wrap');
    const grid=el('div',undefined,'practice-grid'); grid.style.setProperty('--columns',data.grid[0].length);
    if(enlarged)grid.classList.add('enlarged');
    grid.setAttribute('role','group');grid.setAttribute('aria-label',crossword?'Crossword grid':'Word search grid');
    const active=new Set(clue.path.map(key));
    const filled=new Set(data.clues.filter((c,i)=>solved.has(i)).flatMap(c=>c.path.map(key)));
    data.grid.forEach((line,row)=>line.forEach((letter,col)=>{
      const pos={row,col}, cellKey=key(pos);
      if (!letter) { const black=el('span',undefined,'practice-cell black'); black.setAttribute('aria-hidden','true');grid.append(black);return; }
      const shown=!crossword || filled.has(cellKey) ? letter : '';
      const cell=button(shown,()=>guarded(()=>{
        if (crossword) {
          const matches=data.clues.map((c,i)=>({c,i})).filter(x=>x.c.path.some(p=>key(p)===cellKey));
          current=(matches.find(x=>x.i!==current)||matches[0]).i;
          renderPuzzle(); document.getElementById('crossword-answer')?.focus();
        } else selectCell(pos);
      }),'practice-cell');
      cell.setAttribute('aria-label',`Row ${row+1}, column ${col+1}${shown?', '+shown:''}`);
      cell.dataset.row=row;cell.dataset.col=col;
      if (crossword && active.has(cellKey)) cell.classList.add('active');
      if (filled.has(cellKey)) cell.classList.add('found');
      if (startCell && key(startCell)===cellKey) cell.classList.add('start');
      const starts=data.clues.filter(c=>key(c.path[0])===cellKey);
      if (crossword && starts.length) cell.append(el('small',String(starts[0].number)));
      grid.append(cell);
    }));
    const gridArea=el('div',undefined,'practice-grid-area');
    gridWrap.append(grid);
    const sizeButton=button(enlarged?'Fit grid':'Larger grid',()=>{enlarged=!enlarged;grid.classList.toggle('enlarged',enlarged);sizeButton.textContent=enlarged?'Fit grid':'Larger grid';},'quiet');
    gridArea.append(gridWrap,sizeButton);layout.append(gridArea);
    const visual=el('div',undefined,'puzzle-picture');
    visual.append(el('h3',`${clue.number}${crossword?' '+clue.direction:''} · ${[...clue.answer].length} letters`));
    media(clue,'image',visual); translation(clue,visual);layout.append(visual);
    const panel=el('div',undefined,'puzzle-clue');
    panel.append(el('p',crossword?'Type the word for this picture. Spaces and punctuation are not needed.':'Tap the first letter, then the last letter of the word. It can go across, down or diagonally.','help'));
    const msg=el('p',feedback,'practice-feedback');msg.setAttribute('role','status');panel.append(msg);
    if (solved.has(current)) {
      panel.append(el('p',clue.text,'practice-word'),el('p',solved.get(current)==='shown'?'Answer shown':'Found!'));
      if (clue.audio) media(clue,'audio',panel);
      wordLink(clue,panel);
    } else {
      if (crossword) {
        const form=el('form');const label=el('label','Your answer');label.htmlFor='crossword-answer';
        const input=el('input');input.id='crossword-answer';input.autocomplete='off';input.spellcheck=false;input.setAttribute('autocapitalize','none');input.maxLength=255;
        const submit=el('button','Check answer');submit.type='submit';
        form.append(label,input,submit);form.addEventListener('submit',event=>{event.preventDefault();const answer=input.value;guarded(()=>{
          if(normalize(answer)===clue.answer){solved.set(current,'correct');renderPuzzle('Correct!');}else{msg.textContent='Not quite. Try again, or show the answer.';input.focus();}
        });});panel.append(form);
      }
      panel.append(button('Show answer',()=>guarded(()=>{solved.set(current,'shown');startCell=null;renderPuzzle();}),'quiet'));
    }
    const navigation=el('div',undefined,'actions');
    navigation.append(button('Previous clue',()=>guarded(()=>{current=(current+data.clues.length-1)%data.clues.length;startCell=null;renderPuzzle();})),button('Next clue',()=>guarded(()=>{current=(current+1)%data.clues.length;startCell=null;renderPuzzle();})));
    panel.append(navigation);layout.append(panel);body.append(layout);
    const clues=el('div',undefined,'clue-choices');clues.setAttribute('aria-label','Choose a picture clue');
    data.clues.forEach((c,i)=>{const b=button(`${c.number}${crossword?' '+c.direction:''}${solved.has(i)?' ✓':''}`,()=>guarded(()=>{current=i;startCell=null;renderPuzzle();}));b.setAttribute('aria-pressed',i===current?'true':'false');clues.append(b);});body.append(clues);
    if (solved.size===data.clues.length) {const done=el('div',undefined,'practice-complete');done.append(el('h3','Puzzle complete'),button('New puzzle',()=>start(data.game)));body.append(done);}
  }
  function selectCell(end) {
    if (!startCell) {startCell=end;renderPuzzle('Now tap the last letter.');return;}
    const dr=end.row-startCell.row,dc=end.col-startCell.col;
    if (!(dr===0 || dc===0 || Math.abs(dr)===Math.abs(dc))) {startCell=null;renderPuzzle('Choose a straight line of letters.');return;}
    const length=Math.max(Math.abs(dr),Math.abs(dc))+1;
    const path=Array.from({length},(_,i)=>({row:startCell.row+Math.sign(dr)*i,col:startCell.col+Math.sign(dc)*i}));
    const letters=path.map(p=>data.grid[p.row][p.col]).join('');
    const match=data.clues.findIndex(c=>c.answer===letters || c.answer===[...letters].reverse().join(''));
    startCell=null;
    if(match<0){renderPuzzle('Not one of these words yet. Try again.');return;}
    if(!solved.has(match))solved.set(match,'correct');current=match;
    // Accept accidental duplicate occurrences too; mark the selected occurrence.
    data.clues[match].path=path;
    renderPuzzle('Found it!');
  }
  async function start(kind) {
    if(busy)return;
    const mode=document.getElementById('flashcard-mode').value;
    const style=document.getElementById('flashcard-style').value;
    clear();busy=true;const expected=epoch;status.textContent='Preparing your activity…';
    try {
      const result=await fetchData({game:kind,mode,style});
      if(expected!==epoch)return;
      if(kind==='flashcards' && !result.cards.length){clear('No cards have both kinds of content yet. Choose another direction or add the missing pictures, words or recordings.');return;}
      data=result;current=0;revealed=false;learned=0;solved=new Map();mcWrong=new Set();mcOutcome='';mcFirst=0;
      choices.hidden=true;game.hidden=false;status.textContent='';enlarged=false;
      document.body.classList.add('practice-active');
      title.textContent=kind==='flashcards'?'Flashcards':kind==='crossword'?'Picture crossword':'Word scramble';
      if(kind==='flashcards'){queue=[...data.cards];total=queue.length;renderFlashcard();}else renderPuzzle();
      title.focus();
    }catch(e){if(expected===epoch)clear(e.message || 'Unable to connect. Please try again.');}
    finally{if(expected===epoch)busy=false;}
  }
  root.querySelectorAll('[data-start]').forEach(b=>b.addEventListener('click',()=>start(b.dataset.start)));
  document.getElementById('practice-back').addEventListener('click',()=>clear());
  // Recheck every action, periodically, and after returning from another app.
  // Already displayed/downloaded material cannot be recalled from a device.
  setInterval(()=>{if(data&&!busy&&!document.hidden)guarded(()=>{});},30000);
  document.addEventListener('visibilitychange',()=>{
    if(!data)return;
    if(document.hidden){body.querySelectorAll('audio').forEach(a=>a.pause());game.hidden=true;}
    else guarded(()=>{game.hidden=false;});
  });
  window.addEventListener('pagehide',()=>clear());
  window.addEventListener('pageshow',e=>{if(e.persisted)clear('Choose an activity to use the latest shared content.');});
})();
