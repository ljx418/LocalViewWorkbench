from pathlib import Path
import json
O=Path(__file__).resolve().parent
rows=json.loads((O/'negative-results.json').read_text());assessment=[]
for r in rows:
 n=r['name'];ok=False;basis=''
 if n.startswith('finish_'):
  ok='CPU_RECONCILIATION_UNSETTLED' in r['actual'] and r['starts_before']==r['starts_after'] and r['uncertain_after_attempt'] and not r['final']['cleanup_proven'] and r['final']['root_retained'];basis='拒绝在新增charge前；未知账本、原槽和根保留'
 elif n=='live_exit':ok='CPU_CONCURRENCY_LIMIT' in r['third_live'] and r['after_one_exit']=='ADMITTED' and 'CPU_CONCURRENCY_LIMIT' in r['one_more'];basis='两live及仅释放一个'
 elif n=='unknown_original':ok=r['first_occupied'] and 'CPU_CONCURRENCY_LIMIT' in r['one_more'];basis='未知原退出仍占槽'
 elif n=='sequential13':ok=r['starts']==13 and r['peak']<=2 and r['final']['cleanup_proven'] and r['first_finished_wall_unchanged'] and r['reserved']==60;basis='13次合成原句柄顺序累计，一次finalizer不退款'
 elif n.startswith('idempotency_'):ok='CPU_RECONCILIATION_UNSETTLED' in r['admit'] and r['new_starts']==0 and not r['final']['cleanup_proven'] and r['final']['root_retained'];basis='原四种冲突，无pending遮蔽'
 elif n.startswith('local_marker_'):ok=not r['final']['cleanup_proven'] and r['final']['root_retained'];basis='磁盘分歧不被补写成cleanup'
 elif n.startswith('deadline_'):ok=r['deadline_unchanged'] and ((r['actual']=='ADMITTED' and r['starts']==2) if r['offset']<0 else ('SESSION_ADMISSION_WINDOW_CLOSED' in r['actual'] and r['starts']==1));basis='poll/finish/read有限I/O跨原截止复核'
 elif n=='uncertain_after_reconciliation':ok='SESSION_UNCERTAIN_CUSTODY' in r['actual'] and r['starts']==1;basis='协调后不确定状态复核'
 elif n.startswith('identity_'):ok='CPU_RECONCILIATION_UNSETTLED' in r['actual'] and r['starts']==1 and not r['final']['cleanup_proven'];basis='budget及admission/pidbirth/状态身份原件冲突'
 elif n.startswith('exact_terminal_'):ok=r['final']['cleanup_proven'] and r['finished_wall_unchanged'] and r['starts']==1 and r['reserved']==60;basis='已持久合法终态不调用坏finish、不重写不退款'
 elif n.startswith('final_read_'):
  expect=n.startswith('final_read_False_') and n.endswith('_real')
  ok=r['final']['cleanup_proven']==expect and r['final']['root_retained']!=expect and ((r['final']['exit_code']==0)==expect)
  basis='无本地已结算标记的未结算charge可由真实finish首次成功持久；已结算或finish失败且读失败须保根'
 assessment.append({'name':n,'pass':bool(ok),'basis':basis})
assert len(assessment)==58 and all(x['pass'] for x in assessment)
(O/'assessment.json').write_text(json.dumps({'cases':assessment,'count':58,'failed':0,'scope':'independent synthetic triggers only; not StagePASS'},ensure_ascii=False,indent=2))
print('58 observations independently evaluated; no failed obligation in scoped model')
