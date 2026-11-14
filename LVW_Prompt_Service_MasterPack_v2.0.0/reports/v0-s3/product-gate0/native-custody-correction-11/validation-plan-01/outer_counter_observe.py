import os,sys,json,errno,stat
from pathlib import Path
EXPECTED='/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json'
def observe(path):
    if str(path)!=EXPECTED:
        raise ValueError('COUNTER_PATH_MISMATCH')
    results=[]
    for target in [str(Path(path).parent),str(path)]:
        row={'path':target}
        try:
            st=os.lstat(target)
            row.update(status='PRESENT_UNEXPECTED',mode=st.st_mode,symlink=stat.S_ISLNK(st.st_mode))
        except OSError as error:
            row.update(status='MISSING' if error.errno==errno.ENOENT else 'UNKNOWN_ERROR',errno=error.errno)
        results.append(row)
    accepted=all(row['status']=='MISSING' for row in results)
    return {'kind':'LVW_EXPIRED_FIXTURE_COUNTER_ABSENCE_OBSERVATION','observations':results,
            'accepted_absence':accepted,'counter_state':'MISSING' if accepted else 'UNEXPECTED_OR_UNKNOWN',
            'historical_counter_continuity':'UNAVAILABLE_NOT_PROVEN',
            'historical_expected_sha256':'acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98',
            'counter_content_read':False,'counter_created':False,'counter_written':False,
            'counter_reset':False,'counter_refunded':False,'historical_grant_revived':False}
if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('EXPECTED_COUNTER_PATH_AND_OUTPUT')
    result=observe(sys.argv[1])
    output=Path(sys.argv[2]);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))
    raise SystemExit(0 if result['accepted_absence'] else 2)
