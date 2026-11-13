from pathlib import Path
import json,hashlib,collections,stat
P=Path('LVW_Prompt_Service_MasterPack_v2.0.0');D=P/'reports/v0-s3/product-gate0/independent-production-composition-01';R=Path('/mnt/c/workspace/videoworkline/localviewworkbench')/P
save=lambda n,o:(D/n).write_text(json.dumps(o,indent=2,ensure_ascii=False))
findings=[]
for line in (D/'review.md').read_text().splitlines():
 if line.startswith('| M0') or line.startswith('| m0'):
  cells=[x.strip() for x in line.strip('|').split('|')];ident,severity=cells[0].split();findings.append({'id':ident,'severity':severity,'location':cells[1],'trigger_expected_actual_evidence':cells[2]})
assert collections.Counter(x['severity'] for x in findings)=={'Major':9,'Minor':2}
save('findings.json',{'candidate':'7c27a11111ede5bb2eb449211f5450270d884ee3','baseline':'c6bce90eeac384d534ebb7601193693840b5b70d','outcome':'CHANGES_REQUIRED','counts':{'Fatal':0,'Major':9,'Minor':2},'findings':findings,'stage_pass_claim':False,'product_gate0':False})
cmap={'C01':['I03','I04','I23'],'C02':['I07'],'C03':['I10','I11','I21'],'C04':['I13','I14'],'C05':['I16'],'C06':['I19','I20'],'C07':['I24'],'C08':['I22'],'C09':['I01','I02','I05','I06'],'C10':['I17','I18'],'C11':['I15'],'C12':['I%02d'%i for i in range(1,25)]}
delta={
'I01':('unchanged owner/profile source only','No new real default profile/ledger; M02'),
'I02':('unchanged warm owner source only','No real warm/native lifecycle'),
'I03':('candidate/auth context rejection and formal main binding','M01/M02/M03 trusted admission/seal break'),
'I04':('authority owner source unchanged; controller verifier inspected using budget spy only','No original ledger read/debit; M01/M02'),
'I05':('old default hook source unchanged','No real S2 default production regression run'),
'I06':('existing install factory source unchanged','No install/rollback execution'),
'I07':('exact candidate main/worker/16 rows/66 messages/pipe/canonical verified','Synthetic thread only; M03/M07; not native dependency closure'),
'I08':('blocking callback synthetic driver, real parent deadline and UNKNOWN retained','daemon worker persists at return; m01; no native descendants'),
'I09':('fsync write failure UNKNOWN with partial summary; bounded real parent readers used','M04/M08; no real backend/ledger blocking I/O, no fresh OS partial fixture'),
'I10':('history order and duplicate start exact rejection with first deadline fixed','Real long history/native callback combinations unproved'),
'I11':('frozen10800/600/21600 and controlled parent clock expiry','No wall-duration platform run; m01'),
'I12':('real66 frames and duplicate-history/bad-reference/worker-missing-terminal negatives','Not all protocol variants freshly rerun; exact072 prior13 preserved only'),
'I13':('worker refusal/missing terminal accurate UNKNOWN; unexpected read error reproduced','M08 missing receipt/finally cleanup; native parent loss unproved'),
'I14':('write failure and incomplete worker retain reservations with no retry','M07 cleanup fact retention mismatch; m01'),
'I15':('RecoveryEntry through controller; no custody from synthetic PID, no resend','No native parent crash/recovery'),
'I16':('real manifest82 entries independently checked, root-before-manifest rejection','M05 post-manifest unsafe consumption; M06 outside write'),
'I17':('real phase residue observation retains unknown and no arbitrary deletion','M07 cleanup/reservation adapter mismatch'),
'I18':('same accepted residue accessor source; no new arbitrary path operation','No Windows reparse or fresh512/256 exhaustive boundary tests'),
'I19':('formal main actual adapter and twelve-key aggregate; absent obligations nonPASS','M07 false internal PASS; outerBLOCKED not exoneration'),
'I20':('real QS recompute owner valid/mismatch raw tests; absent QS/A06 nonPASS','No real quality judgments/independent scorer/A06'),
'I21':('five worker/context/history/fixed-command compatibility nodes and true phase progress','No full old541/257 suite; binary stream m02'),
'I22':('independent audit guard before candidate import,8 selftest denials, candidate denials0','Only offline isolation; not A06/native cleanup'),
'I23':('preflight wrong candidate/hash/auth/root/projection refuses0spawn; counter outerread only','M01–M04; original expired grant not reopened'),
'I24':('same candidate/root/sourceplan/raw/manifest/summary positive chain verified','M03/M05; native originalhandle countersettlement remains072-only evidence')}
prior=(R/'reports/v0-s3/product-gate0/production-composition-01/received-review/i01-i24-coverage-delta.md').read_text();owners={}
for line in prior.splitlines():
 if line.startswith('| I'):
  cells=[s.strip() for s in line.strip('|').split('|')];owners[cells[0]]=cells[1]
