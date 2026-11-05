"""One no-model native page diagnosis; not complete Stage acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace

from tools import v0_verification_authority as auth
from tools import v0_s2_stage_checkpoint as cp
from tools.v0_s2_compute_diagnostic import Driver
from tools.v0_s2_seal import seal_candidate
from tools.v0_s2_stage_archive import OwnedArchive
from tools import v0_s2_browser_temp as scratch

HARNESS='tools/v0_s2_manual_page_diagnostic.py'
NODE=r'''
const fs=require('fs'),cp=require('child_process'),crypto=require('crypto');
const config=JSON.parse(fs.readFileSync(process.argv[1]));
const spawn=cp.spawn,originals=[];
cp.spawn=function(command,args,options){
 const child=spawn.call(this,command,args,options);
 if(command===config.browser){const raw=fs.readFileSync(`/proc/${child.pid}/stat`,'utf8');const f=raw.slice(raw.lastIndexOf(')')+2).split(' ');
 const row={pid:child.pid,group:Number(f[2]),birth:f[19],child};originals.push(row);
 fs.appendFileSync(config.output+'.processes.jsonl',JSON.stringify({event:'spawn',pid:row.pid,group:row.group,birth:row.birth})+'\n');
 child.once('exit',(code,signal)=>fs.appendFileSync(config.output+'.processes.jsonl',JSON.stringify({event:'exit',pid:row.pid,group:row.group,birth:row.birth,code,signal})+'\n'));}
 return child;
};
(async()=>{
 const {chromium}=require(config.playwright);let server,browser,context,page;
 const result={decision:'NO_GO',stage_pass_claim:false,errors:[],network:[],phases:[],provider_calls:0};
 const save=()=>fs.writeFileSync(config.output,JSON.stringify(result,null,2));
 let preview=0,userWrites=0,uploads=0,phase='boot';
 try{
 server=await chromium.launchServer({host:'127.0.0.1',port:0,headless:true,executablePath:config.browser,timeout:15000,
 args:['--disable-gpu','--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--disable-extensions','--no-proxy-server']});
 browser=await chromium.connect(server.wsEndpoint());context=await browser.newContext({viewport:{width:1600,height:1200},serviceWorkers:'block',acceptDownloads:true});
 await context.routeWebSocket('**/*',route=>{
  const u=new URL(route.url());if(u.protocol==='ws:'&&u.host==='127.0.0.1:8191'&&u.pathname==='/ws')return route.connectToServer();
  return route.close({code:1008,reason:'local-only'});
 });
 await context.route('**/*',async route=>{
  const req=route.request(),u=new URL(req.url()),raw=req.postDataBuffer();
  let allowed=u.origin==='http://127.0.0.1:8191'&&(req.method()==='GET'||req.method()==='HEAD');
  if(u.origin==='http://127.0.0.1:8191'&&raw&&raw.length<=131072){
   if(req.method()==='POST'&&u.pathname.replace(/^\/api/,'')==='/lvw/v0/video/workbench'){
    const b=JSON.parse(raw);allowed=b.action==='preview'&&++preview<=1;
   }else if(req.method()==='POST'&&u.pathname.replace(/^\/api/,'')==='/lvw/v0/video/upload'&&config.sample){
    allowed=++uploads<=1&&raw.length===config.sample.bytes&&crypto.createHash('sha256').update(raw).digest('hex')===config.sample.sha256;
   }else if(['POST','PUT','DELETE'].includes(req.method())&&(/^\/api\/(userdata|settings)\//.test(u.pathname)||u.pathname==='/api/settings'))allowed=++userWrites<=16;
  }
  if(result.network.length>=4096)throw Error('NETWORK_BOUND');
  result.network.push({method:req.method(),path:u.pathname,allowed});
  return allowed?route.continue():route.abort('blockedbyclient');
 });
 page=await context.newPage();
 page.on('pageerror',e=>{if(result.errors.length<16)result.errors.push({phase,time:Date.now(),message:e.message,stack:e.stack});save();});
 await page.goto('http://127.0.0.1:8191',{waitUntil:'domcontentloaded',timeout:30000});
 if(config.readiness)await require(config.readiness).waitForHost(page);
 else await page.waitForFunction(()=>window.comfyAPI?.app?.app?.graph&&window.comfyAPI.app.app.canvas,null,{timeout:30000});
 if(config.dismissStartup)await require(config.readiness).dismissStartupTemplates(page);
 const observe=async name=>{result.phases.push({name,...await page.evaluate(()=>({
  nodes:window.comfyAPI.app.app.graph._nodes?.length,canvas_id:window.comfyAPI.app.app.canvas?.canvas?.id,
  host_setup_complete:window.app===window.comfyAPI.app.app,configuring:window.comfyAPI.app.app.configuringGraph,
  graph_sequence:window.comfyAPI.app.app.graphLoadSequence,committed_sequence:window.comfyAPI.app.app.committedGraphLoadSequence,
  canvases:[...document.querySelectorAll('canvas')].map(c=>({id:c.id,connected:c.isConnected,width:c.width,height:c.height})),
  fields:document.querySelectorAll('[data-lvw-field]').length
 }))});save();};
 await observe('legacy-ready');
 phase='load-workflow';await page.evaluate(async graph=>{const {app}=await import('/scripts/app.js');await app.loadGraphData(graph);},config.graph);
 await page.locator('[data-lvw-field]').first().waitFor({timeout:15000});await observe(phase);
 const worker=config.oracle?require(config.oracle):null;
 phase='edit';for(const name of ['natural_zh','natural_en','image_prompt','video_prompt','tags','negative','edit_instruction'])await page.locator(`[data-lvw-field="${name}"]`).fill(worker?worker.FIELDS[name]:'manual '+name);
 await page.screenshot({path:config.screenshot,fullPage:true,timeout:10000});
 phase='export';const [item]=await Promise.all([page.waitForEvent('download',{timeout:20000}),
   page.getByRole('button',{name:'导出人工稿 JSON',exact:true}).click({timeout:15000})]);
 await item.saveAs(config.export);await observe(phase);
 if(worker){
  const exported=JSON.parse(fs.readFileSync(config.export));worker.same(exported.draft,{...worker.FIELDS,tags:['人工','local']},'INITIAL_MANUAL_DRAFT_CHANGED');
  const canvas=page.locator('#graph-canvas');await canvas.focus();result.main_canvas_focused=await canvas.evaluate(element=>document.activeElement===element);
  if(!result.main_canvas_focused)throw Error('NATIVE_CANVAS_FOCUS_UNPROVEN');
 }
 if(config.sample){
  phase='upload';const captured=await worker.withUiAction(page.waitForResponse(r=>{
   const u=new URL(r.url());return u.origin==='http://127.0.0.1:8191'&&u.pathname.replace(/^\/api/,'')==='/lvw/v0/video/upload'&&r.request().method()==='POST';
  }).then(worker.captureResponse),()=>page.getByLabel('选择并上传 MP4 或 MOV 视频，最大 256 MiB、60 秒',{exact:true}).setInputFiles(config.sample.path));
  result.upload={status:captured.response.status(),body:worker.responseJson(captured),response_sha256:crypto.createHash('sha256').update(captured.body).digest('hex')};
  if(result.upload.status!==201||typeof result.upload.body.video_reference!=='string')throw Error('ACTUAL_UPLOAD_INVALID');
  await observe(phase);
 }
 await page.screenshot({path:config.screenshot,fullPage:true,timeout:10000});
 result.decision=result.errors.length?'PAGE_FAULT_CAPTURED_NOT_PRODUCT_ACCEPTANCE':'MANUAL_PAGE_DIAGNOSED_NOT_PRODUCT_ACCEPTANCE';
 }catch(e){result.error=e.stack;if(page)await page.screenshot({path:config.screenshot,timeout:10000}).catch(()=>{});}
 finally{
  if(server)await server.close();
  result.originals=originals.map(({pid,group,birth,child})=>({pid,group,birth,exited:child.exitCode!==null||child.signalCode!==null}));save();
 }
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
'''


def run(candidate,run_id):
    if run_id not in {'manual-page-diagnostic-01','manual-page-diagnostic-02','manual-page-diagnostic-03','manual-page-diagnostic-04','manual-page-diagnostic-05','manual-page-diagnostic-06','manual-page-diagnostic-07'}:raise ValueError('finite diagnostic ID required')
    parent=cp.repository_json(auth.PROGRAM);auth.validate(parent,'V0-S2')
    identity=seal_candidate(cp.ROOT,candidate,['tools','LVW_V0_RuntimePatch',auth.PROGRAM,'reports/v0-s1/wp-s1-03-phase-a/live_probe.py'])
    old=cp.STATE_ROOT/'full-v0-auto-03/terminal.json';receipt=cp.repository_json('reports/v0-s2/full-v0-auto-03/receipt.json')
    if cp.file_hash(old)!=receipt['raw_terminal_sha256']:raise ValueError('historical terminal changed')
    tools=json.loads(old.read_bytes())['runtime_evidence']['default']['binding_proof']['tool_bindings']
    for row in tools.values():
        if cp.file_hash(Path(row['path']))!=row['sha256']:raise ValueError('critical tool changed')
    sample=cp.repository_json('reports/v0-s2/frozen-structural-inputs-02.json')['categories']['tracking'] if run_id=='manual-page-diagnostic-07' else None
    budget={'comfy_starts':1,'ollama_starts':0,'browser_starts':1,'provider_calls':0,'media_reads':int(sample is not None),'uploads':int(sample is not None),'public_submissions':0,
        'manual_previews':1,'user_writes':16,'downloads':0,'cloud_calls':0,'paid_calls':0,'native_commands':128}
    child=auth.child(parent,stage='V0-S2',run_id=run_id,candidate=candidate,harness_sha256=cp.file_hash(cp.ROOT/HARNESS),
        program_sha256=cp.file_hash(cp.ROOT/auth.PROGRAM),budget=budget,max_seconds=600)
    child.update(tool_bindings=tools,command_executables={tools['powershell']['path']:tools['powershell']['sha256']},
        source_payload_sha256=identity['payload_sha256'],ports=[8191],cleanup='original registered root and owned PID/birth only; preserve uncertainty')
    if sample is not None:child['fixed_sample']={k:sample[k] for k in ['path','bytes','sha256']}
    directory=cp.STATE_ROOT/run_id;directory.mkdir(exist_ok=False);cp.write_new(directory/'active-child.json',child)
    (directory/'lease.closed').write_bytes(b'0')
    authorization_sha=hashlib.sha256(cp.canonical(child)).hexdigest()
    archive=OwnedArchive(directory,run_id=run_id,candidate_sha=candidate,authorization_sha256=authorization_sha,authorize=lambda *args:None)
    result={'run_id':run_id,'candidate_sha':candidate,'decision':'NO_GO','stage_pass_claim':False,'provider_calls':0,'media_reads':int(sample is not None)}
    driver=root=context=temporary=lease=None
    try:
        root=Path(tempfile.mkdtemp(prefix='lvw-manual-diag-',dir=directory)).resolve();archive.register(root,'default')
        for name in ['input','output','temp','custom_nodes']:(root/name).mkdir()
        args=SimpleNamespace(run_id=run_id,max_public_submissions=1,max_loopback_requests=256,max_native_clock_reads=16,
            warm_benchmark=False,native_audit=False,ffprobe_exe=None,
            **{name:tools[name]['path'] for name in ['powershell','comfy_python','comfy_main','ollama_exe','ffmpeg_exe','nvidia_exe']})
        driver=Driver(args,{'owned_run_root':str(root)},directory,child)
        context=SimpleNamespace(root=root,driver=driver,binding={'candidate_sha':candidate,'authorization_sha256':authorization_sha})
        source=cp.ROOT/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge';target=root/'custom_nodes/lvw_v0_bridge'
        shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        prefix='LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/'
        expected={p[len(prefix):]:d for p,d in identity['execution_artifact_sha256'].items() if p.startswith(prefix)}
        if {p.relative_to(target).as_posix():cp.file_hash(p) for p in target.rglob('*') if p.is_file()}!=expected:raise ValueError('deployed source mismatch')
        copied_sample=None
        if sample is not None:
            driver.guard();source_sample=cp.ROOT/sample['path'];raw=source_sample.read_bytes()
            if len(raw)!=sample['bytes'] or len(raw)>131072 or hashlib.sha256(raw).hexdigest()!=sample['sha256']:raise ValueError('fixed component sample changed')
            copied_sample=root/'input/component-tracking.mov';copied_sample.write_bytes(raw)
        driver._powershell("$x=Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue|Where-Object {$_.LocalPort -in 8191,11434};if(@($x).Count){throw 'PORT_BUSY'}")
        driver.start_comfy(root,root/'comfy.log')
        bind={'run_id':run_id,'candidate_sha':candidate,'authorization_sha256':authorization_sha}
        temporary,lease=scratch.create(bind,root/'temp')
        config={'browser':tools['browser_executable']['path'],'playwright':tools['playwright_module']['path'],
            'readiness':str(cp.ROOT/'tools/v0_s2_browser_readiness.cjs') if run_id not in {'manual-page-diagnostic-01','manual-page-diagnostic-02'} else None,
            'dismissStartup':run_id in {'manual-page-diagnostic-05','manual-page-diagnostic-06','manual-page-diagnostic-07'},
            'oracle':str(cp.ROOT/'tools/v0_s2_browser_acceptance.cjs') if run_id in {'manual-page-diagnostic-06','manual-page-diagnostic-07'} else None,
            'sample':{'path':str(copied_sample),'bytes':sample['bytes'],'sha256':sample['sha256']} if sample is not None else None,
            'graph':cp.repository_json('LVW_V0_RuntimePatch/workflows/video_reverse_prompt_v0.ui.json'),
            'output':str(root/'temp/page-result.json'),'export':str(root/'temp/manual-export.json'),'screenshot':str(root/'temp/page.png')}
        cfg=root/'temp/page-config.json';cp.write_new(cfg,config)
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','TMPDIR':str(temporary),'TMP':str(temporary),'TEMP':str(temporary),
            'XDG_CONFIG_HOME':str(temporary/'config'),'XDG_CACHE_HOME':str(temporary/'cache'),'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD':'1','NO_PROXY':'127.0.0.1,localhost'}
        output=subprocess.run([tools['node_executable']['path'],'-e',NODE,str(cfg)],capture_output=True,env=env,timeout=150)
        (root/'temp/node-stdout.log').write_bytes(output.stdout);(root/'temp/node-stderr.log').write_bytes(output.stderr)
        page=json.loads((root/'temp/page-result.json').read_bytes());result['page']=page
        groups={r['group'] for r in page['originals']};survivors=[]
        for p in Path('/proc').iterdir():
            if not p.name.isdecimal():continue
            try:
                raw=(p/'stat').read_text();fields=raw[raw.rfind(')')+2:].split()
                if int(fields[2]) in groups:survivors.append(int(p.name))
            except (FileNotFoundError,ProcessLookupError):pass
        if output.returncode or not groups or survivors or not all(r['exited'] for r in page['originals']):raise ValueError('browser exit unproven')
        result['scratch_cleanup']=scratch.remove(temporary,lease,independent_cleanup={'decision':'BROWSER_CLEANUP_PROVEN'},node_terminal=True,callbacks_pending=0)
        driver.guard()
        if seal_candidate(cp.ROOT,candidate,['tools','LVW_V0_RuntimePatch',auth.PROGRAM,'reports/v0-s1/wp-s1-03-phase-a/live_probe.py'])!=identity:raise ValueError('diagnostic source changed')
        result['decision']='MANUAL_PAGE_OBSERVED_NOT_STAGE_ACCEPTANCE'
    except BaseException as error:result['error_code']=type(error).__name__+':'+str(error)
    finally:
        if driver is not None:
            driver.cleanup_mode=True
            try:
                result['cleanup']=driver.cleanup()
                if result['cleanup']['proven'] and result.get('scratch_cleanup',{}).get('proven'):result['archive']=archive(context,result['cleanup'])
            except Exception as error:result['cleanup_error']=type(error).__name__+':'+str(error)
        result['root_retained']=root is not None and root.exists()
        result['commands']=driver.commands if driver else []
        cp.write_new(directory/'terminal.json',result);(directory/'lease.closed').write_bytes(b'1')
        cp.write_new(directory/'terminal-child.json',auth.expire(child,'COMPLETE' if result['decision'].startswith('MANUAL_PAGE_OBSERVED') else 'NO_GO','terminal.json'))
        report=cp.ROOT/'reports/v0-s2'/run_id;report.mkdir(exist_ok=False)
        public={k:result[k] for k in ['run_id','candidate_sha','decision','stage_pass_claim','provider_calls','media_reads','root_retained']}
        public.update(raw_terminal_sha256=cp.file_hash(directory/'terminal.json'),cleanup_proven=result.get('cleanup',{}).get('proven',False),
            browser_decision=result.get('page',{}).get('decision'),page_error_count=len(result.get('page',{}).get('errors',[])),
            upload_status=result.get('page',{}).get('upload',{}).get('status'))
        cp.write_new(report/'receipt.json',public)
    return public


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',required=True);parser.add_argument('--run-id',required=True)
    args=parser.parse_args();print(json.dumps(run(args.candidate,args.run_id)))
