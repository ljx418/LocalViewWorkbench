#!/usr/bin/env python3
"""Fail-closed release evidence checker. Does not establish evidence truthfulness."""
from pathlib import Path
import argparse, json, hashlib, math, re, sys
ROOT=Path(__file__).resolve().parents[1]

def checked_artifact(root, item, label, errors):
 try:
  p=(root/item['path']).resolve()
  if not p.is_relative_to(root) or not p.is_file():raise ValueError('outside root or missing')
  if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('hash mismatch')
  return p
 except Exception as exc:
  errors.append(label+': evidence '+str(exc));return None

def main():
 ap=argparse.ArgumentParser();ap.add_argument('report',type=Path);ap.add_argument('--target',choices=['V0-Min','V0.1','V0.2','V0','V1','V2','V3'],required=True);ap.add_argument('--evidence-root',type=Path);args=ap.parse_args()
 errors=[]
 try:report=json.loads(args.report.read_text(encoding='utf-8'))
 except Exception as exc:print('NOT_ACCEPTED:',str(exc));return 2
 required=json.loads((ROOT/'plans/release_gates.json').read_text())['gates'][args.target]['required_cases']
 root=(args.evidence_root or args.report.parent).resolve();seen={}
 for c in report.get('cases',[]):
  cid=c.get('case_id')
  if cid in seen:errors.append('duplicate case '+str(cid))
  seen[cid]=c
 for field in ['run_id','application_commit','implementation_owner','target_environment']:
  if not report.get(field):errors.append('missing '+field)
 commit=report.get('application_commit')
 if not isinstance(commit,str) or not re.fullmatch(r'[0-9a-f]{40}',commit):errors.append('application_commit must be a full lowercase Git SHA')
 expected_acceptance_hash=hashlib.sha256(('\n'.join(sorted(required))+'\n').encode()).hexdigest()
 if report.get('acceptance_hash')!=expected_acceptance_hash:errors.append('acceptance_hash does not bind the fixed release denominator')
 for cid in required:
  c=seen.get(cid,{})
  if c.get('status')!='PASS':errors.append(cid+': not PASS')
  if c.get('candidate_sha')!=commit:errors.append(cid+': candidate mismatch')
  if c.get('run_id')!=report.get('run_id'):errors.append(cid+': run mismatch')
  if c.get('observed') is None:errors.append(cid+': no actual observations')
  evidence=c.get('evidence') or []
  if not evidence:errors.append(cid+': no evidence')
  for e in evidence:
   checked_artifact(root,e,cid,errors)
 independent=report.get('independent_review') or {}
 if independent.get('decision')!='PASS':errors.append('independent review is not PASS')
 if not independent.get('reviewer') or independent.get('reviewer')==report.get('implementation_owner'):errors.append('independent reviewer missing or not separated')
 if independent.get('candidate_sha')!=commit:errors.append('independent review candidate mismatch')
 checked_artifact(root,independent,'independent review',errors)
 signoff=report.get('human_signoff') or {}
 if signoff.get('decision')!='APPROVED':errors.append('human signoff is not APPROVED')
 for field in ('signer','signed_at'):
  if not signoff.get(field):errors.append('human signoff missing '+field)
 if signoff.get('scope')!=args.target+'_RELEASE':errors.append('human signoff scope mismatch')
 if signoff.get('candidate_sha')!=commit:errors.append('human signoff candidate mismatch')
 m=report.get('metrics',{})
 def number(key):
  value=m.get(key)
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):errors.append('invalid metric '+key);return None
  return value
 for key,limit,op in [('gpu_peak_gib',23,'lt'),('system_available_ram_gib_min',2,'ge'),('release_after_stop_seconds',30,'le'),('critical_hallucinations',0,'le')]:
  x=number(key)
  if x is not None and not (x<limit if op=='lt' else x>=limit if op=='ge' else x<=limit):errors.append(key+' outside gate')
 performance_series=[('image_warm_seconds',180,1 if args.target=='V0-Min' else 10)]
 if args.target!='V0-Min':performance_series.append(('video4_warm_seconds',300,1 if args.target=='V0.1' else 10))
 for key,limit,minimum_count in performance_series:
  values=m.get(key)
  if not isinstance(values,list) or len(values)<minimum_count or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in values):errors.append(key+' needs >='+str(minimum_count)+' valid measured samples');continue
  p95=sorted(values)[math.ceil(.95*len(values))-1]
  if p95>limit:errors.append(key+' P95 outside gate')
 cold_keys=['image_cold_seconds']+([] if args.target=='V0-Min' else ['video4_cold_seconds'])
 for key in cold_keys:
  x=number(key)
  if x is not None and (x<0 or x>420):errors.append(key+' outside 420s timeout')
 if args.target=='V0-Min': sample_minima=[('image_samples',1),('image_usable',1)]
 elif args.target=='V0.1': sample_minima=[('image_samples',1),('image_usable',1),('video_samples',1),('video_usable',1)]
 elif args.target in {'V0','V0.2'}: sample_minima=[('image_samples',10),('image_usable',8),('video_samples',6),('video_usable',5)]
 else: sample_minima=[('image_samples',12),('image_usable',10),('video_samples',6),('video_usable',5)]
 for key,minimum in sample_minima:
  x=number(key)
  if x is not None and (x<minimum or int(x)!=x):errors.append(key+' below required count')
 ratios=[('image',1.0 if args.target in {'V0-Min','V0.1'} else (.8 if args.target in {'V0','V0.2'} else 10/12))]
 if args.target!='V0-Min':ratios.append(('video',1.0 if args.target=='V0.1' else 5/6))
 for part,ratio in ratios:
  used=m.get(part+'_usable');total=m.get(part+'_samples')
  if isinstance(used,(int,float)) and isinstance(total,(int,float)) and total>0:
   if used>total or used/total<ratio:errors.append(part+' usable proportion outside gate')
 if m.get('outbound_attempts')!=0:errors.append('outbound_attempts must be measured as zero')
 if m.get('oom_count')!=0:errors.append('oom_count must be measured as zero')
 if errors:
  print(json.dumps({'decision':args.target+'_NOT_ACCEPTED','errors':errors},ensure_ascii=False,indent=2));return 1
 print(json.dumps({'decision':'EVIDENCE_STRUCTURE_VALID','candidate_release':args.target+'_ACCEPTED','warning':'This verifies signoff structure and binding, not signer identity or semantic authenticity; those remain human and independent-review responsibilities.'},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':sys.exit(main())
