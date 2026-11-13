import hashlib,json,pathlib,subprocess,time
P=pathlib.Path('LVW_Prompt_Service_MasterPack_v2.0.0');O=P/'reports/v0-s3/product-gate0/independent-fixture-result-05';C='07277a6f2f6f730dc7b9383bfeaf8c412126fe16'
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.check_output(['git',*a])
def write(n,d):(O/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
f='tools/open_lvw_browser.cmd';b=(P/f).read_bytes();candidate=git('show',C+':'+str(P/f));write('cmd-exception.json',{'file':f,'work_sha256':sha(b),'candidate_sha256':sha(candidate),'normalized_equal':b.replace(b'\r\n',b'\n')==candidate.replace(b'\r\n',b'\n'),'executed':False})
initial=json.loads((O/'initial-state.json').read_text());status=git('status','--porcelain=v2').decode();idx=pathlib.Path(git('rev-parse','--git-path','index').decode().strip());cp=pathlib.Path(json.loads((O/'live-counter-before.json').read_text())['path']);counter=cp.read_bytes(); filter_status=lambda s:'\n'.join(x for x in s.splitlines() if str(O) not in x)
unchanged_inputs=[]
for f in ['input-integrity.json','authority-and-prior-input-hashes.json']:
 for row in json.loads((O/f).read_text()):
  p=pathlib.Path(row.get('file',row.get('path')));unchanged_inputs.append({'path':str(p),'unchanged':sha(p.read_bytes())==row['sha256']})
write('input-final-integrity.json',unchanged_inputs)
state={'head':git('rev-parse','HEAD').decode().strip(),'status':status,'index_sha256':sha(idx.read_bytes()),'time':time.time(),'head_unchanged':git('rev-parse','HEAD').decode().strip()==initial['head'],'index_byte_exact':idx.read_bytes()==(O/'initial-index.bin').read_bytes(),'old_status_exact_excluding_new_report_dir':filter_status(status)==filter_status(initial['status']),'live_counter_sha256':sha(counter),'live_counter_unchanged':sha(counter)==json.loads((O/'live-counter-before.json').read_text())['sha256'],'inputs_unchanged':all(x['unchanged'] for x in unchanged_inputs),'cmd_exception_preserved':sha(b)=='f6886a9c75774eae5092489ddd4fc7b44cee3dea9ac17e3c2f70625d476deb04'}
write('final-state.json',state)
assert all(state[k] for k in ['head_unchanged','index_byte_exact','old_status_exact_excluding_new_report_dir','live_counter_unchanged','inputs_unchanged','cmd_exception_preserved'])
raw=json.loads((O/'recomputation-final.json').read_text());oracle=json.loads((O/'oracle-comparison.json').read_text());assert raw['all_pass'] and oracle['caps_unchanged'] and oracle['all_assertions_unchanged']
write('decision.json',{'candidate_sha':C,'evidence_commit':'c6bce90eeac384d534ebb7601193693840b5b70d','status':'LIMITED_EXACT13_FIXTURE_COMPONENT_VERIFIED','Fatal':0,'Major':0,'Minor':0,'inherited_accepted_nonblocking_Minor':1,'collected':13,'unique':13,'pass':13,'fail':0,'skip':0,'notrun':0,'new_fixture_runs_by_this_review':0,'new_candidate_imports':0,'fixed_denominator':24,'full24_proven':False,'product_denominator':12,'stage_pass_claim':False,'product_gate0':False,'grant_terminal':'EXPIRED_NO_REPLAY','counter_terminal_sha256':sha(counter),'remaining':'remaining-workpack.md','new_report_committed':False})
print(json.dumps({'integrity':True,'checks':len(raw['checks']),'input_files':len(json.loads((O/'input-integrity.json').read_text())),'F':0,'M':0,'m':0,'inherited_m':1,'candidate_imported':False,'fixture_runs':0}))
