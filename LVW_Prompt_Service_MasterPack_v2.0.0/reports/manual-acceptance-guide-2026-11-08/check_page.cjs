'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {once}=require('node:events');
const root=path.resolve(__dirname,'../..');
const report=__dirname;
const slot=process.argv[2]||'01';assert.match(slot,/^[0-9]{2}$/);
const authPath=path.join(report,'ui-authorization-'+slot+'.json');
const terminalAuthPath=path.join(report,'ui-authorization-'+slot+'.terminal.json');
const originalAuth=fs.readFileSync(authPath,'utf8');
const auth=JSON.parse(originalAuth);
const sha=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const checkAuth=()=>{
 assert.equal(fs.readFileSync(authPath,'utf8'),originalAuth);assert.equal(fs.existsSync(terminalAuthPath),false,'expired child replay');
 const parent=JSON.parse(fs.readFileSync(path.join(root,auth.program),'utf8'));
 assert.equal(parent.status,'ACTIVE');assert.equal(sha(path.join(root,auth.program)),auth.program_sha256);
 assert.equal(auth.status,'ACTIVE_ONE_SHOT');assert.ok(Date.now()/1000<auth.expires_at);
 assert.equal(sha(__filename),auth.harness_sha256);assert.equal(sha(path.join(root,'人工验收指南.html')),auth.guide_sha256);
 for(const [key,tool] of Object.entries(auth.tools))assert.equal(sha(tool.path),tool.sha256,key+' identity');
};
let server,original,temporary,baseContext;
const checks=[],errors=[],network=[];
const receipt={kind:'STATIC_GUIDE_HEADLESS_UI_CHECK_NOT_PRODUCT_ACCEPTANCE',candidate_sha:auth.candidate_sha,run_id:auth.run_id,guide_sha256:auth.guide_sha256,product_services_started:0,model_calls:0,media_decodes:0,human_signoff_submitted:false,stage_pass_claim:false,checks,decision:'NO_GO'};
const test=async(name,fn)=>{checkAuth();await fn();checks.push({name,status:'PASS'});};
(async()=>{try{
 checkAuth();
 temporary=fs.mkdtempSync(path.join(os.tmpdir(),'lvw-guide-ui-'));fs.chmodSync(temporary,0o700);
 process.env.TMPDIR=temporary;process.env.TMP=temporary;process.env.TEMP=temporary;
 process.env.XDG_CONFIG_HOME=path.join(temporary,'config');process.env.XDG_CACHE_HOME=path.join(temporary,'cache');
 const {chromium}=require(auth.tools.playwright.path);
 server=await chromium.launchServer({host:'127.0.0.1',port:0,headless:true,executablePath:auth.tools.browser.path,args:['--disable-gpu','--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--disable-extensions','--no-proxy-server']});
 original=server.process();receipt.browser_original_pid=original.pid;
 const browser=await chromium.connect(server.wsEndpoint());
 async function context(viewport,blocked=false){const ctx=await browser.newContext({viewport,acceptDownloads:true,serviceWorkers:'block'});await ctx.route(/^https?:\/\//,async route=>{network.push(route.request().url());await route.abort();});if(blocked)await ctx.addInitScript(()=>Object.defineProperty(window,'localStorage',{get(){throw new DOMException('UI-only storage denial','SecurityError');}}));return ctx;}
 baseContext=await context({width:1440,height:1000});const page=await baseContext.newPage();page.on('pageerror',e=>errors.push(e.message));
 const url=pathToFileURL(path.join(root,'人工验收指南.html')).href;
 await page.goto(url);const data=await page.locator('#guide-data').textContent();const guide=JSON.parse(data);const required=guide.checks.filter(c=>c.required);
 await test('initial state separates historical machine evidence from unsigned human review',async()=>{assert.equal(required.length,7);assert.equal(await page.locator('#progress-text').textContent(),'0 / 7');assert.equal(await page.locator('#copy-signature').isDisabled(),true);assert.equal(Object.keys(guide.machine_cases).length,9);assert.ok(Object.values(guide.machine_cases).every(v=>v==='PASS'));assert.match(await page.locator('.signature-state').first().textContent(),/尚未提交/);});
 await page.screenshot({path:path.join(report,'desktop-'+slot+'.png'),fullPage:false});
 await test('launcher selection respects actual fallback port without sending requests',async()=>{await page.locator('#port').selectOption('18770');assert.equal(await page.locator('#image-link').getAttribute('href'),'http://127.0.0.1:18770');assert.ok((await page.locator('#video-command').textContent()).includes('ffmpeg-win-x86_64-v7.1.exe'));assert.ok((await page.locator('#video-command').textContent()).includes('--base-directory $lvwSession'));});
 await test('clipboard denial provides visible manual-copy fallback',async()=>{await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw new Error('UI fixture denial');}}}));await page.locator('[data-copy="launcher-path"]').click();await page.waitForFunction(()=>!document.getElementById('copy-fallback').hidden);assert.match(await page.locator('#fallback-text').inputValue(),/START_LVW\.cmd$/);});
 await test('unavailable and issue states do not count as pass; notes survive reload',async()=>{await page.locator('[data-result="video_entry"]').selectOption('UNAVAILABLE');assert.equal(await page.locator('#progress-text').textContent(),'0 / 7');await page.locator('[data-result="video_entry"]').selectOption('ISSUE');await page.locator('[data-note="video_entry"]').fill('UI-only synthetic issue; not a product defect');await page.reload();assert.equal(await page.locator('[data-result="video_entry"]').inputValue(),'ISSUE');assert.equal(await page.locator('[data-note="video_entry"]').inputValue(),'UI-only synthetic issue; not a product defect');});
 let exported;
 await test('explicit review selections enable a proposal but export remains unsigned',async()=>{for(const c of required)await page.locator('[data-result="'+c.id+'"]').selectOption('PASS');assert.equal(await page.locator('#copy-signature').isDisabled(),true);await page.locator('#overall').fill('UI自动化模拟勾选，非真实人工体验，不是签署。');await page.locator('#scope-ack').check();assert.equal(await page.locator('#copy-signature').isDisabled(),false);const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#export').click()]);const target=path.join(temporary,'ui-notes.json');await download.saveAs(target);exported=JSON.parse(fs.readFileSync(target,'utf8'));assert.equal(exported.human_signoff_submitted,false);assert.equal(exported.stage_pass_claim,false);assert.equal(exported.record_kind,'HUMAN_EXPERIENCE_NOTES_ONLY');assert.equal(exported.proposed_signature,guide.signature);assert.equal(exported.candidate,auth.candidate_sha);});
 await test('issue in any recorded item disables the proposal',async()=>{await page.locator('[data-result="image"]').selectOption('ISSUE');assert.equal(await page.locator('#copy-signature').isDisabled(),true);await page.locator('[data-result="image"]').selectOption('NOT_TRIED');});
 await test('foreign candidate import is rejected without changing existing records',async()=>{await page.locator('#import-file').setInputFiles({name:'wrong.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({...exported,candidate:'f'.repeat(40)}))});await page.waitForFunction(()=>document.getElementById('action-status').textContent.includes('未导入'));assert.equal(await page.locator('#progress-text').textContent(),'7 / 7');});
 await test('matching import sanitizes claimed signature fields and leaves official state untouched',async()=>{page.once('dialog',d=>d.accept());await page.locator('#reset').click();assert.equal(await page.locator('#progress-text').textContent(),'0 / 7');page.once('dialog',d=>d.accept());await page.locator('#import-file').setInputFiles({name:'same.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({...exported,human_signoff_submitted:true,stage_pass_claim:true}))});await page.waitForFunction(()=>document.getElementById('progress-text').textContent==='7 / 7');const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#export').click()]);const target=path.join(temporary,'sanitized.json');await download.saveAs(target);const value=JSON.parse(fs.readFileSync(target,'utf8'));assert.equal(value.human_signoff_submitted,false);assert.equal(value.stage_pass_claim,false);});
 const mobile=await context({width:390,height:844});const mp=await mobile.newPage();mp.on('pageerror',e=>errors.push(e.message));await mp.goto(url);
 await test('mobile layout stays within viewport and starts unsigned',async()=>{assert.equal(await mp.locator('#progress-text').textContent(),'0 / 7');const sizes=await mp.evaluate(()=>({width:document.documentElement.scrollWidth,viewport:innerWidth}));assert.ok(sizes.width<=sizes.viewport+1,JSON.stringify(sizes));await mp.screenshot({path:path.join(report,'mobile-'+slot+'.png'),fullPage:false});});
 const denied=await context({width:1100,height:900},true);const dp=await denied.newPage();dp.on('pageerror',e=>errors.push(e.message));await dp.goto(url);
 await test('storage refusal keeps current input and allows unsigned download',async()=>{await dp.locator('[data-note="video_entry"]').fill('temporary UI note');assert.match(await dp.locator('#storage-status').textContent(),/不允许本地保存/);assert.equal(await dp.locator('[data-note="video_entry"]').inputValue(),'temporary UI note');const [download]=await Promise.all([dp.waitForEvent('download'),dp.locator('#export').click()]);const target=path.join(temporary,'storage-denied.json');await download.saveAs(target);const value=JSON.parse(fs.readFileSync(target,'utf8'));assert.equal(value.checks.video_entry.note,'temporary UI note');assert.equal(value.human_signoff_submitted,false);});
 assert.deepEqual(errors,[]);assert.deepEqual(network,[]);receipt.decision='STATIC_GUIDE_UI_CHECKS_PASSED_NOT_PRODUCT_OR_HUMAN_ACCEPTANCE';
 }catch(error){receipt.error=error.stack;process.exitCode=1;}
 finally{
  try{if(server){await server.close();if(original.exitCode===null&&original.signalCode===null)await Promise.race([once(original,'exit'),new Promise((_,reject)=>setTimeout(()=>reject(new Error('owned browser exit unproven')),5000))]);receipt.browser_original_terminal=original.exitCode!==null||original.signalCode!==null;}}catch(error){receipt.cleanup_error=error.message;receipt.decision='NO_GO';process.exitCode=1;}
  try{if(temporary&&(!server||receipt.browser_original_terminal)){fs.rmSync(temporary,{recursive:true});receipt.owned_temp_removed=!fs.existsSync(temporary);}}catch(error){receipt.cleanup_error=error.message;receipt.decision='NO_GO';process.exitCode=1;}
  receipt.page_errors=errors;receipt.network_requests=network;receipt.external_network_requests=network.length;receipt.finished_at=new Date().toISOString();
  fs.writeFileSync(path.join(report,'ui-receipt-'+slot+'.json'),JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
  const terminalAuth={...auth,status:'EXPIRED_'+(process.exitCode?'NO_GO':'STATIC_UI_VERIFIED'),terminal:'ui-receipt-'+slot+'.json'};
  fs.writeFileSync(terminalAuthPath,JSON.stringify(terminalAuth,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({decision:receipt.decision,checks:checks.length,errors:errors.length,network:network.length,cleanup:receipt.owned_temp_removed}));
 }
})();
