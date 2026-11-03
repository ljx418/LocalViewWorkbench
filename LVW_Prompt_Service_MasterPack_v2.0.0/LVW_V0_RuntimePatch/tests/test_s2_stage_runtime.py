"""Real staging, native binding writers and archival; synthetic services/GPU."""
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import v0_s2_stage_runtime as runtime
from tools.v0_s2_runtime import NativeRuntime
from tools.v0_s2_stage_archive import OwnedArchive
from tools.v0_s2_checkpoint_oracles import EvidenceError


class FactoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(); self.events = []; self.failure = None
        paths = {}; tools = self.root/'installed'; tools.mkdir()
        for name in runtime.TOOL_KEYS:
            path = tools/name; path.write_bytes(b'explicit synthetic tool'); paths[name] = path
        source = self.root/'samples'; source.mkdir(); samples = {}
        for kind, suffix in (('image', '.jpg'), ('video', '.mp4')):
            path = source/(kind+suffix); raw = (kind+' bytes, no decoder in this test').encode(); path.write_bytes(raw)
            samples[kind] = {'path': str(path), 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        prefix = 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/'
        names = [path.relative_to(runtime.ROOT).as_posix() for path in (runtime.ROOT/prefix).rglob('*')
            if path.is_file() and '__pycache__' not in path.parts]
        names += ['tools/v0_s2_browser_acceptance.cjs', 'tools/v0_s2_browser_policy.cjs',
            'LVW_V0_RuntimePatch/workflows/video_reverse_prompt_v0.ui.json']
        identity = {'candidate_sha': 'a'*40, 'execution_artifact_sha256': {
            name: hashlib.sha256((runtime.ROOT/name).read_bytes()).hexdigest() for name in names}}
        self.directory = self.root/'child'; self.directory.mkdir()
        self.archive = OwnedArchive(self.directory, run_id='factory-test', candidate_sha='a'*40,
            authorization_sha256='b'*64, authorize=lambda *args: None)
        self.kwargs = dict(directory=self.directory, run_id='factory-test', candidate_sha='a'*40,
            authorization_sha256='b'*64, paths=paths, tool_sha256={key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in paths.items()},
            source_identity=identity, samples=samples, fixture_plan=json.loads((runtime.ROOT/'reports/v0-s2/frozen-structural-inputs-02.json').read_text()),
            model_digest='c'*64, archive=self.archive, authorize=lambda *args: self.events.append(args[0]),
            verify_complete=self.complete, guard_critical=lambda: {'complete_rehash': False,
                'manifest_sha256': 'd'*64, 'critical_files': [key.upper() for key in runtime.TOOL_KEYS]})
        patcher = patch.object(runtime, 'NativeRuntime', side_effect=self.native); patcher.start(); self.addCleanup(patcher.stop)

    def complete(self):
        self.events.append('complete-rehash')
        return {'complete_rehash': True, 'candidate_sha': 'a'*40, 'manifest_sha256': 'd'*64,
            'tool_bindings': {key: {'path': str(path), 'sha256': self.kwargs['tool_sha256'][key]}
                for key, path in self.kwargs['paths'].items()}}

    def native(self, args, evidence):
        driver = NativeRuntime(args, evidence); driver.root = None
        driver._windows_path = lambda value, **kwargs: 'C:/'+str(Path(value).name)
        driver.preflight = lambda: {'max_used_mib': 100, 'target_listener_count': 0}
        driver.native_clock = lambda: {'wall_seconds': 1000, 'monotonic_seconds': 10}
        driver.owned_listener_birth = lambda port: {'pid': port, 'start_ticks': 100}
        def start_ollama(log):
            self.events.append('ollama-start'); driver.root = log.parent
            driver.ollama_log = log; log.write_text('synthetic no-cloud fixture log')
            driver.owned.append(('ollama_wrapper', object(), object())); driver.listener_proofs[11434] = {}
        driver.start_ollama = start_ollama
        driver.no_cloud_remote_gate = lambda: {'ollama_no_cloud': True, 'scope': 'synthetic service only'}
        driver.verify_model = lambda: {'digest': ('e' if self.failure in ('model', 'cleanup') else 'c')*64}
        def start_comfy(root, log):
            self.events.append('comfy-start'); (root/'user').mkdir(); log.write_text('synthetic Comfy log')
            driver.owned.append(('comfy', object(), object())); driver.listener_proofs[8191] = {}
        driver.start_comfy = start_comfy
        driver.registry = lambda: {name: {'synthetic_registry': True} for name in runtime.REQUIRED_NODES}
        def powershell(script):
            if script.startswith('New-Item -ItemType Junction'):
                root = next(path for path in self.directory.glob('lvw-s2-default-*'))
                (root/'input/redirect').symlink_to(root/'outside-input', target_is_directory=True); return ''
            if script.startswith('$item=Get-Item'):
                return json.dumps({'path': 'C:/redirect', 'attributes': 0x400, 'link_type': 'Junction', 'targets': ['C:/outside-input']})
            if script.startswith('[System.IO.Directory]::Delete'):
                root = next(self.directory.glob('lvw-s2-default-*'))
                (root/'input/redirect').unlink()
                return json.dumps({'link_absent': True, 'target_exists': (root/'outside-input').is_dir()})
            if 'FreePhysicalMemory' in script: return str(4096*1024)
            if 'CommandLine' in script:
                parts = [driver._windows_path(args.comfy_python), '-s', '-B', driver._windows_path(args.comfy_main),
                    '--listen', '127.0.0.1', '--port', '8191', '--base-directory', driver._windows_path(str(driver.root)),
                    '--user-directory', 'C:/WRONG' if self.failure == 'user-root' else 'C:/user',
                    '--disable-auto-launch', '--disable-api-nodes', '--disable-all-custom-nodes', '--whitelist-custom-nodes', 'lvw_v0_bridge']
                return ' '.join(parts)
            raise AssertionError(script)
        driver._powershell = powershell
        def sampler(*args, **kwargs):
            self.events.append('sampler-start'); driver.resource_observer = lambda: None
            return SimpleNamespace(scope='synthetic worker, not a native trace')
        driver.start_sampler = sampler
        def cleanup():
            self.events.append('cleanup')
            return {'proven': self.failure != 'cleanup', 'owned_count': len(driver.owned), 'final_target_listener_count': 0,
                'owned_listener_terminal_states': [dict(port=port, terminal_absent=True, unknown_descendants_absent=True) for port in driver.listener_proofs],
                'owned_wrapper_terminal_states': [dict(exited=True, native_wrapper_absent=True) for _ in driver.owned]}
        driver.cleanup = cleanup
        return driver

    def test_default_and_fresh_warm_use_actual_bindings_and_exact_owned_staging(self):
        factory = runtime.StageRuntimeFactory(**self.kwargs)
        default = factory.prepare_default()
        self.assertEqual(19, default.binding['max_runs']); self.assertEqual(0, default.driver.submissions)
        self.assertEqual(45, default.driver.max_public_submissions)
        self.assertEqual('tracking', default.primary_category)
        self.assertEqual(256*1024**2+1, (default.root/'input/oversize.mp4').stat().st_size)
        self.assertEqual(default.root/'outside-input', (default.root/'input/redirect').resolve())
        self.assertTrue(default.verify_bindings(default.browser_config, 'preflight')['ephemeral_user_root_verified'])
        self.assertEqual('a'*40, default.authorize_launch(default.browser_config)['candidate_sha'])
        with self.assertRaises(EvidenceError): factory.prepare_warm()  # Root is still live, even with mocked services.
        self.assertTrue(self.archive(default, default.driver.cleanup())['proven'])
        warm = factory.prepare_warm()
        self.assertTrue(warm.driver.warm_benchmark); self.assertEqual(20, warm.binding['max_requests'])
        self.assertEqual(20, warm.driver.max_public_submissions); self.assertNotEqual(default.root, warm.root)
        self.assertTrue(self.archive(warm, warm.driver.cleanup())['proven'])
        with self.assertRaises(EvidenceError): factory.prepare_default()

    def test_changed_model_archives_partial_start_once_and_never_starts_comfy(self):
        self.failure = 'model'; factory = runtime.StageRuntimeFactory(**self.kwargs)
        with self.assertRaises(EvidenceError): factory.prepare_default()
        self.assertNotIn('comfy-start', self.events); self.assertEqual(1, self.events.count('ollama-start'))
        self.assertEqual(1, self.events.count('cleanup'))
        receipt = json.loads((self.directory/'default-preparation-failure.json').read_text())
        self.assertFalse(receipt['root_retained']); self.assertTrue(receipt['archive']['proven'])
        with self.assertRaises(EvidenceError): factory.prepare_warm()

    def test_sample_mismatch_before_any_start_still_archives_and_cleans_own_root(self):
        Path(self.kwargs['samples']['image']['path']).write_bytes(b'changed source')
        factory = runtime.StageRuntimeFactory(**self.kwargs)
        with self.assertRaises(EvidenceError): factory.prepare_default()
        self.assertNotIn('ollama-start', self.events); self.assertNotIn('comfy-start', self.events)
        receipt = json.loads((self.directory/'default-preparation-failure.json').read_text())
        self.assertFalse(receipt['root_retained']); self.assertTrue(receipt['archive']['proven'])
        self.assertEqual(0, receipt['cleanup']['owned_count'])

    def test_wrong_actual_comfy_user_directory_is_rejected_before_sampler(self):
        self.failure = 'user-root'; factory = runtime.StageRuntimeFactory(**self.kwargs)
        with self.assertRaises(EvidenceError): factory.prepare_default()
        self.assertNotIn('sampler-start', self.events); self.assertEqual(1, self.events.count('cleanup'))
        receipt = json.loads((self.directory/'default-preparation-failure.json').read_text())
        self.assertFalse(receipt['root_retained']); self.assertFalse(receipt['stage_pass_claim'])

    def test_unproven_partial_cleanup_preserves_root_and_stops_retries(self):
        self.failure = 'cleanup'; factory = runtime.StageRuntimeFactory(**self.kwargs)
        with self.assertRaises(EvidenceError): factory.prepare_default()
        receipt = json.loads((self.directory/'default-preparation-failure.json').read_text())
        self.assertTrue(receipt['root_retained']); self.assertFalse(receipt['cleanup']['proven'])
        self.assertNotIn('archive', receipt); self.assertEqual(1, self.events.count('cleanup'))
        with self.assertRaises(EvidenceError): factory.prepare_default()

    def test_denial_or_incomplete_full_binding_stops_before_staging_or_service(self):
        for failure in ('denial', 'incomplete'):
            with self.subTest(failure=failure):
                kwargs = dict(self.kwargs)
                if failure == 'denial': kwargs['authorize'] = lambda *args: (_ for _ in ()).throw(EvidenceError('denied'))
                else: kwargs['verify_complete'] = lambda: {'complete_rehash': False}
                with self.assertRaises(EvidenceError): runtime.StageRuntimeFactory(**kwargs).prepare_default()
                self.assertEqual([], list(self.directory.glob('lvw-s2-*'))); self.assertNotIn('ollama-start', self.events)

    def test_literal_windows_cli_grammar_does_not_approximate_ambiguous_quotes(self):
        self.assertEqual(['C:/Program Files/Python/python.exe', '-s', 'C:/a.py'],
            runtime.strict_argv('"C:/Program Files/Python/python.exe" -s C:/a.py'))
        for value in ('"unterminated', '"C:/a"extra', 'C:/a\\"bad', 'C:/a\nnext'):
            with self.subTest(value=value), self.assertRaises(EvidenceError): runtime.strict_argv(value)


if __name__ == '__main__': unittest.main()
