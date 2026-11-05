const assert=require('node:assert/strict'),vm=require('node:vm'),crypto=require('node:crypto');
const {installFetchObserver,captureBrowserResponse}=require('./v0_s2_browser_fetch_observer.cjs');
const origin='http://127.0.0.1:8191',url=origin+'/api/lvw/v0/video/upload',nonce='a'.repeat(64);
const digest=value=>crypto.createHash('sha256').update(value).digest('hex');
function environment(fetch){
 const context=vm.createContext({fetch,URL,Request,TextDecoder,crypto:crypto.webcrypto,location:{href:origin+'/'},config:{nonce,origin}});
 vm.runInContext('('+installFetchObserver.toString()+')(config)',context);return context;
}
async function ready(context,query){
 for(let i=0;i<100;i++){const row=context.__lvwReadFetchEvidence(query);if(row)return row;await new Promise(r=>setTimeout(r,1));}
 throw Error('test observation timeout');
}
(async()=>{
 const raw='{"actual":"真实返回"}',input='sample bytes',options={method:'POST',body:input,headers:{'X-LVW-Control':'local-ui'}};
 let calls=0;const response=new Response(raw,{status:201});
 const context=environment(async(...args)=>{calls++;assert.equal(args[0],url);assert.equal(args[1],options);return response;});
 const actual=await context.fetch(url,options);assert.equal(actual,response);assert.equal(await actual.text(),raw);assert.equal(calls,1);
 const query={nonce,url,method:'POST',status:201,request_sha256:digest(input)};
 const row=await ready(context,query);assert.equal(row.raw_utf8,raw);assert.equal(row.sha256,digest(raw));assert.equal(row.bytes,Buffer.byteLength(raw));
 assert.equal(context.__lvwReadFetchEvidence(query),null);assert.throws(()=>context.__lvwReadFetchEvidence({...query,nonce:'wrong'}));
 let inputSame=false;const request=new Request(url,{method:'POST',body:'original request'});
 const second=environment(async passed=>{inputSame=passed===request;assert.equal(await passed.text(),'original request');return new Response(raw,{status:201});});
 await second.fetch(request);await ready(second,{...query,request_sha256:digest('original request')});assert.equal(inputSame,true);
 const third=environment(async()=>new Response(raw,{status:201}));await third.fetch(url,options);
 const browserResponse={finished:async()=>null,request:()=>({method:()=> 'POST',postDataBuffer:()=>Buffer.from(input)}),url:()=>url,status:()=>201,
  body:async()=>{throw Error('inspector cache unavailable');}};
 const page={async evaluate(fn,q){return third.__lvwReadFetchEvidence(q);}};
 const captured=await captureBrowserResponse(page,browserResponse,nonce);assert.equal(captured.body.toString(),raw);
 await assert.rejects(captureBrowserResponse(page,{...browserResponse,finished:async()=>Error('transfer failed')},nonce),/transfer failed/);
 const broken=environment(async()=>new Response(new Uint8Array([0xff]),{status:201}));await broken.fetch(url,options);
 await assert.rejects(ready(broken,query),/FETCH_EVIDENCE_INVALID/);
 console.log('Native fetch arguments/response identity, exact bytes, one-shot binding and cache-independent observation verified.');
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
