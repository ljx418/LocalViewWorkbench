"""Complete ordered S2 phase composition; requires real bound runtime factories.

No CLI, child creation or Stage PASS. Factories must enforce the fresh full
source/dependency/authorization gate, own partial-startup cleanup and return the
actual Runtime contexts below. Archive must retain immutable raw evidence and
remove only the proven owned run root. It is not a substitute for that binding
executor, independent review or human signature.
"""
from dataclasses import dataclass
from pathlib import Path
import re

from tools.v0_s2_cumulative_phase import CumulativePhase, CASES as CUMULATIVE
from tools.v0_s2_public_phase import PublicPhase, FIXED_CASES as PUBLIC
from tools.v0_s2_browser_phase import run_browser_phase
from tools.v0_s2_browser_handlers import default_offline_runner
from tools.v0_s2_warm_phase import WarmPhase, FIXED_CASES as WARM
from tools.v0_s2_checkpoint_oracles import EvidenceError


@dataclass
class DefaultContext:
    driver: object
    root: Path
    binding: dict
    image: dict
    baseline_gpu_mib: int
    fixture_plan: dict
    references: dict
    primary_category: str
    browser_config: dict
    node_executable: str
    node_sha256: str
    authorize_launch: object
    verify_bindings: object
    nvidia_exe: str
    nvidia_sha256: str


@dataclass
class WarmContext:
    driver: object
    root: Path
    binding: dict
    worker: object
    samples: dict


