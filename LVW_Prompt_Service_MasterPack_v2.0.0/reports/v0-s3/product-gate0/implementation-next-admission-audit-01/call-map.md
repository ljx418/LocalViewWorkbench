# N2 call map — the current real source, read only

OPT-C-NEXT-ADMISSION-01 · audit thread 1 · baseline HEAD `58881bd97e2602d70d8407df8b5fbf9e53aac4b3` · product source candidate `b9a81aed8e8f8fe6763a4dfd3d051cacf10e0820`

Everything below is read from the exact current sources of the repository at the baseline above. No source was edited, imported, compiled, collected or executed, and no service, model, GPU, native, media, network, database or counter action was performed. The historical `implementation-native-execution-readiness-01/proposed-implementation-packet.md` is **design input only**: it is not a frozen N2 contract and nothing below is derived from it.

## 0. The audited files and their exact hashes

| file | sha256 |
|---|---|
| tools/v0_s2_stage_runtime.py | `cf6ad01d66c0c7885475eedeae5ba66df9bec61bf7281ee511600f6224833e26` |
| tools/v0_s3_stage_runtime.py | `c4815fdc2140961171af938ba5396763260314de2e938a1087ab6b21038b1aad` |
| tools/v0_s3_coordinator.py | `14e8dd284971aeab00999f010679d5c95deb88ee3bff8f4ca0708d958b56f12c` |
| tools/v0_s3_quality_worker.py | `e3648446f39d6e7a1c31f180248ccb59c36272ddc10c80edbe544f7d3c595592` |
| tools/v0_s2_runtime.py | `a97ea20d02ed80ab4f99f133dd8162331ddba34662bfdcca637fcade40b4dbd2` |
| tools/v0_s2_driver.py | `72883e2fa0c252aef7655708f40ada88a755978d71f632043c8203b53b42afed` |
| tools/v0_s2_stage_sequence.py | `0b6be81e1cf9d0db88e7f5fe581f23686418d3a15634bd53f88ccb56f8718e20` |
| tools/v0_s3_production_controller.py | `a452275a866b8b496175ecf3cba37d86fd0109be91020c09948f9bf9583a2b38` |
| tools/v0_s3_native_custody.py | `7f26e9276a1c7507b0ad716fc31d8f5a4b17e5b670625a6982c52fbb93494581` |
| tools/v0_s3_native_broker.py | `06cfc9518ccb782d456b930f627ca99e0774f82e81d214115277cef3be79bb83` |
| LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py | `7968f4682dfe272877a814f4b4b46dc50e5fb0775f03cc122f4c121d9dade765` |
| LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/resource_policy.py | `997021aeac31cd8ed814deebd4dbd0137f002468be5b0feccc238fdf1d82f708` |
| LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/video_evidence.py | `217de485ee626861241f6fd4f469f8cf5be380601e2b7272f3db892a57d8cff8` |
| LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/benchmark.py | `bd6e167e6de8c8546a50e689d7958f02aee89d9e9ad2cd88ec180af18fca46ba` |

## 1. The real current prepare lifecycle

`StageRuntimeFactory` — `tools/v0_s2_stage_runtime.py:54`. `prepare_default` → `_prepare(False)` (`:155`), `prepare_warm` → `_prepare(True)` (`:156`). The body of `_prepare` (`:158-270`) is the **only** real preparation lifecycle in the tree, in this exact order:

