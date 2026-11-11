"""Independent adaptation of correction-01 owner counterexample; synthetic only."""
import pathlib,sys,tempfile,json,hashlib,subprocess,os,io,contextlib,time
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path.cwd()/'tools'))
import s3_sample_preparation as s
import test_s3_sample_preparation as fixtures
O=pathlib.Path(__file__).resolve().parent
results=[]
for stream in ('stdout','stderr'):
 with tempfile.TemporaryDirectory(prefix='ic02-'+stream+'-') as td:
  root=pathlib.Path(td);package=fixtures.correction_package(root,video=True);package.write_documents();args=fixtures._cli_args(package)
  doc={'format':{'format_name':'mp4','duration':4},'streams':[{'codec_type':'video','width':8,'height':8}]}
  payload=json.dumps(doc).encode(); exe=root/'probe'
  exe.write_text('#!'+sys.executable+'\nimport os\nos.write(1,'+repr(payload)+')\nos.write('+('1' if stream=='stdout' else '2')+',b" "*(4*1024*1024+4096))\n');exe.chmod(0o700)
  adapter=s.MediaAdapter(exe,exe)
  preflight={'decision':'PREFLIGHT_PASSED','candidate':{'sha':args.candidate},'child':{'sha256':fixtures.sha256_path(package.root/s.CHILD_REL),'child_id':'SYNTHETIC'},'catalog':{'sha256':fixtures.sha256_path(package.root/s.CATALOG_REL)},'holdout_manifest':{'sha256':fixtures.sha256_path(package.root/s.HOLDOUT_REL)},'runtime':{'relative_path':s.relative_to_package(package.runtime_root(),package.root)},'tools':{k:{'real_path':str(exe)} for k in ('ffmpeg','ffprobe')}}
  fixtures.write_json(pathlib.Path(args.preflight),preflight)
  later=dict.fromkeys(['resolve','stat','hash','decode'],0);frames=[0];created=[];polls=[]
  orig_start=subprocess.Popen;orig_resolve=s.resolve_source_path;orig_stat=pathlib.Path.stat;orig_hash=s.sha256_file
  def start(*a,**kw):
   p=orig_start(*a,**kw);orig_poll=p.poll
   def poll():
    began=time.monotonic();actual=p.wait(timeout=2);observed=orig_poll();polls.append({'pid':p.pid,'wait_result':actual,'poll_result':observed,'seconds':time.monotonic()-began});return observed
   p.poll=poll;created.append(p);return p
  def resolve(root,rel):
   if rel=='b.mp4':later['resolve']+=1
   return orig_resolve(root,rel)
  def stat(path,*a,**kw):
   if path==package.source/'b.mp4':later['stat']+=1
   return orig_stat(path,*a,**kw)
  def hashing(path,*a,**kw):
   if pathlib.Path(path)==package.source/'b.mp4':later['hash']+=1
   return orig_hash(path,*a,**kw)
  def frame(path,*a,**kw):
   frames[0]+=1
   if pathlib.Path(path)==package.source/'b.mp4':later['decode']+=1
   raise AssertionError('frame reached after probe failure')
  stdout=io.StringIO();stderr=io.StringIO()
  with patch.object(s,'HANDOFF_GUARD',fixtures.stub_guard),patch.object(s,'git_blob',lambda root,sha,rel:(root/rel).read_bytes()),patch.object(s,'MediaAdapter',lambda *a:adapter),patch.object(subprocess,'Popen',start),patch.object(s,'resolve_source_path',resolve),patch.object(pathlib.Path,'stat',stat),patch.object(s,'sha256_file',hashing),patch.object(adapter,'extract_frame',frame),contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
   cli=s.command_run(args,package_root=package.root)
  r=json.loads(pathlib.Path(args.receipt).read_text());entry=adapter.run_log[0]
  reaped=[]
  for p in created:
   try:os.waitpid(p.pid,os.WNOHANG);reaped.append(False)
   except ChildProcessError:reaped.append(True)
  retained=entry['stdout_text'].encode();err=entry['stderr_text'].encode()
  assert json.loads(retained)==doc
  assert hashlib.sha256(retained).hexdigest()==entry['stdout_sha256']
  assert hashlib.sha256(err).hexdigest()==entry['stderr_sha256']
  assert entry['exit_code']==0 and entry['error'].endswith('VIDEO_PROCESS_OUTPUT_LIMIT')
  assert cli==1 and r['decision']=='PREPARATION_FAILED_PROBE_CAPTURE_LIMIT_EXCEEDED'
  assert frames[0]==0 and later==dict.fromkeys(later,0) and r['candidates'][1]['status']=='not_run'
  assert len(created)==1 and all(reaped) and created[0].returncode==0
  assert r['cleanup']['staging_removed'] and r['cleanup']['cleanup_process']['reaped']
  assert entry['stdout_bytes']+entry['stderr_bytes']==4*1024*1024
  try:adapter.budget.check();raise AssertionError('sticky failure cleared')
  except s.BudgetStop:pass
  result={'stream':stream,'cli_exit':cli,'cli_args':vars(args),'probe_entry':{k:v for k,v in entry.items() if k not in ('stdout_text','stderr_text')},'retained_json_valid':True,'capture_hashes_independently_recomputed':True,'frames':frames[0],'later':later,'real_processes':[{'pid':p.pid,'returncode':p.returncode,'reaped':v} for p,v in zip(created,reaped)],'poll_waits':polls,'receipt':r,'owned_temp':str(root),'owned_entries_before':len(list(root.rglob('*'))),'owned_bytes_before':sum(p.stat().st_size for p in root.rglob('*') if p.is_file())}
  (O/(stream+'.cli.stdout.log')).write_text(stdout.getvalue());(O/(stream+'.cli.stderr.log')).write_text(stderr.getvalue());(O/(stream+'.cli.exit.log')).write_text(str(cli)+'\n')
 result['owned_temp_absent_after']=not root.exists();assert result['owned_temp_absent_after'];results.append(result)
(O/'probe-overflow-owner.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
