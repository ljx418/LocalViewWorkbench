#!/usr/bin/env python3
"""Fail-closed release evidence checker. Does not establish evidence truthfulness."""
from pathlib import Path
import argparse, json, hashlib, math, sys
ROOT=Path(__file__).resolve().parents[1]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('report',type=Path);ap.add_argument('--target',choices=['V0','V1','V2','V3'],required=True);ap.add_argument('--evidence-root',type=Path);args=ap.parse_args()
 errors=[]
 try:report=json.loads(args.report.read_text(encoding='utf-8'))
 except Exception as exc:print('NOT_ACCEPTED:',str(exc));return 2
 required=json.loads((ROOT/'plans/release_gates.json').read_text())['gates'][args.target]['required_cases']
 root=(args.evidence_root or args.report.parent).resolve();seen={}
 for c in report.get('cases',[]):
  cid=c.get('case_id')
  if cid in seen:errors.append('duplicate case '+str(cid))
  seen[cid]=c
 for field in ['run_id','application_commit','target_environment']:
  if not report.get(field):errors.append('missing '+field)
 for cid in required:
  c=seen.get(cid,{})
  if c.get('status')!='PASS':errors.append(cid+': not PASS')
  if c.get('observed') is None:errors.append(cid+': no actual observations')
  evidence=c.get('evidence') or []
  if not evidence:errors.append(cid+': no evidence')
  for e in evidence:
   try:
    p=(root/e['path']).resolve()
    if not p.is_relative_to(root) or not p.is_file():raise ValueError('outside root or missing')
    if hashlib.sha256(p.read_bytes()).hexdigest()!=e['sha256']:raise ValueError('hash mismatch')
   except Exception as exc:errors.append(cid+': evidence '+str(exc))
 m=report.get('metrics',{})
 def number(key):
  value=m.get(key)
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):errors.append('invalid metric '+key);return None
  return value
 for key,limit,op in [('gpu_peak_gib',23,'lt'),('system_available_ram_gib_min',2,'ge'),('release_after_stop_seconds',30,'le'),('critical_hallucinations',0,'le')]:
  x=number(key)
  if x is not None and not (x<limit if op=='lt' else x>=limit if op=='ge' else x<=limit):errors.append(key+' outside gate')
 for key,limit in [('image_warm_seconds',180),('video4_warm_seconds',300)]:
  values=m.get(key)
  if not isinstance(values,list) or len(values)<10 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in values):errors.append(key+' needs >=10 valid measured samples');continue
  p95=sorted(values)[math.ceil(.95*len(values))-1]
  if p95>limit:errors.append(key+' P95 outside gate')
 for key in ['image_cold_seconds','video4_cold_seconds']:
  x=number(key)
  if x is not None and (x<0 or x>420):errors.append(key+' outside 420s timeout')
 for key,minimum in [('image_samples',10 if args.target=='V0' else 12),('image_usable',8 if args.target=='V0' else 10),('video_samples',6),('video_usable',5)]:
  x=number(key)
  if x is not None and (x<minimum or int(x)!=x):errors.append(key+' below required count')
 for part,ratio in [('image',.8 if args.target=='V0' else 10/12),('video',5/6)]:
  used=m.get(part+'_usable');total=m.get(part+'_samples')
  if isinstance(used,(int,float)) and isinstance(total,(int,float)) and total>0:
   if used>total or used/total<ratio:errors.append(part+' usable proportion outside gate')
 if m.get('outbound_attempts')!=0:errors.append('outbound_attempts must be measured as zero')
 if m.get('oom_count')!=0:errors.append('oom_count must be measured as zero')
 if errors:
  print(json.dumps({'decision':args.target+'_NOT_ACCEPTED','errors':errors},ensure_ascii=False,indent=2));return 1
 print(json.dumps({'decision':'EVIDENCE_STRUCTURE_VALID','candidate_release':args.target+'_ACCEPTED','warning':'This checks evidence presence, hashes and numeric gates only. Human review must verify evidence authenticity, quality annotation and semantic assertions.'},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':sys.exit(main())