| # | step | line | what it actually does |
|---|---|---|---|
| 1 | order / replay / default-root closure | `:163-164` | `label in self.used` or a live `default` root ⇒ `EvidenceError('factory order/replay/default root not closed')` |
| 2 | admission | `:165` | `self.authorize('prepare_bound_native_runtime', label)` |
| 3 | complete execution binding | `:166` | `self._complete()` → `verify_complete()` proof (`:80-89`): binding scope, `complete_rehash is True`, candidate, manifest sha256, the nine `TOOL_KEYS` path+sha256 bindings |
| 4 | owned run root | `:167` | `_allocate_preparation_root(label)` — S3 override creates the root by `os.mkdir` relative to the **parent descriptor** (`tools/v0_s3_stage_runtime.py:179-191`) |
| 5 | archive registration | `:172` | `self.archive.register(root, label)` |
| 6 | preparation directories | `:173` | `input`, `output`, `temp`, `custom_nodes` (`tools/v0_s3_stage_runtime.py:193-200`, dir-fd relative, `O_NOFOLLOW`) |
| 7 | **driver construction** | `:177` | `driver = NativeRuntime(args, evidence)`; `context.driver = driver` (`:170`) |
| 8 | deployment | `:179` | S3 override `_deploy` (`:345-440`) installs the frozen package through `package.ProtectedInstall`, verifies the manifest, the sandbox marker, the ownership record and every payload digest |
| 9 | authorized samples | `:181-183` | `_copy` of the image and the video sample into `root/input/authorized-*` |
| 10 | public references (default only) | `:184` | `_references` (`:116-134`): categories, negatives, `empty.mp4`, `oversize.mp4`, the reparse fixture |
| 11 | **preflight** | `:186` | `self.authorize('native_preflight', label)` then `driver.preflight()` |
| 12 | host RAM | `:188-190` | `FreePhysicalMemory`; `< 2048` ⇒ `EvidenceError('factory host RAM below minimum')` |
| 13 | **baseline** | `:191` | `baseline = evidence['preflight']['max_used_mib']` |
| 14 | **ollama** | `:192` | `self.authorize('start_owned_ollama', label)` then `driver.start_ollama(root/'ollama.log')` |
| 15 | cloud gate | `:194` | `driver.no_cloud_remote_gate()` |
| 16 | model identity | `:196-198` | `driver.verify_model()`, then the digest must equal `self.model` |
| 17 | resource profile | `:199` | `resource_policy.profile(model=…, digest=…)` |
| 18 | **comfy** | `:200` | `self.authorize('start_owned_comfy', label)` then `driver.start_comfy(root, root/'comfy.log')` |
| 19 | user root identity | `:202` | `(st_dev, st_ino)` of `root/user` is pinned in `self.user_roots` |
| 20 | **owned listener proof** | `:203` | `self._user_root(driver, root)` (`:136-153`): the archive lease, the listener birth (`driver.owned_listener_birth(8191)`) and the Comfy CLI argument reproof |
| 21 | public registry | `:205-208` | `driver.registry()`, `REQUIRED_NODES.issubset(registry)` |
| 22 | **first exclusive profile write** | `:212-214` | `binding = self._write_profile_binding(driver, root, label, baseline)`; `context.binding = binding` |
| 23 | **sampler** | `:215-218` | `self.authorize('start_owned_resource_sampler', label)` then `driver.start_sampler(root, nvidia_exe=…, nvidia_sha256=…)`, `driver.resource_observer()`, `driver.ownership_summary()` |
| 24 | context construction | `:220-251` | warm ⇒ `WarmContext(driver, root, binding, worker, samples)`; default ⇒ `DefaultContext(driver, root, binding, image, baseline_gpu_mib=baseline, fixture_plan, references, primary_category, browser_config, node_executable, node_sha256, authorize_launch, verify_bindings, nvidia_exe, nvidia_sha256)` |
| 25 | evidence and return | `:252-254` | `self.contexts[label] = result`; `_persist_preparation_evidence(root, label, evidence)`; **returns the context** |
| — | failure path | `:255-270` | failure record, `driver.cleanup()`, the archive on a proven cleanup, `_persist_preparation_failure`, re-raise |

**The order that matters**: preflight (and therefore the measured baseline) comes **before** ollama; the model digest and the resource profile come **after** ollama and **before** comfy; the **first and only** exclusive profile write comes **after** the registry check and **before** the sampler. `_write_profile_binding` (`:293-308`) resolves the extra parameters *before* the writer runs, so the S3 budget capability is part of the very first write; the writers create their file with `open('x')` and refuse an overwrite (`tools/v0_s2_runtime.py:149`, `:164`).

## 2. The inheritance chain and the returned driver identity

```
StageRuntimeFactory                       tools/v0_s2_stage_runtime.py:54
  └─ InstalledPackageRuntimeFactory       tools/v0_s3_stage_runtime.py:75
       └─ S3InstalledRuntimeFactory       tools/v0_s3_coordinator.py:309
```

`InstalledPackageRuntimeFactory` inherits `_prepare` **unchanged** — `super()._prepare(warm)` at `tools/v0_s3_stage_runtime.py:251` — and adds only: the protected parent descriptor and the dir-fd root allocation (`:179-191`), the directory creation (`:193-200`), the preparation guard (`:106-116`), the archive adapter (`:49-72`), the exclusive evidence write (`:202-220`) and the bounded callbacks around `verify_bindings` / `authorize_launch` (`:222-237`).

