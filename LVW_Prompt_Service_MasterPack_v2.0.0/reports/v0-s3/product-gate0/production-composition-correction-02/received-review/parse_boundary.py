from probes import *
def test_canonical_parsed_before_sealed_bytes(build,monkeypatch):
 comp=build();original=c.load_published_execution_receipt;observed={}
 def read_then_change(root):
  parsed=original(root);p=Path(root)/'qd-receipt.json';doc=json.loads(p.read_bytes());doc['test_counts']['PASS']=15;doc['test_counts']['FAIL']=1;doc['rows'][-1]['execution_status']='FAIL';doc['rows'][-1]['error_code']='INDEPENDENT_AFTER_PARSE';p.write_text(json.dumps(doc));observed.update(parsed_counts=parsed['test_counts'],actual_counts=doc['test_counts'],actual_sha256=sha(p.read_bytes()));return parsed
 monkeypatch.setattr(c,'load_published_execution_receipt',read_then_change)
 v,seam,obj=run(comp,monkeypatch);save('M05-parse-seal-drift',{**v,'oracle':observed,'controller_cached_counts':obj.canonical['test_counts'] if obj.canonical else None})
 assert observed and v['receipt']['state']=='SUMMARY_PERSISTED'
 assert v['receipt']['receipts']['quality_16_rows']['status']=='PASS'
 assert v['receipt']['summary']['provenance']['canonical']['sha256']==observed['actual_sha256']