coverage=[]
for i in range(1,25):
 key='I%02d'%i;scope,gap=delta[key];coverage.append({'id':key,'owner_path':owners[key],'C_mapping':[c for c,ids in cmap.items() if key in ids],'independent_observation':scope,'remaining_gap':gap,'complete_obligation':'NOT_PROVEN','new_candidate_fixed13_pass_claimed':False,'product_pass':False})
save('coverage.json',{'candidate':'7c27a11111ede5bb2eb449211f5450270d884ee3','fixed_I_denominator':24,'product_denominator':12,'C_is_mapping_not_new_denominator':True,'C_map':cmap,'I_coverage':coverage,'stage_pass_claim':False,'product_gate0':False})
a=json.loads((D/'concentrated-results.json').read_text());b=json.loads((D/'corrected-results.json').read_text());s=json.loads((D/'score-results.json').read_text());allnodes=a['collected']+b['nodes']+s['nodes'];latest={}
for group in [a,b,s]:
 for row in group['results']:latest[row['nodeid']]=row['outcome']
assert len(allnodes)==45 and len(set(allnodes))==40 and set(latest.values())=={'passed'}
save('execution-accounting.json',{'initial':{'collection':37,'passed_assertions':33,'failed_independent_oracles':4,'exit':1},'narrow_oracle_correction_and_one_added_variant':{'collection':6,'passed_assertions':6,'exit':0},'narrow_remaining_QS_concern':{'collection':2,'passed_assertions':2,'exit':0},'total_pytest_node_invocations':45,'unique_pytest_nodes':40,'latest_oracle_outcomes':dict(collections.Counter(latest.values())),'passing_reproduction_is_not_acceptance':True,'author_final':{'nodes':123,'pass':122,'skip':1},'author_interim01':{'nodes':118,'pass':118,'skip':0},'author_interim02':{'nodes':123,'pass':122,'skip':1},'author_total_node_invocations':364,'author_composition_nodes_separate':3,'new_candidate_fixed13_pass':False})
# Append the outer static audit commands and their genuinely observed statuses, including failed oracle.
commands=json.loads((D/'commands.json').read_text());commands.extend([{'label':'audit-final-initial','argv':['python3',str(D/'audit_final.py')],'exit':1,'stderr':'audit-final.initial.stderr.log','source_snapshot':'audit_final.initial.txt','reason':'independent audit assumed nonexistent sourceplan run_root field; no candidate executed'},{'label':'audit-final-corrected','argv':['python3',str(D/'audit_final.py')],'exit':0,'stderr':'audit-final.stderr.log','stdout':'audit-final.stdout.log','reason':'check canonical.run_root and each sourceplan absolute path instead; no candidate executed'}]);save('commands.json',commands)
# Existing clean CMD exception is recorded, never executed.
cmd=P/'tools/open_lvw_browser.cmd';save('cmd-exception.json',{'path':str(cmd),'work_sha256':hashlib.sha256(cmd.read_bytes()).hexdigest(),'previously_approved_CRLF_exception':True,'normalized_equal_to_candidate':True,'executed':False})
print(json.dumps({'findings':len(findings),'I_coverage':len(coverage),'node_invocations':len(allnodes),'unique_nodes':len(set(allnodes))}))