`S3InstalledRuntimeFactory` adds exactly one behaviour: the private profile binding hook (`:324-330`), which returns **only** `{'s3_budget_binding': dict(self.binding)}` and raises `S3IntegrationError('S3_PROFILE_PARAMETER_SET_INVALID')` for any other key set. The hook is resolved before the first profile write, so the sealed S3 budget capability is inside the first write.

**Returned driver identity**: the object returned by `_prepare` *is* the context whose `.driver` is the **same** `NativeRuntime` instance that started ollama (`:192`), started comfy (`:200`), measured the baseline (`:186-191`), wrote the profile (`:212`) and started the sampler (`:216`). `DefaultContext.driver` / `WarmContext.driver` (`tools/v0_s2_stage_sequence.py:22-46`) carry that instance, and `context.binding` is the profile value written by that same driver. There is **no** second driver in the prepared path.

**The phase protocol re-proves that identity**: `StageSequence.context` (`tools/v0_s2_stage_sequence.py:73-80`) requires `context.driver.submissions == 0` (an uncontaminated prelude), the matching warm mode, a non-redirected root, and then `root = context.driver.owned_listener_birth(11434)` with `(root['pid'], root['start_ticks']) == (context.binding['ollama_pid'], context.binding['ollama_start_ticks'])` — otherwise `EvidenceError('Stage bound model root changed')`.

**The ordered sequence** (`tools/v0_s2_stage_sequence.py:118-181`): `authorize('prepare_default_runtime')` → `prepare_default()` → context check → cumulative *online* → public → offline runner → browser → cumulative *offline* → `default.driver.submissions == 45` → `close(default, complete=True)` → `authorize('prepare_fresh_warm_runtime')` → `prepare_warm()` → context check → the fresh/same-model rule (`:160-163`: a different root, the same model digest, a **different** ollama pid/ticks) → warm phase → `warm.driver.submissions == 20` → `close(warm, complete=True)`. The terminal decision string is `MACHINE_SEQUENCE_COMPLETE_REQUIRES_INDEPENDENT_REVIEW_AND_HUMAN_SIGNOFF` (`:171`) — it is **not** a Stage PASS.

## 3. `build_native_driver` is not a production path, and the public entry refuses

`build_native_driver(context)` — `tools/v0_s3_quality_worker.py:615-641`. It builds a **second**, independent `NativeRuntime` from `context.document['driver_arguments']` (`warm_benchmark=False`, `native_audit=True`, `max_public_submissions=45`, `max_loopback_requests=8192`, `max_native_clock_reads=128`, `ffprobe_exe=None` plus the six tool paths) with `evidence = {'owned_run_root': str(context.root)}`. Its own docstring says it "is the *future* interface of the native execution and it is not reachable from the command line of this worker".

* **No product caller.** The only reference outside its own definition is `tools/test_v0_s3_production_composition.py:1219`, where it is *denied* (`monkeypatch.setattr(worker, 'build_native_driver', deny)`). The only product callers of `prepare_default` / `prepare_warm` are `tools/v0_s2_stage_checkpoint.py:553` and `tools/v0_s2_browser_component.py:121`; every other call site is a test.
* **The public entry refuses before any construction.** `main()` (`tools/v0_s3_quality_worker.py:548`) parses `--context` / `--context-sha256`, then at `:594-596`: `if driver is None: raise WorkerError(NATIVE_EXECUTION_BACKEND_NOT_READY)` — the refusal is written as `S3_WORKER_REFUSED <code>` to stderr and the entry returns 2 (`:604-605`). The refusal happens **before** any driver is constructed and before any model is touched.
* **The native admission is a diagnostic, never a permission.** `verify_native_admission(context, document)` — `tools/v0_s3_production_controller.py:567-600` — states that the verification scope is `SHAPE_AND_IDENTITY_OF_SEALED_DOCUMENTS_ONLY`, that the budget binding scope is `SEALED_BINDING_SHAPE_ONLY_NOT_BALANCE_NOT_AUTHORIZATION_NOT_CUSTODY`, and that "there is no accepted native execution backend on this platform, so the report is never accepted: the stable code `NATIVE_EXECUTION_BACKEND_NOT_READY` is the primary reason of every report".
* **The offline composition seam is not a service path.** `OfflineCompositionSeam` (`tools/v0_s3_production_controller.py:1044-1064`) replaces exactly three things: the native driver construction, the OS child process and the monotonic clock; it is a Python object, is never written into a context document, is never reachable from the command line and cannot start a native service, because the driver construction is never called while the seam is active. Its cooperative cancel cannot kill a non-cooperating worker: the worker stays retained, the seam reports the retention and the run stays unknown.

