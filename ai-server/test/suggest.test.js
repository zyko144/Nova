import {test} from 'node:test';
import assert from 'node:assert/strict';
import handler,{permitted,clean} from '../api/suggest.js';
test('private input is rejected',()=>{assert.ok(permitted('mai'));for(const q of ['https://private.test','a@example.test','gsk_secret','a\nsecret'])assert.equal(permitted(q),false);});
test('provider output is bounded and sanitized',()=>assert.deepEqual(clean(['maison','mail','maison','https://bad.test',42,'mairie','extra'],'mai'),['maison','mail','mairie']));
test('invalid requests never call provider',async()=>{
  let calls=0;const original=globalThis.fetch;globalThis.fetch=()=>{calls++;throw Error();};
  const res={setHeader(){},status(v){this.code=v;return this;},json(v){this.body=v;}};
  try{await handler({method:'POST',headers:{},body:{query:'gsk_secret'}},res);assert.equal(res.code,400);assert.equal(calls,0);}finally{globalThis.fetch=original;}
});
