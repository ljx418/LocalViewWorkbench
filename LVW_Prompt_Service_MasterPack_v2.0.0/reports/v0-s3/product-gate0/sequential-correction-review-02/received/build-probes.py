from pathlib import Path
out=Path('reports/v0-s3/product-gate0/independent-sequential-correction-02')
s=(out/'negative_probes.py').read_text()
s=s.replace("for kind in ['gate','oserror','false','read_gate','read_oserror']:","for kind in ['gate','oserror','false','read_gate','read_oserror','read_only_gate','read_only_oserror']:")
s=s.replace("if kind.startswith('read_'):","if kind.startswith('read_'):").replace("if kind=='read_gate':raise", "if kind in ('read_gate','read_only_gate'):raise")
s=s.replace("ex.counter.charge_state=failread", "ex.counter.charge_state=failread\n   if kind.startswith('read_only_'):ex.counter.finish=original_finish")
s=s.replace("uncertain=ex.uncertain; ledger=ex.charge_ledger()", "assert after['starts_total']==before['starts_total'] and 'CPU_RECONCILIATION_UNSETTLED' in result\n  assert all(x['state']=='STARTED' and not x['settled'] for x in after['charges'])\n  uncertain=ex.uncertain; ledger=ex.charge_ledger()")
# Persist snapshots after every observation, even if later diagnostics fail.
s=s.replace("RESULTS.append({'name':name,**data});print", "RESULTS.append({'name':name,**data});(OUT/'negative-results.json').write_text(json.dumps(RESULTS,indent=2));print")
# Original terminal conflict triggers: prove cleanup refusal without any pending admission.
s=s.replace("before=c.read_bytes();a=attempt(ex);after=json.loads(c.read_text());f=final(p,ex)","before=c.read_bytes();a=attempt(ex)\n if a=='ADMITTED':\n  nxt=Handle(740002,0);ex.register(nxt)\n after=json.loads(c.read_text());f=final(p,ex)\n assert not f['cleanup_proven'] and f['root_retained'] and f['exit_code']!=0\n assert after['starts_total']==1")
s=s.replace("f=final(p,ex)\nsave('local_marker_disk_divergence'", "f=final(p,ex)\nassert not f['cleanup_proven'] and f['root_retained']\nassert json.loads(c.read_text())['charges'][0]['state']=='STARTED'\nsave('local_marker_disk_divergence'")
s=s[:s.index("(OUT/'negative-results.json').write_text(json.dumps(RESULTS,indent=2))\nprint('DIAGNOSTICS_CAPTURED'")]
(out/'negative_probes.py').write_text(s)