**Consequence for N2**: preparing a factory and *then* constructing a driver independently (the `build_native_driver` shape) would create a second owner of the same root while the prepared driver still owns the services and the profile. The current source has no such path, and the audit does not propose one.

## 4. The strict consumer, the two true profiles, and the provenance of baseline / PID birth / budget cap

**The strict consumer** is the bridge-side native checkpoint telemetry, `LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/video_evidence.py:16-31` (`validate_binding`). It requires exactly these five identity bindings plus the run facts:

1. `candidate_sha` — 40 lowercase hex (`:18-19`)
2. `authorization_sha256` — 64 lowercase hex (`:18-19`)
3. `model_digest` — 64 lowercase hex (`:18-19`)
4. `program_authorization_id` — exactly `AUTH-PROGRAM-V1-COMPLETE-03` for the S3 scope, otherwise `AUTH-PROGRAM-V1-LOCAL-01` (`:26`)
5. `scope` — exactly `V0_S3_NATIVE_CHECKPOINT` or `V0_S2_NATIVE_CHECKPOINT` (`:26`)

and then: `max_runs` an int in 1..64 (`:27`), `ollama_pid` and `ollama_start_ticks` positive ints (`:27`), and `issued_at`/`expires_at` a finite window of at most 21600 s (S3) or 7200 s (`:29-31`). The warm counterpart is `benchmark.validate_binding` (`benchmark.py:25-42`) with the same five identity bindings plus `baseline_gpu_mib` (a valid baseline, `:36`) and `max_requests == 20` (`:36`).

**The two true profiles are different documents**:

| key | native / default profile | warm profile |
|---|---|---|
| written by | `write_native_binding` — `tools/v0_s2_runtime.py:152-165` | `write_warm_binding` — `tools/v0_s2_runtime.py:131-150` |
| file | `temp/lvw-native-profile.json` (`:164`) | `temp/lvw-warm-profile.json` (`:148`) |
| scope | `V0_S2_NATIVE_CHECKPOINT` (`:158`) | `V0_S2_WARM_BENCHMARK` (`:140`) |
| program | `AUTH-PROGRAM-V1-LOCAL-01` (`:158`) | `AUTH-PROGRAM-V1-LOCAL-01` (`:140`) |
| budget key | `max_runs` = **19** (written at `tools/v0_s2_stage_runtime.py:308`) | `max_requests` = **20** (`:141`) |
| `baseline_gpu_mib` | **absent** | present (`:142`) |
| `nvidia_smi_sha256` | absent | present (`:141`) |
| ollama identity | `ollama_pid`, `ollama_start_ticks` (`:159`) | `ollama_pid`, `ollama_start_ticks` (`:143`) |
| window | `issued_at` … `expires_at` = +7200 s (`:160`) | +7200 s (`:144`) |

The S3 overlay replaces the program/scope and adds the child identity: `program_budget.s3_profile` (`program_budget.py:151-158`) rewrites `program_authorization_id` to `AUTH-PROGRAM-V1-COMPLETE-03`, maps `V0_S2_` → `V0_S3_`, and adds `child_path`, `child_sha256`, `run_id`, `budget_binding_sha256`, `expires_at`; then `validate_profile` (`program_budget.py:137-148`) requires the profile to match the sealed binding on the eight mapped keys `candidate_sha, authorization_sha256→child_sha256, child_sha256, child_path, run_id, model_digest, ollama_pid, ollama_start_ticks`, the program id, the scope, the binding seal and the nested expiry window.

**Provenance of the three facts**:

