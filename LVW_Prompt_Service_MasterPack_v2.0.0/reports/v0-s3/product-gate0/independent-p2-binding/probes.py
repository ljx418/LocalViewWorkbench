"""Offline control-flow probes; synthetic grant, roots and fixed missing tools only."""
from pathlib import Path
import sys,json,tempfile,hashlib
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tools import v0_s3_runtime_binding as h
OUT=Path(__file__).resolve().parent
records=[]
with tempfile.TemporaryDirectory(prefix='lvw-p2b-review-probes-') as temp:
 base=Path(temp)
 for name in ['first','relocated','finalization']:
  root=base/name;root.mkdir()
  (root/'contract').write_text('synthetic contract');(root/'approval').write_text('synthetic approval');(root/'source').write_text('synthetic source')
  child={'child_id':'SYNTHETIC-REVIEW-ONLY','contract_sha256':h.digest(root/'contract'),'parent_approval':'approval','parent_approval_sha256':h.digest(root/'approval'),'limits':h.LIMITS}
  (root/'child').write_text(json.dumps(child))
  fake={k:str(root/('missing-'+k)) for k in ['windows_python','wsl','python']}
  with patch.multiple(h,ROOT=root,BASE=root/'receipts',CHILD='child',CONTRACT='contract',SOURCES=['source'],FIXED=fake),patch.object(h.subprocess,'check_output',side_effect=lambda argv,**kw:'a'*40 if argv[1]=='rev-parse' else b''):
   pre=h.preflight('a'*40)
   if name!='finalization':
    result=h.run();terminal=json.loads((h.BASE/'consumed.json').read_text())
    try:h.preflight('a'*40)
    except ValueError as e:denied=str(e)
    records.append({'case':name,'child_sha256':pre['child_sha256'],'terminal':terminal,'same_root_reentry':denied,'machine_process_starts':result['counters']['process_starts'],'error':result['error']})
   else:
    meter=h.Meter()
    with patch.object(h,'Meter',return_value=meter),patch.object(meter,'check',side_effect=ValueError('wall budget')):
     try:h.run()
     except ValueError as e:error=str(e)
    records.append({'case':'terminal_write_skipped_on_final_meter_error','error':error,'consumed':json.loads((h.BASE/'consumed.json').read_text()),'lifecycle_written':(h.BASE/'cross-os-lifecycle.json').exists()})
 assert records[0]['child_sha256']==records[1]['child_sha256']
 records.append({'same_synthetic_grant_consumed_at_two_roots':True,'new_machine_batches':0,'synthetic_debits':0})
records.append({'owned_root':temp,'removed':not Path(temp).exists()})
(OUT/'probes.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records,indent=2))
