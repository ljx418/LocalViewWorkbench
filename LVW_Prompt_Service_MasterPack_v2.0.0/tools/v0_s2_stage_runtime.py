"""Concrete native default/warm factories for a sealed full S2 parent.

No CLI or child authorization. Complete installed/source/offline/tool/sample
binding callbacks must come from the full executor. Failure retains the original
runtime cleanup and archive evidence; no fallback sample or second start occurs.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import secrets
import shutil
import tempfile
from types import SimpleNamespace

from tools.v0_s2_driver import ROOT, base
from tools.v0_s2_runtime import NativeRuntime
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import profile
from tools.v0_s2_execution_bindings import plain, stamp, hashed_file
from tools.v0_s2_public_phase import NEGATIVES, PATH_REFERENCES, encoded
from tools.v0_s2_stage_sequence import DefaultContext, WarmContext
from tools.v0_s2_checkpoint_oracles import EvidenceError

import time

REQUIRED_NODES = {'LVWControlledImageInput', 'LVWImagePromptBridge', 'LVWManualPromptOwner',
    'LVWDraftStateOwner', 'LVWVideoPromptOwner', 'LVWControlledVideoInput'}
BROWSER_BUDGET = {'browser_starts': 1, 'uploads': 1, 'public_submissions': 2, 'previews': 8,
    'adoptions': 2, 'cancellations': 1, 'held_responses': 1, 'downloads': 6, 'user_writes': 16}
TOOL_KEYS = {'comfy_main', 'comfy_python', 'ollama_exe', 'ffmpeg_exe', 'powershell',
    'node_executable', 'nvidia_exe', 'playwright_module', 'browser_executable'}


def strict_argv(command):
    """Accept only the simple literal argument grammar emitted by our wrapper.

    Embedded/escaped quotes and shell syntax are not generalized here: they are
    outside the frozen paths and produce a refusal rather than an approximation.
    """
    if not isinstance(command, str) or '\\"' in command or '\r' in command or '\n' in command:
        raise EvidenceError('native command line unsupported')
    result = []; offset = 0
    pattern = re.compile(r'\s*(?:"([^"\r\n]*)"|([^\s"\r\n]+))(?=\s|$)')
    while offset < len(command):
        if command[offset:].isspace(): break
        match = pattern.match(command, offset)
        if not match: raise EvidenceError('native command line malformed')
        result.append(match.group(1) if match.group(1) is not None else match.group(2)); offset = match.end()
    return result


class StageRuntimeFactory:
    def __init__(self, *, directory, run_id, candidate_sha, authorization_sha256, paths, tool_sha256,
                 source_identity, samples, fixture_plan, model_digest, archive, authorize,
                 verify_complete, guard_critical):
        if (set(paths) != TOOL_KEYS or set(tool_sha256) != TOOL_KEYS
                or any(not re.fullmatch('[a-f0-9]{64}', value) for value in tool_sha256.values())
                or not re.fullmatch('[a-f0-9]{40}', candidate_sha) or not re.fullmatch('[a-f0-9]{64}', authorization_sha256)
                or not re.fullmatch('[a-f0-9]{64}', model_digest)
                or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}', run_id)
                or set(samples) != {'image', 'video'} or source_identity.get('candidate_sha') != candidate_sha
                or any(not callable(f) for f in (archive, authorize, verify_complete, guard_critical))
                or any(not callable(getattr(archive, name, None)) for name in ('register', 'lease'))):
            raise ValueError('complete sealed native factory inputs required')
        self.directory = Path(directory); self.run_id = run_id; self.candidate = candidate_sha; self.auth = authorization_sha256
        self.paths = {key: Path(value) for key, value in paths.items()}; self.digests = dict(tool_sha256)
        self.source_identity = copy.deepcopy(source_identity); self.samples = copy.deepcopy(samples)
        self.plan = copy.deepcopy(fixture_plan); self.model = model_digest; self.archive = archive
        self.authorize = authorize; self.verify_complete = verify_complete; self.guard_critical = guard_critical
        self.used = set(); self.contexts = {}; self.evidence = {}; self.user_roots = {}
        self.manifest = None

    def _complete(self):
        proof = self.verify_complete()
        if (proof.get('complete_rehash') is not True or proof.get('candidate_sha') != self.candidate
                or not re.fullmatch('[a-f0-9]{64}', proof.get('manifest_sha256', ''))
                or proof.get('tool_bindings') != {key: {'path': str(path), 'sha256': self.digests[key]}
                    for key, path in self.paths.items()}):
            raise EvidenceError('factory complete execution binding not proven')
        self.manifest = proof['manifest_sha256']
        return proof

    def _copy(self, source, target, expected, *, limit):
        source = plain(source); before = stamp(source)
        if before[2] != expected['bytes'] or not 0 < before[2] <= limit:
            raise EvidenceError('factory sample size binding changed')
        with target.open('xb') as output:
            digest, count = hashed_file(source, before, time.monotonic()+30, write=output.write)
        if digest != expected['sha256'] or stamp(source) != before:
            raise EvidenceError('factory sample hash binding changed')
        return {'reference': target.name, 'sha256': digest, 'bytes': count}

    def _deploy(self, root):
        source = ROOT/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge'; target = root/'custom_nodes/lvw_v0_bridge'
        plain(source)
        for path in source.rglob('*'):
            if '__pycache__' not in path.parts: plain(path)
        shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        prefix = 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/'
        expected = {path[len(prefix):]: digest for path, digest in self.source_identity['execution_artifact_sha256'].items()
            if path.startswith(prefix)}
        actual = {}
        for path in target.rglob('*'):
            plain(path)
            if path.is_file(): actual[path.relative_to(target).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        if not expected or actual != expected: raise EvidenceError('factory deployed plugin is not exact frozen candidate')

    def _references(self, driver, root):
        references = dict(PATH_REFERENCES)
        for kind in ('categories', 'negatives'):
            for name, value in self.plan[kind].items():
                source = ROOT/value['path']; reference = 's2-'+source.name
                self._copy(source, root/'input'/reference, value, limit=8*1024**2); references[name] = reference
        (root/'input/empty.mp4').touch(exist_ok=False); references['empty'] = 'empty.mp4'
        with (root/'input/oversize.mp4').open('xb') as stream: stream.truncate(256*1024**2+1)
        references['oversize'] = 'oversize.mp4'
        outside = root/'outside-input'; outside.mkdir()
        self._copy(ROOT/self.plan['categories']['static']['path'], outside/'source.mp4', self.plan['categories']['static'], limit=8*1024**2)
        self.authorize('create_owned_reparse_fixture', 'default')
        link = root/'input/redirect'
        driver.evidence['reparse_fixture_creation_attempted'] = True
        driver._powershell('New-Item -ItemType Junction -Path '+base.ps_quote(driver._windows_path(str(link)))
            +' -Target '+base.ps_quote(driver._windows_path(str(outside)))+' -ErrorAction Stop | Out-Null')
        driver.verify_reparse_fixture(root)
        if set(references) != set(self.plan['categories']) | set(NEGATIVES): raise EvidenceError('factory public inputs incomplete')
        return references

    def _user_root(self, driver, root):
        lease = self.user_roots[root]
        self.archive.lease('warm' if driver.warm_benchmark else 'default')
        current = plain(root/'user').stat()
        if (current.st_dev, current.st_ino) != lease: raise EvidenceError('factory user root replaced')
        birth = driver.owned_listener_birth(8191)
        raw = driver._powershell(f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {birth['pid']}').CommandLine")
        actual = strict_argv(raw)
        expected = [driver._windows_path(str(self.paths['comfy_python'])), '-s', '-B',
            driver._windows_path(str(self.paths['comfy_main'])), '--listen', '127.0.0.1', '--port', '8191',
            '--base-directory', driver._windows_path(str(root)), '--user-directory', driver._windows_path(str(root/'user')),
            '--disable-auto-launch', '--disable-api-nodes', '--disable-all-custom-nodes', '--whitelist-custom-nodes', 'lvw_v0_bridge']
        for values in (actual, expected):
            for index in (0, 3, 9, 11):
                if len(values) <= index: raise EvidenceError('factory Comfy launch arguments missing')
                values[index] = base.normalized_windows_path(values[index]).casefold()
        if actual != expected: raise EvidenceError('factory Comfy CLI/user directory differs from frozen launch')
        return birth

    def prepare_default(self): return self._prepare(False)
    def prepare_warm(self): return self._prepare(True)

    def _prepare(self, warm):
        label = 'warm' if warm else 'default'
        if (label in self.used or (warm and ('default' not in self.contexts
                or self.contexts['default'].root.exists()))): raise EvidenceError('factory order/replay/default root not closed')
        self.used.add(label); self.authorize('prepare_bound_native_runtime', label)
        proof = self._complete(); plain(self.directory)
        root = Path(tempfile.mkdtemp(prefix='lvw-s2-'+label+'-', dir=self.directory)).resolve(strict=True)
        driver = None; evidence = {'run_id': self.run_id, 'candidate_sha': self.candidate, 'authorization_sha256': self.auth,
            'label': label, 'binding_proof': proof, 'owned_run_root': str(root)}; self.evidence[label] = evidence
        context = SimpleNamespace(root=root, binding={'candidate_sha': self.candidate, 'authorization_sha256': self.auth})
        try:
            self.archive.register(root, label)
            for name in ('input', 'output', 'temp', 'custom_nodes'): (root/name).mkdir()
            args = SimpleNamespace(run_id=self.run_id, max_public_submissions=20 if warm else 45,
                max_loopback_requests=8192, max_native_clock_reads=128, warm_benchmark=warm, native_audit=not warm,
                ffprobe_exe=None, nvidia_exe=str(self.paths['nvidia_exe']), **{key: str(self.paths[key]) for key in ('powershell', 'comfy_main', 'comfy_python', 'ollama_exe', 'ffmpeg_exe')})
            driver = NativeRuntime(args, evidence); context.driver = driver
            self._deploy(root)
            staged = {}
            for kind, value in self.samples.items():
                source = Path(value['path']); reference = 'authorized-'+kind+source.suffix.lower()
                staged[kind] = self._copy(source, root/'input'/reference, value, limit=(20 if kind == 'image' else 256)*1024**2)
            references = None if warm else self._references(driver, root)
            self.authorize('native_preflight', label); evidence['preflight'] = driver.preflight()
            ram = int(driver._powershell('(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory'))//1024
            if ram < 2048: raise EvidenceError('factory host RAM below minimum')
            baseline = evidence['preflight']['max_used_mib']; evidence['preflight']['available_ram_mib'] = ram
            self.authorize('start_owned_ollama', label); driver.start_ollama(root/'ollama.log')
            evidence['no_cloud_gate'] = driver.no_cloud_remote_gate()
            evidence['model'] = driver.verify_model()
            if evidence['model']['digest'] != self.model: raise EvidenceError('factory actual model digest changed')
            evidence['resource_profile']=profile(model=evidence['model']['model'],digest=evidence['model']['digest'])
            self.authorize('start_owned_comfy', label); driver.start_comfy(root, root/'comfy.log')
            info = plain(root/'user').stat(); self.user_roots[root] = (info.st_dev, info.st_ino)
            self._user_root(driver, root)
            registry = driver.registry()
            if not REQUIRED_NODES.issubset(registry): raise EvidenceError('factory actual public registry incomplete')
            evidence['public_registry'] = {name: registry[name] for name in sorted(REQUIRED_NODES)}
            # Comfy startup can clear temp. Install the finite profile only
            # after readiness, owned CLI/user-root and registry verification,
            # before any production request; the writer still refuses overwrite.
            parameters = dict(candidate_sha=self.candidate, authorization_sha256=self.auth, model_digest=self.model)
            if warm:
                binding = driver.write_warm_binding(root, **parameters, nvidia_sha256=self.digests['nvidia_exe'], baseline_gpu_mib=baseline)
            else:
                binding = driver.write_native_binding(root, **parameters, max_runs=19)
            context.binding = binding
            self.authorize('start_owned_resource_sampler', label)
            worker = driver.start_sampler(root, nvidia_exe=str(self.paths['nvidia_exe']), nvidia_sha256=self.digests['nvidia_exe'])
            driver.resource_observer(); evidence['ownership'] = driver.ownership_summary()
            if warm:
                result = WarmContext(driver=driver, root=root, binding=binding, worker=worker, samples=staged)
            else:
                fixture = self.plan['categories']['tracking']; reference = references['tracking']
                config = dict(schema_version='lvw.s2.browser-config/1', run_id=self.run_id, candidate_sha=self.candidate,
                    authorization_sha256=self.auth, expires_at=binding['expires_at'], run_root=str(root),
                    sample_path=str(root/'input'/reference), sample_sha256=fixture['sha256'], sample_bytes=fixture['bytes'],
                    browser_executable=str(self.paths['browser_executable']), browser_executable_sha256=self.digests['browser_executable'],
                    playwright_module=str(self.paths['playwright_module']), playwright_entry_sha256=self.digests['playwright_module'],
                    protocol_nonce=secrets.token_hex(32), budget=dict(BROWSER_BUDGET))
                for key, path in (('harness_sha256', 'tools/v0_s2_browser_acceptance.cjs'),
                        ('policy_sha256', 'tools/v0_s2_browser_policy.cjs'),
                        ('ui_workflow_sha256', 'LVW_V0_RuntimePatch/workflows/video_reverse_prompt_v0.ui.json')):
                    config[key] = self.source_identity['execution_artifact_sha256'][path]
                def verify(current, action):
                    self.authorize('verify_browser_runtime_bindings', action)
                    if current != config: raise EvidenceError('factory browser config changed')
                    guarded = self.guard_critical()
                    if (guarded.get('complete_rehash') is not False or guarded.get('manifest_sha256') != self.manifest
                            or not {key.upper() for key in TOOL_KEYS}.issubset(guarded.get('critical_files', []))):
                        raise EvidenceError('factory critical tool binding guard incomplete')
                    driver.resource_observer(); birth = self._user_root(driver, root)
                    return {'owned_run_root': str(root), 'comfy_pid': birth['pid'], 'ephemeral_user_root_verified': True}
                def launch(current):
                    self.authorize('authorize_original_browser_worker', label); self._complete()
                    value = verify(current, 'before_node_launch')
                    return {**value, 'candidate_sha': self.candidate, 'authorization_sha256': self.auth,
                        'node_sha256': self.digests['node_executable']}
                result = DefaultContext(driver=driver, root=root, binding=binding, image=staged['image'],
                    baseline_gpu_mib=baseline, fixture_plan=self.plan, references=references, primary_category='tracking',
                    browser_config=config, node_executable=str(self.paths['node_executable']), node_sha256=self.digests['node_executable'],
                    authorize_launch=launch, verify_bindings=verify, nvidia_exe=str(self.paths['nvidia_exe']), nvidia_sha256=self.digests['nvidia_exe'])
            self.contexts[label] = result
            (root/'temp/runtime-preparation.json').write_bytes(encoded(evidence))
            return result
        except BaseException as error:
            failure = {'error_type': type(error).__name__, 'error': str(error), 'root_name': root.name,
                'run_id': self.run_id, 'candidate_sha': self.candidate, 'authorization_sha256': self.auth,
                'stage_pass_claim': False, 'evidence': evidence}
            if isinstance(error, base.StopProbe):
                failure['error_evidence'] = copy.deepcopy(error.evidence)
                evidence['admission_error_evidence'] = copy.deepcopy(error.evidence)
            if driver is not None:
                try:
                    failure['cleanup'] = driver.cleanup()
                    if failure['cleanup'].get('proven') is True: failure['archive'] = self.archive(context, failure['cleanup'])
                except Exception as cleanup_error: failure['cleanup_error'] = type(cleanup_error).__name__+':'+str(cleanup_error)
            # Unknown/partial native lineage is retained rather than guessed or
            # overwritten by another attempt. The terminal parent sees this file.
            failure['root_retained'] = root.exists()
            with (self.directory/(label+'-preparation-failure.json')).open('xb') as output: output.write(encoded(failure))
            raise
