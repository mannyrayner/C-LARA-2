const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../static/community_dictionary/word_images.js'), 'utf8');
function element(props = {}) {
  return Object.assign({listeners:{},textContent:'',hidden:true,disabled:false,checked:false,
    addEventListener(name, fn){this.listeners[name]=fn}, fire(name){this.listeners[name]?.({})}}, props);
}
function page(storage, ids, {server = false, supplied = {}, tokenPrefix = 'token'} = {}) {
  const boxes=ids.map(id=>element({value:tokenPrefix+id,dataset:{pictureId:String(id)}}));
  const one=Object.fromEntries(['selection-tokens','selection-message','selected-count','selected-estimate','confirm-generation','selection-changed','select-visible','clear-selection','picture-selection'].map(k=>[k,element()]));
  const link=element(); const bulk=[element(),element()]; let scroll;
  const root={dataset:{storageKey:'fixture',unitMicro:'508750',serverSelection:server?'1':'0',limitMessage:'At most 50'},
    querySelector(selector){return one[selector.slice(6,-1)]},
    querySelectorAll(selector){return selector==='[data-picture-id]'?boxes:selector==='[data-bulk-button]'?bulk:[link]}};
  vm.runInNewContext(source,{document:{querySelectorAll(){return []},getElementById(id){return id==='word-picture-overview'?root:{textContent:JSON.stringify(supplied)}}},
    sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
    window:{scrollY:337,scrollTo:(x,y)=>{scroll=y}},requestAnimationFrame:fn=>fn(),location:{hash:'#word-image-progress'}});
  return {boxes,one,bulk,link,get scroll(){return scroll}};
}
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
  p.boxes[50].checked=true;p.boxes[50].fire('change');assert.equal(p.boxes[50].checked,false);
  assert.equal(p.one['selection-message'].textContent,'At most 50');
  assert.equal(p.one['confirm-generation'].disabled,true);assert.equal(p.one['selection-changed'].hidden,false);
});
test('server-approved selection replaces a stale stored selection',()=>{
  const store=new Map([['fixture',JSON.stringify({selected:{99:'old'}})]]);
  const p=page(store,[1,2],{server:true,supplied:{1:'approved'}});
  assert.equal(p.one['selected-count'].textContent,'1');assert.deepEqual(JSON.parse(p.one['selection-tokens'].value),['token1']);
  assert.equal(p.one['confirm-generation'].disabled,false);
});
