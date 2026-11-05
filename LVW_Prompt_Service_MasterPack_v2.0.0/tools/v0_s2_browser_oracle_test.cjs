const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {same, waitForEmptyGroup, FIELDS, withUiAction} = require('./v0_s2_browser_acceptance.cjs');
(async () => {
 const actual=JSON.parse(fs.readFileSync(path.join(__dirname,'../reports/v0-s2/browser-draft-oracle-correction-01/initial-manual-export.json')));
 const expected={...FIELDS,tags:['人工','local']};
 assert.notEqual(JSON.stringify(actual.draft),JSON.stringify(expected));
 same(actual.draft,expected,'valid original export');
 for(const mutate of [d=>{d.natural_en+=' changed';},d=>{d.tags.reverse();},d=>{delete d.negative;},
   d=>{d.extra='unexpected';},d=>{d.image_prompt=1;}]){
   const bad=structuredClone(actual.draft);mutate(bad);
   assert.throws(()=>same(bad,expected,'DRAFT_CHANGED'),/DRAFT_CHANGED/);
 }
 let reads=0,clock=0;
 assert.equal(await waitForEmptyGroup(1,{members:()=>++reads<3?[{}]:[],now:()=>clock,sleep:async ms=>{clock+=ms;}}),true);
 assert.equal(reads,3);
 clock=0;
 assert.equal(await waitForEmptyGroup(1,{members:()=>[{}],now:()=>clock,sleep:async ms=>{clock+=ms;}}),false);
 assert.equal(clock,5000);
 for (const elapsed of [5000,5001]) {
   clock=0;reads=0;
   assert.equal(await waitForEmptyGroup(1,{members:()=>++reads===1?[{}]:[],now:()=>clock,sleep:async()=>{clock=elapsed;}}),elapsed===5000);
 }
 const unhandled=[];const observe=error=>unhandled.push(error.message);process.on('unhandledRejection',observe);
 try {
   for (const sync of [true,false]) {
     let rejectLater;const waiting=new Promise((resolve,reject)=>{rejectLater=reject;});
     const action=sync?()=>{throw Error('UI failed');}:async()=>{throw Error('UI failed');};
     await assert.rejects(withUiAction(waiting,action),/UI failed/);
     rejectLater(Error('browser closed'));
     await new Promise(resolve=>setImmediate(resolve));
   }
   assert.deepEqual(unhandled,[]);
   let actions=0;assert.equal(await withUiAction(Promise.resolve('real response'),async()=>{actions++;}),'real response');assert.equal(actions,1);
 } finally {process.removeListener('unhandledRejection',observe);}
 console.log('Original browser export semantics and finite process-exit boundaries passed.');
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
