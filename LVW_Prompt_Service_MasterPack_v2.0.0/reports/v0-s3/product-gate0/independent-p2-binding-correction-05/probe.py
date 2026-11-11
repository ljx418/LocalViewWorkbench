"""Independent public run replay: actual replace ENOENT at three owned I/O boundaries."""
import sys, os, json, tempfile, shutil, hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent
sys.argv=[str(OUT/'runner.py'),'directed']
exec((OUT/'runner.py').read_text().split("files=['tools/test_v0_s3_runtime_binding.py']")[0])
import pytest
sys.path.insert(0,str(ROOT/'tools'))
import test_v0_s3_runtime_binding as tests
h=tests.harness
real_run=h.run
results=[]
for fault in ('shared','local','publish'):
    row={'fault':fault,'io_errors':[]};results.append(row)
    os.environ['P2B_RAW_DIR']=str(OUT/('probe-'+fault+'-raw'))
    Path(os.environ['P2B_RAW_DIR']).mkdir()
    def run():
        previous=h.os.replace
        def replace(src,dst):
            source,dest=Path(src),Path(dst)
            hit=(fault=='shared' and dest.name=='shared.claim' and json.loads(source.read_bytes()).get('status')=='EXPIRED') or (fault=='local' and dest==h.BASE/'consumed.json') or (fault=='publish' and source==h.BASE/'terminal-candidate.json' and dest==h.BASE/'cross-os-lifecycle.json')
            if hit:
                try:previous(src,h.BASE/'nonexistent-owned-parent'/dest.name)
                except OSError as exc:
                    row['io_errors'].append({'source':str(src),'destination':str(dst),'actual_failed_destination':str(h.BASE/'nonexistent-owned-parent'/dest.name),'errno':exc.errno,'error':str(exc)})
                    raise
                raise AssertionError('expected real filesystem failure')
            return previous(src,dst)
        h.os.replace=replace
        try:
            life=real_run()
            row['returned']={k:life.get(k) for k in ('status','terminal_persisted','terminal_index_persisted','finalization_proven','claim_finalization','synthetic_debits','phases')}
            row['disk']={}
            for name,path in [('index',h.BASE/'cross-os-lifecycle.json'),('shared',h.BASE.parent/'shared.claim'),('local',h.BASE/'consumed.json'),('staging',h.BASE/'terminal-candidate.json')]:
                data=path.read_bytes() if path.exists() else None
                row['disk'][name]={'exists':data is not None,'sha256':hashlib.sha256(data).hexdigest() if data else None,'value':json.loads(data) if data else None}
            shutil.copytree(h.BASE,OUT/('probe-'+fault+'-disk'))
            return life
        finally:h.os.replace=previous
    with tempfile.TemporaryDirectory(prefix='lvw-independent-c05-probe-'+fault+'-') as tmp:
        mp=pytest.MonkeyPatch();mp.setattr(h,'run',run)
        try:tests.test_correction04_public_run_maximum(Path(tmp),mp,None)
        except AssertionError:row['old_success_oracle']='REJECTED_AS_EXPECTED'
        finally:mp.undo()
    row['owned_tmp']=tmp;row['removed']=not Path(tmp).exists()
    store('independent-probes',results)
    disk=row['disk'];value=disk['index']['value']
    assert row['io_errors'] and all(e['errno']==2 for e in row['io_errors'])
    assert row['returned']['status']=='BLOCKED' and not row['returned']['finalization_proven']
    assert value['status']=='BLOCKED' and value['claim_finalization']=='UNPROVEN'
    assert row['returned']['phases']['normal']=='PERSISTED' and row['returned']['synthetic_debits']==1
    for name in ('shared','local'):
        c=disk[name]['value']
        assert c is None or c.get('result')!='READY_FOR_REVIEW'
        if c and c['status']=='EXPIRED':assert c['terminal_sha256']==disk['index']['sha256']
    if fault=='shared':assert disk['shared']['value']['status']=='RUNNING'
    if fault=='local':assert not disk['local']['exists']
    assert disk['staging']['value']['status']=='READY_FOR_REVIEW' # forensic staging is not canonical
    row['oracle']='PASS: canonical BLOCKED, consumption never decision, phase1 retained'
    store('independent-probes',results)
store('probe-boundary',dict(parser_invocations=len(parser),denied=denied,processes=records))
print(json.dumps({'independent_public_probes':len(results),'passed':3,'parser_invocations':len(parser)}))