* **baseline** — `evidence['preflight']['max_used_mib']` (`tools/v0_s2_stage_runtime.py:191`). That value is produced by `NativeRuntime.preflight` (`tools/v0_s2_runtime.py:59-74`): the Windows `nvidia-smi --query-gpu` and the local WSL `nvidia-smi` rows are parsed and passed to `resource_policy.admit` (`resource_policy.py:38-59`), whose evidence carries `max_used_mib = max(row[2] for row in rows)`. It is a **measured** value; `resource_policy.profile()` (`:20-29`) itself contains **no** `baseline_gpu_mib` key at all — the profile and the baseline are different things, and the warm profile carries the measured baseline while the default profile does not.
* **PID birth** — `owned_listener_birth(port)` (`tools/v0_s2_runtime.py:124-129`) returns `{'pid', 'start_ticks', 'name'}` from `self.listener_births[port]`, which is filled only by `_prove_listener_owned` (`tools/v0_s2_driver.py:118-145`): the wrapper process handle must be live (`self._wrapper_handles`), the wrapper pid file is read, and WMI `CreationDate`/`StartTime` ticks of the **listener** and of the **wrapper** are compared with the expected executable path; a mismatch or a reused pid raises `StopProbe('LISTENER_BIRTH_PROOF_INVALID')` / `'LISTENER_OR_WRAPPER_PID_REUSED'`.
* **budget cap** — `max_runs=19` for the native profile (`tools/v0_s2_stage_runtime.py:308`, validated `1<=max_runs<=64` at `tools/v0_s2_runtime.py:155`) and `max_requests=20` for the warm profile (`tools/v0_s2_runtime.py:141`). The consumer enforces `self.runs >= self.binding['max_runs']` → `refused('NATIVE_RUN_BUDGET_OR_TOKEN_INVALID')` (`video_evidence.py:58-60`).

**Fail codes observed in these paths** (exact strings): `EvidenceError('factory order/replay/default root not closed')`, `'factory complete execution binding not proven'`, `'factory sample size binding changed'`, `'factory sample hash binding changed'`, `'factory deployed plugin is not exact frozen candidate'`, `'factory public inputs incomplete'`, `'factory user root replaced'`, `'factory Comfy launch arguments missing'`, `'factory Comfy CLI/user directory differs from frozen launch'`, `'factory host RAM below minimum'`, `'factory model digest changed'`, `'factory actual public registry incomplete'`, `'factory critical tool binding guard incomplete'`; `StopProbe('NATIVE_CLOCK_BUDGET_INVALID')`, `'GPU_PREFLIGHT_WSL_FAILED'`, `'RESOURCE_TELEMETRY_INVALID'`, `'PREFLIGHT_TARGET_PORT_OWNED'`, `'PREFLIGHT_TARGET_PROCESS_PRESENT'`, `'OWNED_WRAPPER_HANDLE_NOT_LIVE'`, `'LISTENER_BIRTH_PROOF_INVALID'`, `'LISTENER_OR_WRAPPER_PID_REUSED'`, `'RUNTIME_WARM_BINDING_INVALID'`, `'RUNTIME_COLD_BASELINE_INVALID'`, `'NATIVE_BINDING_ID_INVALID'`, `'NATIVE_RUN_BUDGET_INVALID'`, `'OLLAMA_EXECUTABLE_PATH_INVALID'`; `PolicyError('GPU_MODEL_PROFILE_UNVERIFIED')`, `'GPU_CAPACITY_INSUFFICIENT'`, `'GPU_RUNTIME_PEAK_EXCEEDED'`, `'GPU_MEMORY_HEADROOM_INSUFFICIENT'`; `BridgeError('SCOPE_FORBIDDEN', …, subcode='NATIVE_BINDING_INVALID' | 'NATIVE_BINDING_EXPIRED' | 'S3_PROFILE_BINDING_INVALID' | 'BENCHMARK_BINDING_INVALID' | 'BENCHMARK_BINDING_EXPIRED' | 'S3_BRIDGE_PROCESS_FAILED' | 'S3_BRIDGE_RECEIPT_INVALID' | 'S3_BRIDGE_RECEIPT_EXPIRED' | 'S3_BUDGET_BINDING_OR_BRIDGE_INVALID')`; `S3IntegrationError('S3_BUDGET_PROVIDER_REQUIRED' | 'S3_PROFILE_PARAMETER_SET_INVALID' | 'S3_OWNED_RUN_ROOT_UNAVAILABLE' | 'S3_BUDGET_*')`; `WorkerError(NATIVE_EXECUTION_BACKEND_NOT_READY)` → `S3_WORKER_REFUSED <code>`.

## 5. N1 custody handle/job semantics versus the legacy wrapper pid proof

**N1 (the current product custody, CPU proven)**: `tools/v0_s3_native_broker.py` owns **one job object per round**: `create_job` (`:1309`, `CreateJobObjectW`), `set_job_kill_on_close` (`:1316`), `assign_process_to_job` (`:1754`, `AssignProcessToJobObject`), `terminate_job` (`:1332`, `TerminateJobObject`), `job_process_ids` (`:1338`, `QueryInformationJobObject`), released by `_release_the_job` (`:3484`) and terminated by `_terminate_the_job` (`:3319`). The custody session owns the **original handle of the broker** and releases it only after the confirmed facts (`tools/v0_s3_native_custody.py:963`, `:975`); the identity source recorded in the evidence is `PARENT_ORIGINAL_HANDLE` (`tools/v0_s3_native_custody.py:1759`). The N1 round therefore owns: the parent-side original handle, the per-round job object, and the private channel.

