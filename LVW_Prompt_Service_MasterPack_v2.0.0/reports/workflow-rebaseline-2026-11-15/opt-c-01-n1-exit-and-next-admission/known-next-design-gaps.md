# Next admission facts (design input, not code permission)

N1 current CPU component is PASS on exact b9a81ae/58881bd9/f33517eb with189 original+5supp and supervised control. Nine native obligations/product29/formalStage remain unproved. Do not rerun unchanged N1 by default.

The historical implementation-native-execution-readiness-01 proposal is not a frozen N2 contract. Current StageRuntimeFactory._prepare actually owns staging, preflight, start_ollama/start_comfy, first exclusive profile write, then sampler, and returns its driver/context. S3InstalledRuntimeFactory adds the budget hook but still inherits that lifecycle. build_native_driver currently constructs a separate NativeRuntime with no caller; worker defaultmain still refuses before construction. Blindly preparing one factory then independently constructing another driver loses lifecycle ownership.

The native default profile has no baseline_gpu_mib key, whereas the warm profile contains it; DefaultContext separately carries the original measured baseline. The proposal's assumed profile/order must be reconciled against actual source, never guessed baseline0 or trimmed arbitrary mappings. N1 parent broker owns original Windows handles/job; old S2 driver ownership relies on wrapper.pid/listener reproof. No forged wrapperPID file or unowned second service start may bridge them. Preserve existing refusal points and fail-closed admission.

Audit design/coding/live/formal-exit prerequisites separately, including R1 persistence/revisions preparation that may be independent of S3 packaging at coding level (plans/v1-workpack-development-map.json). This is a factual gate0 audit; root freezes interfaces/owners/acceptance after review, not the implementer.
