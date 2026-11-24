const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto').webcrypto;
const script = name => fs.readFileSync(path.join(__dirname, '../static/community_dictionary', name), 'utf8');
const seed = 'a'.repeat(32), revision = 'accepted-v1';
const tick = () => new Promise(resolve => setImmediate(resolve));
class Storage {
  getItem(k) { return this[k] ?? null; }
  setItem(k,v) { this[k] = v; }
  removeItem(k) { delete this[k]; }
}
class Element {
  constructor(tag='div') {
    this.tag=tag;this.children=[];this.listeners={};this.dataset={};this.hidden=false;this.textContent='';
    this.classList={add(){},remove(){},toggle(){}};this.style={setProperty(){}};this.value='';
  }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children=items; }
  addEventListener(event, fn) { (this.listeners[event] ??= []).push(fn); }
  async fire(event, props={}) { for(const fn of this.listeners[event] || []) await fn({type:event,preventDefault(){},...props}); }
  setAttribute(name,value) { this[name]=value; }
  focus() {}
  querySelectorAll(selector) { return this.all().filter(x=>x.tag===selector); }
  all() { return this.children.flatMap(x=>[x,...x.all()]); }
}
const row = (id,text) => ({id,text,meaning:'PRIVATE MEANING',image:'/private-media/'+id,
  audio:'',word_url:'/community-dictionaries/7/words/'+id+'/',entry_url:'/community-dictionaries/7/entries/'+id+'/'});
