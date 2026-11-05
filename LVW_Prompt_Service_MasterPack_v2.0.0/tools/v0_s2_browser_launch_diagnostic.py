"""Finite, blank-page Chromium filesystem diagnostic; no services or media."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import time

from tools import v0_verification_authority as auth
from tools import v0_s2_stage_checkpoint as cp
from tools.v0_s2_seal import seal_candidate

HARNESS = 'tools/v0_s2_browser_launch_diagnostic.py'
NODE = r'''
const fs = require('fs'), cp = require('child_process');
const config = JSON.parse(fs.readFileSync(process.argv[1]));
const originals = [], spawn = cp.spawn;
cp.spawn = function(command, args, options) {
  const child = spawn.call(this, command, args, options);
  if (command === config.browser) {
    const stat = fs.readFileSync(`/proc/${child.pid}/stat`, 'utf8');
    const fields = stat.slice(stat.lastIndexOf(')')+2).split(' ');
    originals.push({pid: child.pid, group: Number(fields[2]), birth: fields[19], child});
  }
  return child;
};
(async () => {
 const {chromium} = require(config.playwright);
 let server; const result = {decision: 'NO_GO', media_reads: 0, provider_calls: 0};
 try {
   server = await chromium.launchServer({host:'127.0.0.1', port:0, headless:true,
     executablePath:config.browser, timeout:15000,
     args:['--disable-gpu','--disable-background-networking','--disable-component-update',
       '--disable-sync','--no-first-run','--disable-extensions','--no-proxy-server',
       '--host-resolver-rules=MAP * ~NOTFOUND','--enable-logging=stderr']});
   result.decision='BLANK_BROWSER_LAUNCHED_NOT_PRODUCT_ACCEPTANCE';
 } catch(e) { result.error = e.message; }
 finally {
   if(server) await server.close();
   result.originals=originals.map(({pid,group,birth,child})=>({pid,group,birth,
     exited:child.exitCode!==null||child.signalCode!==null,exit_code:child.exitCode,signal:child.signalCode}));
   console.log(JSON.stringify(result));
 }
})().catch(e=>{console.error(e.stack);process.exitCode=1;});
'''


def run(candidate):
    program=cp.repository_json(auth.PROGRAM); auth.validate(program,'V0-S2')
    sealed=seal_candidate(cp.ROOT,candidate,['tools',auth.PROGRAM])
    previous=cp.STATE_ROOT/'full-v0-auto-02/terminal.json'
    receipt=cp.repository_json('reports/v0-s2/full-v0-auto-02/receipt.json')
    if cp.file_hash(previous)!=receipt['raw_terminal_sha256']:raise ValueError('original terminal changed')
    tools=json.loads(previous.read_bytes())['runtime_evidence']['default']['binding_proof']['tool_bindings']
    selected={k:tools[k] for k in ['node_executable','browser_executable','playwright_module']}
    for tool in selected.values():
        if cp.file_hash(Path(tool['path']))!=tool['sha256']:raise ValueError('bound tool changed')
    run_id='browser-launch-diagnostic-01'
    budget={'browser_starts':2,'provider_calls':0,'media_reads':0,'service_starts':0,'downloads':0,'cloud_calls':0,'paid_calls':0}
    child=auth.child(program,stage='V0-S2',run_id=run_id,candidate=candidate,
        harness_sha256=cp.file_hash(cp.ROOT/HARNESS),program_sha256=cp.file_hash(cp.ROOT/auth.PROGRAM),budget=budget,max_seconds=180)
    child.update(tools=selected,source_payload_sha256=sealed['payload_sha256'],ports='ephemeral loopback driver only',
        cleanup='original unreaped children only; preserve uncertain directories; never read existing browser profiles')
    directory=cp.STATE_ROOT/run_id; directory.mkdir(exist_ok=False)
    cp.write_new(directory/'active-child.json',child); (directory/'lease.closed').write_bytes(b'0')
    result={'run_id':run_id,'candidate_sha':candidate,'decision':'NO_GO','stage_pass_claim':False,'attempts':[]}
    try:
        for label,base in [('drvfs',directory),('linux',Path('/tmp'))]:
            if time.time()>=child['expires_at'] or cp.file_hash(cp.ROOT/auth.PROGRAM)!=child['program_sha256']:raise ValueError('child expired/revoked')
            temporary=Path(tempfile.mkdtemp(prefix='lvw-browser-diagnostic-',dir=base))
            original=temporary.stat()
            cfg=directory/(label+'-config.json')
            cp.write_new(cfg,{'browser':selected['browser_executable']['path'],'playwright':selected['playwright_module']['path']})
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','TZ':'UTC','TMPDIR':str(temporary),'TMP':str(temporary),'TEMP':str(temporary),
                'XDG_CONFIG_HOME':str(temporary/'config'),'XDG_CACHE_HOME':str(temporary/'cache'),'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD':'1','NO_PROXY':'127.0.0.1,localhost'}
            output=subprocess.run([selected['node_executable']['path'],'-e',NODE,str(cfg)],env=env,capture_output=True,timeout=35)
            (directory/(label+'-stdout.log')).write_bytes(output.stdout);(directory/(label+'-stderr.log')).write_bytes(output.stderr)
            if output.returncode or len(output.stdout)>65536 or len(output.stderr)>262144:raise ValueError('diagnostic child or output failure; preserve temp')
            row=json.loads(output.stdout); row.update(label=label,temporary_root=str(temporary),exit_code=output.returncode)
            row['cleanup_proven']=bool(row['originals']) and all(p['exited'] for p in row['originals'])
            # Read kernel state only; do not kill a claimed/reused process.
            groups={p['group'] for p in row['originals']}; survivors=[]
            for process in Path('/proc').iterdir():
                if not process.name.isdecimal():continue
                try:
                    raw=(process/'stat').read_text();fields=raw[raw.rfind(')')+2:].split()
                    if int(fields[2]) in groups:survivors.append(int(process.name))
                except (FileNotFoundError,ProcessLookupError):pass
            row['group_survivors']=survivors
            row['remaining_entries']=[p.name for p in temporary.iterdir()]
            row['cleanup_proven'] &= not survivors
            current=temporary.lstat()
            if temporary.is_symlink() or (current.st_dev,current.st_ino)!=(original.st_dev,original.st_ino):raise ValueError('diagnostic temp identity changed')
            if row['cleanup_proven']:
                shutil.rmtree(temporary)
                row['cleanup_proven']=not temporary.exists()
            result['attempts'].append(row)
            if not row['cleanup_proven']:raise ValueError('diagnostic cleanup unproven')
        result['decision']='BROWSER_FILESYSTEM_DIAGNOSED_NOT_PRODUCT_ACCEPTANCE'
    except Exception as error:result['error_code']=type(error).__name__+':'+str(error)
    finally:
        cp.write_new(directory/'terminal.json',result);(directory/'lease.closed').write_bytes(b'1')
        cp.write_new(directory/'terminal-child.json',auth.expire(child,'COMPLETE' if result['decision'].startswith('BROWSER_FILESYSTEM') else 'NO_GO','terminal.json'))
        public={'run_id':run_id,'candidate_sha':candidate,'decision':result['decision'],'stage_pass_claim':False,
            'attempts':[{k:row[k] for k in ['label','decision','exit_code','cleanup_proven']} for row in result['attempts']],
            'raw_terminal_sha256':cp.file_hash(directory/'terminal.json'),'budget':budget}
        report=cp.ROOT/'reports/v0-s2'/run_id;report.mkdir(exist_ok=False);cp.write_new(report/'receipt.json',public)
    return public


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',required=True)
    print(json.dumps(run(parser.parse_args().candidate)))
