"""Sequence safety tests with synthetic phase results; no native acceptance."""
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import v0_s2_stage_sequence as sequence
from tools.v0_s2_checkpoint_oracles import EvidenceError


class SequenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(); self.events = []; self.contexts = []
        self.cleanup_proven = True; self.browser_failure = None; self.warm_override = None
        self.sampler_failure = False
        self.online_failure = False; self.missing_handoff = False
        self.public_mutation = lambda value: value
        for name, replacement in (('CumulativePhase', self.cumulative), ('PublicPhase', self.public),
                ('WarmPhase', self.warm), ('run_browser_phase', self.browser),
                ('default_offline_runner', lambda *args, **kwargs: lambda: None)):
            current = patch.object(sequence, name, replacement); current.start(); self.addCleanup(current.stop)

    def result(self, decision, cases=None):
        value = dict(run_id='sequence-test', candidate_sha='a'*40, authorization_sha256='b'*64,
            decision=decision, stage_pass_claim=False)
        if cases is not None: value['cases'] = {case: {'status': 'PASS'} for case in cases}
        return value

    def context(self, warm):
        name = 'warm' if warm else 'default'; self.events.append('prepare-'+name)
        root = self.root/name; root.mkdir()
        birth = {'pid': 30 if warm else 20, 'start_ticks': 100}
        driver = SimpleNamespace(submissions=0, warm_benchmark=warm, workers=[object()],
            owned_listener_birth=lambda port: dict(birth))
        def cleanup():
            self.events.append('cleanup-'+name)
            return {'proven': self.cleanup_proven, 'sampler_workers': [dict(wrapper_exit_code=0,
                receipt=dict(decision='NO_GO' if self.sampler_failure else 'RESOURCE_TRACE_COLLECTED_NOT_STAGE_ACCEPTANCE',
                    owned_gpu_query_exited=True)) for _ in driver.workers]}
        driver.cleanup = cleanup
        binding = self.result('binding'); binding.update(ollama_pid=birth['pid'], ollama_start_ticks=100, model_digest='c'*64)
        common = dict(driver=driver, root=root, binding=binding)
        if warm:
            context = sequence.WarmContext(**common, worker=object(), samples={})
            if self.warm_override: self.warm_override(context)
        else:
            context = sequence.DefaultContext(**common, image={}, baseline_gpu_mib=100,
                fixture_plan={'categories': {'static': {}}}, references={'static': {}}, primary_category='static',
                browser_config={}, node_executable='unused', node_sha256='d'*64,
                authorize_launch=lambda *args: None, verify_bindings=lambda *args: None,
                nvidia_exe='unused', nvidia_sha256='e'*64)
        self.contexts.append(context)
        return context

    def archive(self, context, cleanup):
        self.events.append('archive-'+context.root.name)
        shutil.rmtree(context.root)  # Synthetic fixture roots only.
        return {**self.result('archive'), 'proven': True, 'manifest_sha256': 'f'*64}

    def parent(self, authorize=None):
        return sequence.StageSequence(run_id='sequence-test', candidate_sha='a'*40, authorization_sha256='b'*64,
            prepare_default=lambda: self.context(False), prepare_warm=lambda: self.context(True),
            archive=self.archive, authorize=authorize or (lambda *args: None))

    def cumulative(self, driver, *args, **kwargs):
        def run(segment):
            self.events.append('cumulative-'+segment); driver.submissions += 4 if segment == 'online' else 20
            if segment == 'online' and self.online_failure: return self.result('NO_GO')
            return self.result('ONLINE_CUMULATIVE_VERIFIED_OFFLINE_PENDING' if segment == 'online'
                else 'CUMULATIVE_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', None if segment == 'online' else sequence.CUMULATIVE)
        return SimpleNamespace(run=run)

    def public(self, driver, *args, **kwargs):
        def run():
            self.events.append('public'); driver.submissions += 15
            return self.public_mutation(self.result('PUBLIC_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', sequence.PUBLIC))
        return SimpleNamespace(run=run)

    def browser(self, driver, **kwargs):
        self.events.append('browser')
        if self.browser_failure == 'interrupt': raise KeyboardInterrupt()
        if not self.missing_handoff: driver.workers.append(object())
        driver.submissions += 6
        return {**self.result('BROWSER_COMPONENT_VERIFIED_NOT_STAGE_ACCEPTANCE'),
            'browser_cleanup_proven': self.browser_failure != 'cleanup', 'callbacks_pending': 0}

    def warm(self, driver, *args, **kwargs):
        def run():
            self.events.append('warm'); driver.submissions += 20
            return self.result('WARM_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE', [case for case, _ in sequence.WARM])
        return SimpleNamespace(run=run)

    def test_complete_order_uses_fresh_runtime_and_never_claims_stage_acceptance(self):
        parent = self.parent(); result = parent.run()
        self.assertEqual('MACHINE_SEQUENCE_COMPLETE_REQUIRES_INDEPENDENT_REVIEW_AND_HUMAN_SIGNOFF', result['decision'], result)
        self.assertEqual(['prepare-default', 'cumulative-online', 'public', 'browser', 'cumulative-offline',
            'cleanup-default', 'archive-default', 'prepare-warm', 'warm', 'cleanup-warm', 'archive-warm'], self.events)
        self.assertEqual([45, 20], [context.driver.submissions for context in self.contexts])
        self.assertEqual({'fixed': 9, 'PASS': 9, 'NOT_RUN': 0}, result['test_counts'])
        self.assertFalse(result['stage_pass_claim'])
        with self.assertRaises(EvidenceError): parent.run()

    def test_cross_candidate_run_missing_case_or_skipped_case_stops_before_browser(self):
        for mutation in (lambda value: value.update(candidate_sha='c'*40),
                lambda value: value.update(run_id='other-run'), lambda value: value.pop('run_id'),
                lambda value: value['cases'].pop(next(iter(value['cases']))),
                lambda value: next(iter(value['cases'].values())).update(status='SKIPPED')):
            with self.subTest(mutation=mutation):
                self.events.clear(); self.contexts.clear()
                def change(value): mutation(value); return value
                self.public_mutation = change
                result = self.parent().run()
                self.assertEqual('NO_GO', result['decision']); self.assertNotIn('browser', self.events)
                self.assertNotIn('prepare-warm', self.events); self.assertEqual(0, result['test_counts']['PASS'])
                self.assertEqual(1, self.events.count('cleanup-default'))

    def test_failed_default_cleanup_never_archives_retries_cleanup_or_starts_warm(self):
        self.cleanup_proven = False
        result = self.parent().run()
        self.assertEqual('NO_GO', result['decision'])
        self.assertEqual(1, self.events.count('cleanup-default'))
        self.assertNotIn('archive-default', self.events); self.assertNotIn('prepare-warm', self.events)
        self.assertTrue(self.contexts[0].root.exists())

    def test_unknown_browser_or_interrupt_preserves_root_after_native_cleanup(self):
        for failure in ('cleanup', 'interrupt'):
            with self.subTest(failure=failure):
                self.events.clear(); self.contexts.clear(); self.browser_failure = failure
                if failure == 'interrupt':
                    with self.assertRaises(KeyboardInterrupt): self.parent().run()
                else: self.assertEqual('NO_GO', self.parent().run()['decision'])
                self.assertEqual(1, self.events.count('cleanup-default'))
                self.assertNotIn('archive-default', self.events); self.assertNotIn('prepare-warm', self.events)
                shutil.rmtree(self.contexts[0].root)  # Test teardown, not production closure.

    def test_warm_model_mismatch_stops_before_performance_but_cleans_own_roots(self):
        self.warm_override = lambda context: context.binding.update(model_digest='e'*64)
        result = self.parent().run()
        self.assertEqual('NO_GO', result['decision']); self.assertNotIn('warm', self.events)
        self.assertEqual(1, self.events.count('cleanup-default')); self.assertEqual(1, self.events.count('cleanup-warm'))
        self.assertEqual(0, result['test_counts']['PASS'])

    def test_authorization_denial_prevents_factory_or_cleanup_actions(self):
        def deny(*args): raise EvidenceError('authorization denied')
        result = self.parent(deny).run()
        self.assertEqual('NO_GO', result['decision']); self.assertEqual([], self.events)

    def test_terminal_sampler_failure_is_archived_but_cannot_start_warm_or_claim_pass(self):
        self.sampler_failure = True
        result = self.parent().run()
        self.assertEqual('NO_GO', result['decision']); self.assertEqual(0, result['test_counts']['PASS'])
        self.assertIn('archive-default', self.events); self.assertNotIn('prepare-warm', self.events)
        self.assertEqual(1, self.events.count('cleanup-default'))

    def test_early_online_failure_closes_one_registered_sampler_without_false_cleanup_failure(self):
        self.online_failure = True
        result = self.parent().run()
        self.assertEqual('NO_GO', result['decision']); self.assertEqual(0, result['test_counts']['PASS'])
        self.assertNotIn('default_cleanup_error', result)
        self.assertEqual(1, len(result['default_cleanup']['sampler_workers']))
        self.assertIn('archive-default', self.events); self.assertNotIn('prepare-warm', self.events)

    def test_missing_handoff_still_blocks_completed_default_phase(self):
        self.missing_handoff = True
        result = self.parent().run()
        self.assertEqual('NO_GO', result['decision']); self.assertIn('default_cleanup_error', result)
        self.assertNotIn('prepare-warm', self.events)

    def test_early_sampler_failure_and_abort_remain_blocking(self):
        for failure in ('receipt', 'abort', 'missing-receipt'):
            with self.subTest(failure=failure):
                context = self.context(False); result = {}
                if failure == 'receipt': self.sampler_failure = True
                elif failure == 'abort': context.driver.resource_abort_latched = True
                else: context.driver.cleanup = lambda: dict(proven=True, sampler_workers=[])
                self.assertFalse(self.parent().close(context, result, 'default'))
                self.assertIn('default_cleanup_error', result)
                self.sampler_failure = False


if __name__ == '__main__': unittest.main()
