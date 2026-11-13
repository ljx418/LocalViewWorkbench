import os,json,hashlib
from pathlib import Path
from tools import v0_s3_coordinator as c
O=Path(__file__).resolve().parent
binding={'run_id':'synthetic-owner','candidate_sha':'a'*40}
receipts={name:{'kind':c.AGGREGATE_RECEIPT_KIND,'status':'PASS',**binding,'stage_pass_claim':False,'product_gate0':False,'independent':True,'real_isolation':True} for requirements in c.TWELVE_REQUIREMENTS.values() for name in requirements}
assert 'cleanup' not in receipts
summary=c.aggregate_twelve_keys(receipts=receipts,binding=binding)
assert summary['pass_count']==12
# A matching root identity cannot allow raw from an ancestor symlink escaping that root.
root=O/'owner-bound-root';root.mkdir();outside=O/'owner-outside-bound-root';outside.mkdir();(outside/'canonical.json').write_text('{"rows":[]}');(outside/'source.json').write_text('{"plan":[]}');(outside/'raw.bin').write_bytes(b'EXTERNAL_SYNTHETIC_RAW')
(root/'redirect').symlink_to(outside,target_is_directory=True)
e=c.ParentOriginalEvidence(**binding,child_sha256='b'*64,root=root,projection_sha256='c'*64)
e.seal_plan([{'ordinal':i,'asset_id':'I%02d'%i,'media_kind':'image','source_sha256':'d'*64,'source_bytes':1} for i in range(1,17)])
st=root.stat();e.seal_root([st.st_dev,st.st_ino]);verified=e.verify_selected_root();sealed=e.seal_originals(canonical='redirect/canonical.json',source_plan='redirect/source.json',raw=['redirect/raw.bin'])
assert sealed['raw'][0]['sha256']==hashlib.sha256(b'EXTERNAL_SYNTHETIC_RAW').hexdigest()
manifest=e.manifest();(outside/'raw.bin').write_bytes(b'CHANGED_AFTER_SEAL');reverified=e.verify_selected_root();after=e.manifest()
result={'all12_without_cleanup':summary,'symlink_escape':{'root_verified':verified,'canonical_resolved':str((root/'redirect/canonical.json').resolve()),'bound_root':str(root),'manifest':manifest},'changed_raw':{'selected_root_reverified':reverified,'manifest_unchanged':after==manifest,'new_actual_sha256':hashlib.sha256((outside/'raw.bin').read_bytes()).hexdigest()}}
(O/'owner-observations.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