function response(kind,style='recall') {
  const rows=[row(1,'PRIVATE CAT'),row(2,'PRIVATE DOG')];
  if(kind==='flashcards')return {game:kind,seed,revision,mode:'image-text',style,
    cards:rows.map(r=>style==='choice'?{...r,options:rows}:r)};
  return {game:kind,seed,revision,grid:[['C','A','T'],['D','O','G']],clues:rows.map((r,i)=>({
    ...r,answer:i?'DOG':'CAT',number:i+1,direction:'across',path:[0,1,2].map(col=>({row:i,col}))}))};
}
function page(storage, {url='https://clara.test/community-dictionaries/7/practise/', result=response('flashcards'),
  valid=true,user='8',unavailable=false}={}) {
  const ids=Object.fromEntries(['practice','practice-choices','practice-game','game-body','practice-status',
    'game-title','game-progress','flashcard-mode','flashcard-style','practice-back'].map(id=>[id,new Element()]));
  ids.practice.dataset={url:'/community-dictionaries/7/practise/data/',category:''};
  ids['flashcard-mode'].value='image-text';ids['flashcard-style'].value=result.style || 'recall';
  const starts=['flashcards','crossword','scramble'].map(kind=>{const e=new Element('button');e.dataset.start=kind;return e;});
  ids.practice.querySelectorAll=()=>starts;
  const doc=new Element();doc.body=new Element('body');doc.body.dataset.user=user;doc.hidden=false;
  doc.getElementById=id=>ids[id] || ids['game-body'].all().find(x=>x.id===id);
  doc.createElement=tag=>new Element(tag);
  const win=new Element();let scroll;
  win.scrollY=417;win.scrollTo=(x,y)=>{scroll=y};
  const requests=[];
  const context={window:win,document:doc,sessionStorage:storage,crypto,Uint8Array,URL,URLSearchParams,
    location:new URL(url),AbortController,setTimeout,clearTimeout,setInterval(){},
    async fetch(target){
      const params=new URL(target).searchParams;requests.push(params);
      return {ok:!unavailable,status:unavailable?404:200,headers:{get:()=> 'application/json'},
        async json(){return params.has('validate')?{valid}:JSON.parse(JSON.stringify(result));}};
    }};
  vm.createContext(context);
  vm.runInContext(script('practice_session.js'),context);
  vm.runInContext(script('practice.js'),context);
  const find=text=>ids['game-body'].all().find(x=>x.textContent===text);
  return {ids,win,context,requests,get scroll(){return scroll},find,
    async start(){await starts.find(x=>x.dataset.start===result.game).fire('click');},
    async visit(){const a=ids['game-body'].all().find(x=>x.tag==='a');assert.ok(a);await a.fire('click');return new URL(a.href).searchParams.get('return_game');}};
}
async function resume(storage, token, options={}) {
  const p=page(storage,{...options,url:'https://clara.test/community-dictionaries/7/practise/?resume='+token});
  await tick();await tick();return p;
}
test('recall returns to the same revealed card, queue, count and scroll; no dictionary content is saved',async()=>{
  const store=new Storage(),p=page(store);await p.start();
  await p.find('Show answer').fire('click');await p.find('Got it').fire('click');
  await p.find('Show answer').fire('click');const token=await p.visit();
  await p.win.fire('pagehide');
  const encoded=JSON.stringify(store);assert.ok(!encoded.includes('PRIVATE'));assert.ok(!encoded.includes('/private-media/'));
  const back=await resume(store,token);
  assert.ok(back.find('PRIVATE DOG'));assert.ok(back.find('Got it'));
  assert.match(back.ids['game-progress'].textContent,/1 of 2 remembered/);assert.equal(back.scroll,417);
  assert.equal(back.requests[0].get('seed'),seed);
  await back.ids['practice-back'].fire('click');assert.equal(Object.keys(store).length,0);
});
test('ordinary navigation clears recovery and browser Back rechecks a retained game',async()=>{
  const store=new Storage(),p=page(store);await p.start();await p.find('Show answer').fire('click');await p.visit();
  await p.win.fire('pagehide');await p.win.fire('pageshow',{persisted:true});
  await tick();
  assert.equal(p.ids['practice-game'].hidden,false);assert.ok(p.requests.some(p=>p.has('validate')));
  await p.win.fire('pagehide');assert.equal(Object.keys(store).length,0);
});
test('multiple-choice return retains wrong choices, revealed outcome and first-attempt count',async()=>{
  const store=new Storage(),result=response('flashcards','choice'),p=page(store,{result});await p.start();
  await p.find('B. PRIVATE DOG').fire('click');await p.find('Show answer').fire('click');
  const token=await p.visit(),back=await resume(store,token,{result});
  assert.ok(back.find('Answer shown.'));assert.equal(back.find('B. PRIVATE DOG').disabled,true);
  assert.match(back.ids['game-progress'].textContent,/1 of 2 completed · 0 correct first time/);
  await back.find('Next card').fire('click');assert.ok(back.find('Show answer'));
});
for(const kind of ['crossword','scramble'])test(kind+' return retains the selected clue and solved grid',async()=>{
  const store=new Storage(),result=response(kind),p=page(store,{result});await p.start();
  await p.find('Show answer').fire('click');await p.find('Next clue').fire('click');
  await p.find('Show answer').fire('click');const token=await p.visit(),back=await resume(store,token,{result});
  assert.ok(back.find('PRIVATE DOG'));assert.ok(back.find('Puzzle complete'));
  assert.match(back.ids['game-progress'].textContent,/2 of 2 completed/);
  assert.ok(back.find(kind==='crossword'?'2 across · 3 letters':'2 · 3 letters'));assert.ok(back.find('C'));
});
test('a changed or withdrawn dictionary discards recovery; no old content is rendered',async()=>{
  for(const options of [{result:{...response('flashcards'),revision:'changed'}},{unavailable:true}]){
    const store=new Storage(),p=page(store);await p.start();await p.find('Show answer').fire('click');
    const token=await p.visit(),back=await resume(store,token,options);
    assert.equal(back.find('PRIVATE CAT'),undefined);assert.equal(Object.keys(store).length,0);
    assert.ok(back.ids['practice-status'].textContent);
  }
});
test('expired, malformed and other-account progress cannot resume',async()=>{
  for(const mode of ['expired','malformed','other-user']){
    const store=new Storage(),p=page(store);await p.start();await p.find('Show answer').fire('click');const token=await p.visit();
    const key=Object.keys(store)[0];
    if(mode==='expired'){const s=JSON.parse(store[key]);s.saved-=3*60*60*1000;store[key]=JSON.stringify(s);}
    if(mode==='malformed')store[key]='not json';
    const back=await resume(store,token,{user:mode==='other-user'?'9':'8'});
    assert.equal(back.find('PRIVATE CAT'),undefined);assert.match(back.ids['practice-status'].textContent,/no longer available/);
    assert.equal(Object.keys(store).length,0);
  }
});
test('return context follows several word/sentence/picture links, keeps picture fragments and excludes other destinations',()=>{
  let current='https://clara.test/community-dictionaries/7/words/1/?return_game='+seed;
  for(const next of ['entries/5/?picture=4#words','words/2/','entries/6/']){
    const control={dataset:{token:seed,category:'A & B',wordPrefix:'/community-dictionaries/7/words/',entryPrefix:'/community-dictionaries/7/entries/'}};
    const links=[{href:new URL('../'+next,'https://clara.test/community-dictionaries/7/placeholder/').href},
      {href:'https://evil.test/community-dictionaries/7/words/2/'},
      {href:'https://clara.test/community-dictionaries/8/words/2/'},
      {href:'https://clara.test/community-dictionaries/7/entries/5/contribute/'}];
    const original=links.slice(1).map(x=>x.href);
    vm.runInNewContext(script('game_navigation.js'),{document:{querySelector:()=>control,querySelectorAll:()=>links},URL,location:new URL(current)});
    current=links[0].href;const parsed=new URL(current);
    assert.equal(parsed.searchParams.get('return_game'),seed);assert.equal(parsed.searchParams.get('game_category'),'A & B');
    if(next.includes('picture')){assert.equal(parsed.searchParams.get('picture'),'4');assert.equal(parsed.hash,'#words');}
    assert.deepEqual(links.slice(1).map(x=>x.href),original);
  }
});