**Legacy S2 driver ownership** (the `ollama`/`comfy` services of the N2 path): `tools/v0_s2_driver.py` owns a **wrapper pid file** plus a live wrapper **process handle** (`self._wrapper_handles`, `:65`, `:120-121`) and proves the listener through WMI birth ticks (`:118-145`). The wrapper process is spawned by `start_ollama` (`tools/v0_s2_runtime.py:167-181`), which writes `ollama-wrapper.pid` next to the log and registers the `Popen` handle.

**Where a thin explicit adapter can reuse the original facts** (no new owner, no new file, no second service):

* the *shape* the phase protocol already consumes is `{'pid', 'start_ticks', 'name'}` (`tools/v0_s2_runtime.py:129`); the N1 side already produces the equivalent identity of an owned child from **its own** handle (`PARENT_ORIGINAL_HANDLE`) — an adapter that surfaces the **owner's own** pid/birth facts in that exact shape reuses the original facts instead of re-deriving them;
* the custody/broker already owns the child process handle and the job, so the *ownership* of the listener can be proven by the owner's own handle rather than by a wrapper pid file;
* the sampler already consumes the owner facts through `driver.owned_listener_birth(port)['pid']` (`tools/v0_s2_runtime.py:188`), so the consumer side needs no new interface if the producer side keeps that exact shape.

**Where a new bounded interface / owner decision is needed** (root decisions, not implementation choices):

* the N1 custody owns the **broker** process of a round; it does **not** own an `ollama` listener. A production path that starts ollama/comfy needs an owner of *those* services; the N1 job object is per round and its kill-on-close semantics are the round's, so reusing it for the long-lived service owners is an **owner decision**, not an adapter.
* the current ownership proof for the services is a **wrapper pid file** plus WMI ticks. The N1 model is an **original handle** plus a **job object**. Bridging the two is a decision about which model owns the services, because the wrapper pid file is a *file* that any writer can replace.
* the S3 budget capability is currently bound to the **profile** document (`program_budget.validate_profile`), whose `ollama_pid`/`ollama_start_ticks` must equal the live listener birth (`tools/v0_s2_stage_sequence.py:79`). An owner change changes what those two fields are bound to, and therefore the meaning of `program_budget.validate_profile` and of `video_evidence.validate_binding`.

**Explicitly not proposed and not to be done**: no forged or synthesised wrapper pid file; no second service owner; no bypass of `verify_native_admission` or of the `authorize(...)` admission chain; no reuse of the offline in-process seam (`OfflineCompositionSeam`) as a real production path; no use of the N1 CPU checkpoint as evidence of a native service execution.

## 6. What the audit concludes for N2 (facts, not a decision)

1. The real prepare lifecycle exists once, in `StageRuntimeFactory._prepare`, and the S3 factory inherits it unchanged and adds exactly one hook (the budget capability in the first profile write).
2. The order of the current source is: complete binding → owned root → driver → deployment → samples → **preflight/baseline** → **ollama** → model/profile → **comfy** → user-root/listener proof → registry → **first exclusive profile write** → **sampler** → context.
3. The returned context carries the **same** driver that owns the services and wrote the profile; there is no second driver in the prepared path, and `build_native_driver` has no product caller while the public worker entry refuses with `NATIVE_EXECUTION_BACKEND_NOT_READY` before any construction.
4. The strict consumer requires five identity bindings (candidate, authorization, model digest, program id, scope) plus the run facts; the native profile has no `baseline_gpu_mib` while the warm profile has it, and the baseline is the *measured* `max_used_mib` of the preflight.
5. The native production path is **blocked at admission** today: `verify_native_admission` is a diagnostic whose report is never accepted, and the primary reason of every report is `NATIVE_EXECUTION_BACKEND_NOT_READY`.
6. The ownership models differ: N1 = parent original handle + per-round job object; S2 services = wrapper pid file + WMI birth ticks. The smallest viable workpacks, the allowed file scopes and the minimum root decisions are in `minimal-workpack-proposal.json`; the R1-A/B Gate0 dependency facts are in `gate0-dependency-matrix.json`.
