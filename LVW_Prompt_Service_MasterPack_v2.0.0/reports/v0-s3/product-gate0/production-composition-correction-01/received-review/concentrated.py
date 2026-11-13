import sys,json,os,threading,time
from pathlib import Path
import pytest
D=Path(__file__).parent
# Selected production behavior and failures, no whole integration/fixture/quality suites.
author=['test_the_command_line_entry_refuses_an_unknown_argument','test_the_command_line_entry_refuses_a_wrong_context_seal','test_the_native_path_is_refused_before_any_spawn','test_a_foreign_candidate_is_refused_before_any_spawn','test_a_foreign_authorization_is_refused_before_any_spawn','test_a_foreign_root_is_refused_before_any_spawn','test_a_tampered_worker_context_is_refused_before_any_spawn','test_a_projection_that_the_phase_refuses_is_refused_before_any_spawn','test_the_seam_can_not_be_serialised_into_the_context','test_a_repeated_history_announcement_is_refused_and_does_not_extend_a_deadline','test_a_worker_that_refuses_never_produces_a_summary','test_a_canonical_receipt_that_changed_is_refused','test_a_removed_canonical_receipt_is_refused','test_a_terminal_reference_out_of_the_root_is_refused','test_a_replaced_root_is_refused_by_the_manifest','test_the_recovery_entry_of_an_unknown_outcome_never_replays']
compat=['test_the_worker_really_invokes_the_quality_phase','test_the_history_wait_is_announced_before_the_row_finishes','test_a_context_with_a_wrong_seal_is_refused','test_a_context_with_an_unknown_key_is_refused','test_the_production_command_is_the_fixed_worker']
nodes=['tools/test_v0_s3_production_composition.py::'+n for n in author]+['tools/test_v0_s3_supervisor.py::'+n for n in compat]+[str(D/'probe_test.py')]
(D/'selection.json').write_text(json.dumps({'nodes':nodes,'author_nodes':len(author),'compatibility_nodes':len(compat),'independent_file':str(D/'probe_test.py'),'rationale':'Only necessary new composition negative paths, five worker/context compatibility nodes, independent whole-main chain and adversarial receipt/read/write/thread probes; no OS fixtures or full old suite.'},indent=2))
class Results:
 def __init__(self):self.collected=[];self.results=[]
 def pytest_collection_finish(self,session):self.collected=[i.nodeid for i in session.items]
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.results.append({'nodeid':report.nodeid,'when':report.when,'outcome':report.outcome,'duration':report.duration,'longrepr':str(report.longrepr) if report.failed else None})
p=Results();threads_before=[(t.name,t.ident,t.daemon) for t in threading.enumerate()];fds_before=os.listdir('/proc/self/fd');start=time.time()
code=pytest.main(['-q','-s','--tb=short','-p','no:cacheprovider','--basetemp',str(D/'pytest-temp'),*nodes],plugins=[p])
(D/'concentrated-results.json').write_text(json.dumps({'exit':int(code),'duration':time.time()-start,'collected':p.collected,'results':p.results,'threads_before':threads_before,'threads_after':[(t.name,t.ident,t.daemon) for t in threading.enumerate()],'fds_before':fds_before,'fds_after':os.listdir('/proc/self/fd'),'assertion_success_is_not_product_acceptance':True},indent=2))
raise SystemExit(code)