class StageSequence:
    def __init__(self, *, run_id, candidate_sha, authorization_sha256, prepare_default, prepare_warm, archive, authorize):
        if (not re.fullmatch('[a-f0-9]{40}', candidate_sha) or not re.fullmatch('[a-f0-9]{64}', authorization_sha256)
                or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}', run_id)
                or any(not callable(f) for f in (prepare_default, prepare_warm, archive, authorize))):
            raise ValueError('complete sealed parent callbacks/identity required')
        self.run_id = run_id; self.candidate = candidate_sha; self.auth = authorization_sha256
        self.prepare_default = prepare_default; self.prepare_warm = prepare_warm
        self.archive = archive; self.authorize = authorize; self.used = False
        self.closed = []

    def identity(self, value):
        if value.get('candidate_sha') != self.candidate or value.get('authorization_sha256') != self.auth:
            raise EvidenceError('Stage phase candidate/child mismatch')
        if value.get('run_id', self.run_id) != self.run_id: raise EvidenceError('Stage phase cross-run')

    def phase(self, value, decision, cases=None):
        self.identity(value)
        if value.get('run_id') != self.run_id or value.get('decision') != decision or value.get('stage_pass_claim') is not False:
            raise EvidenceError('Stage phase incomplete: '+str(value.get('decision')))
        if cases is not None and (set(value.get('cases', {})) != set(cases)
                or any(r.get('status') != 'PASS' for r in value['cases'].values())):
            raise EvidenceError('Stage phase fixed denominator missing')

    def context(self, context, warm):
        self.identity(context.binding)
        if context.driver.submissions != 0 or getattr(context.driver, 'warm_benchmark', False) is not warm:
            raise EvidenceError('Stage runtime prelude/mode contaminated')
        if context.root.resolve(strict=True) != context.root: raise EvidenceError('Stage context root redirect')
        root = context.driver.owned_listener_birth(11434)
        if (root['pid'], root['start_ticks']) != (context.binding['ollama_pid'], context.binding['ollama_start_ticks']):
            raise EvidenceError('Stage bound model root changed')

    def close(self, context, result, name, *, preserve=False):
        if any(known is context for known, _ in self.closed):
            return next(passed for known, passed in self.closed if known is context)
        passed = False
        try:
            cleanup = context.driver.cleanup(); result[name+'_cleanup'] = cleanup
            if cleanup.get('proven') is not True: raise EvidenceError('Stage native cleanup unproven')
            if preserve:
                result[name+'_root_preserved'] = True
                raise EvidenceError('Stage browser/callback uncertainty requires retained root')
            archived = self.archive(context, cleanup); result[name+'_archive'] = archived
            self.identity(archived)
            if (archived.get('proven') is not True or not re.fullmatch('[a-f0-9]{64}', archived.get('manifest_sha256', ''))
                    or context.root.exists()): raise EvidenceError('Stage immutable archive/root removal unproven')
            # Absence of processes proves cleanup, not that the resource trace
            # succeeded. A last-sample failure can occur after the final phase
            # observation; its terminal receipt must still block the sequence.
            workers = cleanup.get('sampler_workers', [])
            if (len(workers) != (2 if name == 'default' else 1)
                    or any(worker.get('wrapper_exit_code') != 0
                        or worker.get('receipt', {}).get('decision') != 'RESOURCE_TRACE_COLLECTED_NOT_STAGE_ACCEPTANCE'
                        or worker.get('receipt', {}).get('owned_gpu_query_exited') is not True for worker in workers)
                    or getattr(context.driver, 'resource_abort_latched', False)):
                raise EvidenceError('Stage sampler terminal failure/abort cannot pass as cleanup')
            passed = True
            return True
        except Exception as error:
            result[name+'_cleanup_error'] = type(error).__name__+':'+str(error)
            return False
        finally: self.closed.append((context, passed))

    def run(self):
        if self.used: raise EvidenceError('Stage sequence is one-shot')
        self.used = True
        result = {'kind': 'S2_ORDERED_SEQUENCE_NOT_STAGE_ACCEPTANCE', 'run_id': self.run_id,
            'candidate_sha': self.candidate, 'authorization_sha256': self.auth, 'decision': 'NO_GO', 'stage_pass_claim': False,
            'cases': {c: 'NOT_RUN' for c in ('V0-A01', 'V0-A02', 'V0-A03', 'V0-A04', 'V0-A05', 'V0-A07', 'V0-A08', 'V0-A09', 'V0-A10')},
            'phases': {}, 'native_preflight_and_archive_executor_required': True}
        default = warm = None; interrupted = None; preserve_default = False
        try:
            self.authorize('prepare_default_runtime', self.run_id)
            default = self.prepare_default(); self.context(default, False)
            cumulative = CumulativePhase(default.driver, default.root, run_id=self.run_id, binding=default.binding,
                image=default.image, baseline_gpu_mib=default.baseline_gpu_mib, authorize=self.authorize)
            online = cumulative.run('online'); result['phases']['cumulative_online'] = online
            self.phase(online, 'ONLINE_CUMULATIVE_VERIFIED_OFFLINE_PENDING')
            public = PublicPhase(default.driver, default.root, run_id=self.run_id, candidate_sha=self.candidate,
                authorization_sha256=self.auth, fixture_plan=default.fixture_plan, references=default.references,
                authorize=self.authorize).run(); result['phases']['public'] = public
            self.phase(public, 'PUBLIC_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', PUBLIC)
            primary = default.fixture_plan['categories'][default.primary_category]
            offline = default_offline_runner(default.driver, default.root, run_id=self.run_id, binding=default.binding,
                fixture=primary, reference=default.references[default.primary_category], baseline_gpu_mib=default.baseline_gpu_mib,
                nvidia_exe=default.nvidia_exe, nvidia_sha256=default.nvidia_sha256, authorize=self.authorize)
            preserve_default = True  # Revoke only after independent browser/callback closure.
            browser = run_browser_phase(default.driver, config=default.browser_config, binding=default.binding, fixture=primary,
                node_executable=default.node_executable, node_sha256=default.node_sha256,
                authorize_launch=default.authorize_launch, authorize_action=self.authorize,
                verify_bindings=default.verify_bindings, run_offline=offline)
            result['phases']['browser'] = browser
            preserve_default = browser.get('browser_cleanup_proven') is not True or browser.get('callbacks_pending') != 0
            self.phase(browser, 'BROWSER_COMPONENT_VERIFIED_NOT_STAGE_ACCEPTANCE')
            if browser.get('browser_cleanup_proven') is not True or browser.get('callbacks_pending') != 0:
                raise EvidenceError('Stage browser/callback cleanup unproven')
            cpu = cumulative.run('offline'); result['phases']['cumulative'] = cpu
            self.phase(cpu, 'CUMULATIVE_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', CUMULATIVE)
            # 24 cumulative +15 public +2 UI +2 cancel +2 fault/quarantine.
            if default.driver.submissions != 45: raise EvidenceError('Stage default submission denominator')
            old_root = default.root; old_binding = dict(default.binding)
            if not self.close(default, result, 'default'): raise EvidenceError('Stage default closure failed')
            default = None
            self.authorize('prepare_fresh_warm_runtime', self.run_id)
            warm = self.prepare_warm(); self.context(warm, True)
            if (warm.root == old_root or warm.binding['model_digest'] != old_binding['model_digest']
                    or (warm.binding['ollama_pid'], warm.binding['ollama_start_ticks'])
                    == (old_binding['ollama_pid'], old_binding['ollama_start_ticks'])):
                raise EvidenceError('Stage warm runtime is not fresh/same model')
            hot = WarmPhase(warm.driver, warm.worker, warm.root, run_id=self.run_id, binding=warm.binding,
                samples=warm.samples, authorize=self.authorize).run(); result['phases']['warm'] = hot
            self.phase(hot, 'WARM_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', [c for c, _ in WARM])
            if warm.driver.submissions != 20: raise EvidenceError('Stage warm submission denominator')
            if not self.close(warm, result, 'warm'): raise EvidenceError('Stage warm closure failed')
            warm = None
            result['cases'] = dict.fromkeys(result['cases'], 'PASS')
            result['decision'] = 'MACHINE_SEQUENCE_COMPLETE_REQUIRES_INDEPENDENT_REVIEW_AND_HUMAN_SIGNOFF'
        except BaseException as error:
            result['error_code'] = type(error).__name__+':'+str(error)
            if isinstance(error, (KeyboardInterrupt, SystemExit)): interrupted = error
        finally:
            if warm is not None: self.close(warm, result, 'warm')
            if default is not None: self.close(default, result, 'default', preserve=preserve_default)
            statuses = list(result['cases'].values())
            result['test_counts'] = {'fixed': 9, 'PASS': statuses.count('PASS'), 'NOT_RUN': statuses.count('NOT_RUN')}
        if interrupted is not None: raise interrupted
        return result
