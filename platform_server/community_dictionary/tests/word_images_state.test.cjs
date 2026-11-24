const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/community_dictionary/word_images.js'), 'utf8');
function element(props = {}) {
  return Object.assign({listeners:{},textContent:'',hidden:true,disabled:false,checked:false,
    hasAttribute(){return false}, scrollIntoView(){this.scrolled=true},
    addEventListener(name, fn){this.listeners[name]=fn}, fire(name){this.listeners[name]?.({})}}, props);
}
function page(storage, ids, {server = false, supplied = {}, tokenPrefix = 'token', navHeight = 54} = {}) {
  const boxes=ids.map(id=>element({value:tokenPrefix+id,dataset:{pictureId:String(id)}}));
  const one=Object.fromEntries(['selection-tokens','selection-message','selected-count','selected-estimate','confirm-generation','selection-changed','select-visible','clear-selection','picture-selection','completed-selection','selection-controls'].map(k=>[k,element()]));
  const next=element({hasAttribute(name){return name==='data-return-to-selection'}});
  const link=element(); const bulk=[element(),element()]; let scroll;
  let observer, offset;
  const navigation={getBoundingClientRect(){return {height:navHeight}}};
  const root={dataset:{storageKey:'fixture',unitMicro:'508750',serverSelection:server?'1':'0',limitMessage:'At most 50',completedEntries:'1 2'},
    style:{setProperty(name,value){assert.equal(name,'--picture-nav-offset');offset=value}},
    querySelector(selector){return one[selector.slice(6,-1)]},
    querySelectorAll(selector){return selector==='[data-picture-id]'?boxes:selector==='[data-bulk-button]'?bulk:selector==='[data-clear-selection]'?[one['clear-selection'],next]:[link]}};
  vm.runInNewContext(source,{document:{querySelectorAll(){return []},querySelector(){return navigation},getElementById(id){return id==='word-picture-overview'?root:{textContent:JSON.stringify(supplied)}}},
    ResizeObserver:class {constructor(fn){observer=fn}observe(element){assert.equal(element,navigation)}},
    sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
    window:{scrollY:337,scrollTo:(x,y)=>{scroll=y}},requestAnimationFrame:fn=>fn(),location:{hash:'#word-image-progress'}});
  return {boxes,one,bulk,link,next,get scroll(){return scroll},get offset(){return offset},resizeNav(height){navHeight=height;observer()}};
}
test('sticky selection controls stay below the navigation when it wraps',()=>{
  const p=page(new Map(),[1],{navHeight:54});
  assert.equal(p.offset,'54px');
  p.resizeNav(112);assert.equal(p.offset,'112px');
});
test('selection and estimate survive more words and progress refresh, with fresh signatures',()=>{
  const store=new Map();const first=page(store,[1,2]);
  first.one['select-visible'].fire('click');assert.equal(first.one['selected-estimate'].textContent,'1.02');
  first.link.fire('click');const more=page(store,[1,2,3,4],{tokenPrefix:'fresh'});
  assert.equal(more.one['selected-count'].textContent,'2');assert.equal(more.scroll,337);
  assert.deepEqual(JSON.parse(more.one['selection-tokens'].value),['fresh1','fresh2']);
  more.one['clear-selection'].fire('click');assert.equal(more.one['selected-count'].textContent,'0');
  assert.equal(more.bulk[0].disabled,true);
});
test('bulk selection is capped at 50 and changing selection invalidates cost confirmation',()=>{
  const p=page(new Map(),Array.from({length:51},(_,i)=>i+1));p.one['select-visible'].fire('click');
  assert.equal(p.one['selected-count'].textContent,'50');assert.equal(p.boxes[50].checked,false);
  assert.equal(p.one['selection-message'].hidden,false);
  p.boxes[50].checked=true;p.boxes[50].fire('change');assert.equal(p.boxes[50].checked,false);
  assert.equal(p.one['selection-message'].textContent,'At most 50');
  assert.equal(p.one['confirm-generation'].disabled,true);assert.equal(p.one['selection-changed'].hidden,false);
});
test('a restored full selection explains the limit before another checkbox is clicked',()=>{
  const selected=Object.fromEntries(Array.from({length:50},(_,i)=>[i+1,'old'+i]));
  const p=page(new Map([['fixture',JSON.stringify({selected})]]),[51,52]);
  assert.equal(p.one['selection-message'].textContent,'At most 50');
  assert.equal(p.one['selection-message'].hidden,false);
  assert.equal(p.one['completed-selection'].hidden,false);
  p.next.fire('click');
  assert.equal(p.one['selected-count'].textContent,'0');
  assert.equal(p.one['selection-message'].hidden,true);
  assert.equal(p.one['completed-selection'].hidden,true);
  assert.equal(p.one['selection-controls'].scrolled,true);
  assert.equal(p.one['confirm-generation'].disabled,true);
  p.boxes[0].checked=true;p.boxes[0].fire('change');
  assert.equal(p.one['selected-count'].textContent,'1');
  assert.equal(p.one['completed-selection'].hidden,true);
  assert.deepEqual(JSON.parse(p.one['selection-tokens'].value),['token51']);
});
test('server-approved selection replaces a stale stored selection',()=>{
  const store=new Map([['fixture',JSON.stringify({selected:{99:'old'}})]]);
  const p=page(store,[1,2],{server:true,supplied:{1:'approved'}});
  assert.equal(p.one['selected-count'].textContent,'1');assert.deepEqual(JSON.parse(p.one['selection-tokens'].value),['token1']);
  assert.equal(p.one['confirm-generation'].disabled,false);
});
