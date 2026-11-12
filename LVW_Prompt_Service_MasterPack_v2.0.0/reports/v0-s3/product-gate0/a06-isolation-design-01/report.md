# A06 temporary isolation: bounded architecture recommendation

**Recommendation for root: retain native WFP as the sole next feasibility candidate, requiring a narrowly scoped elevated broker; do not freeze a product executor yet. No route satisfying the current authority is proven feasible.** Privilege alone does not solve per-run identity, delegated DNS, event loss or crash ordering. This is design evidence, not implementation, independent candidate acceptance, authorization or Stage PASS.

2026-11-12. Clean review worktree fast-forwarded with `git merge --no-edit 0308ccb`; base `0308ccbcb6c72ba679c5922a39be54d153123f37`. Read AGENTS/governance, current coordinate, docs06/24, original S3 preparation packet and the four requested A06/budget records. No candidate/P3B files touched. Research used exactly six Microsoft pages, listed inline; no host capability query or product network request occurred.

## Facts and mechanism choice

**Local recorded facts, not new observations:** a06-wfp-read-01/receipt.json says nonadmin token, EngineOpen=0, GetOption(COLLECT_NET_EVENTS)=5, Close=0, collection state unknown. FilterAdd and Subscribe were not attempted; their outcomes remain unknown. Native Windows Comfy/Ollama/GPU remain required. A06 requires blocked nonloopback egress **and** observed attempts; repeated blocked attempts still fail docs06. The B-child known40-action floor, two full=True children and unresolved final budget remain unchanged.

**Microsoft-confirmed:** WFP OPEN is distinct from engine READ, filter-container ADD, referenced-object ADD_LINK, transaction rights and event SUBSCRIBE. Default admin access is broad, but the relevant object permissions must actually succeed; no DACL takeover is justified. [Access control, rights table](https://learn.microsoft.com/en-us/windows/win32/fwp/access-control)

Dynamic sessions delete their own added WFP objects when the session ends, including program termination. They do not bind objects to a PID lineage. [FwpmEngineOpen0, Remarks](https://learn.microsoft.com/en-us/windows/win32/api/fwpmu/nf-fwpmu-fwpmengineopen0)

ALE_APP_ID is an executable device path; ALE_USER_ID is a local-user security-descriptor condition. The documented conditions do not supply a general PID-plus-birth predicate. **Inference:** shared Python/Ollama path or ordinary account-SID rules would affect unrelated instances and are rejected. [Filtering condition identifiers](https://learn.microsoft.com/en-us/windows/win32/fwp/filtering-condition-identifiers-)

Event subscription requires separate permission; API success promises subscription creation, not a lossless audit of every application networking action. Select the supported API/event version explicitly; Subscribe0 is the Windows7 version. [FwpmNetEventSubscribe0](https://learn.microsoft.com/en-us/windows/win32/api/fwpmu/nf-fwpmu-fwpmneteventsubscribe0)

Event collection is documented as enabled by default, but that is not the local value. Collection settings persist across reboots; SetOption is forbidden inside a dynamic session. **Decision:** do not toggle collection or keywords, even with a promised restore. If existing settings are insufficient, return to root with the exact gap instead of expanding this permission proposal. [FwpmEngineSetOption0, Remarks](https://learn.microsoft.com/en-us/windows/win32/api/fwpmu/nf-fwpmu-fwpmenginesetoption0)

**Alternative rejected for this increment:** AppContainer provides identity, device/file and network isolation, but this overview does not establish this installed CUDA/Ollama/Python stack's GPU access, existing weight/file access, loopback client/server compatibility or transient profile lifecycle. A restricted token alone likewise is not demonstrated to enforce the required networking boundary. Do not add loopback exemptions, broad ACL grants, accounts or packaging changes to make an unverified substitute work. [AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)

## Required design properties — hypotheses to validate, not an executable recipe

1. **Identity before launch:** broker creates a fresh run-only security context, starts only approved native roots suspended, and records process handles, PID, creation time, executable identity, parent chain and token identity. A unique logon-SID condition through ALE_USER_ID is a *candidate hypothesis*, not guaranteed by the six pages: demonstrate its access-check semantics, safe token creation without permanent account/ACL changes, and inherited identity in Ollama runners/decoder children first. Ordinary duplicated user tokens or a job membership list are not proof of a new WFP identity. If that hypothesis fails, stop; do not fall back to shared-path blocking or a new driver.
2. **Enforce before resume:** install/verify run-specific dynamic objects transactionally, start the observer, then resume owned roots. Proposed ALE connect authorization at IPv4 and IPv6 must exclude only actual loopback, with no TCP-only or port53-only shortcut; validate UDP, IPv4-mapped addresses, multicast/broadcast and child traffic. Preserve required 127.0.0.1/::1 endpoints. Layer/condition availability, filter arbitration against existing policy and loopback semantics need a frozen native test, not an assumption that a higher weight wins. Prevent child identity escape before execution; retrospective PID discovery leaves a gap.
3. **DNS and delegation:** direct DNS/DoH egress belongs in the block/observe matrix. A resolver or local broker may transmit under a shared service identity; blocking that service would disrupt unrelated users. Literal loopback service URLs reduce DNS need but do not prove no DNS attempts. Require attributable observation of owned callers' resolver requests and demonstrate that delegated requests cannot escape the run boundary. No complete method is established here; no global DNS-service filter is proposed. An unrelated loopback proxy is not an allowed egress relay.
4. **Observe the whole interval:** retain bounded raw events with run/filter IDs, available application/user identity, address family, protocol, destination, timestamps, subscription lifecycle and error/loss/queue-overflow state. PID/birth attribution requires separate contemporaneous lineage evidence; do not invent absent event fields. Start before resume, stop after all owned descendants exit and callbacks drain. Positive controls must recover every planned attempt, including denied UDP/DNS and children. These prove sampled coverage only: no callback, “zero established connections,” or a healthy-looking collector proves losslessness. Unknown kernel delivery loss, attribution or interval gaps make zero-attempt evidence UNPROVEN; an event stream is not a syscall-by-syscall counter.
5. **Cleanup and crash ordering:** normal order is stop owned work → prove descendants exited → drain observer → remove only recorded run GUIDs → close session and verify absence. Dynamic cleanup removes filters on broker death and may therefore reopen networking while children survive. A kill-on-close job/guardian is a candidate lifecycle control, not proof of atomic kill-before-filter-removal. Freeze/test supervisor, collector and owner-crash cases; no claimed crash-safe enforcement until ordering is established. Never kill a PID without handle/birth ownership or alter unrelated policy. Crash cleanup receipts must preserve uncertainty, not infer success posthoc.

## Minimal extra scope for ROOT consideration

Propose **one short-lived elevated local broker invocation**, not elevation of Comfy, Ollama or the development agent. Required access: engine OPEN/READ and transaction rights; READ/ENUM to inspect relevant objects; ADD on run-object containers, ADD_LINK on the exact referenced layers/sublayer, DELETE for owned objects; net-event SUBSCRIBE plus applicable READ/ENUM. Only engine READ denial is locally confirmed; the other rights are required/unmeasured, not claimed missing. Prefer existing authorized elevation rather than granting permanent DACL rights. Exclude engine WRITE/SetOption, WRITE_DAC/take-ownership, driver/service installation, new accounts, system audit policy, firewall-profile changes and arbitrary elevated commands. Token creation authority must be specified only after the proposed run-identity mechanism is established.

**Draft finite validation envelope, not current permission:** one child ≤300s, ≤8 explicitly owned synthetic processes, ≤32 dynamic objects, ≤16 predeclared socket/DNS attempts, ≤8MiB evidence, zero model/GPU/media/production service/ledger actions. First read settings/permissions and validate identity; any denial, unusable collection state or shared-identity match stops before traffic. Only after root freezes exact predicates, observer and crash method may it approve the bounded writes and intentional blocked nonloopback attempts, with controlled same-executable sibling negatives and loopback positives. No retries or automatic fallback. Success would establish only a capability subset; native GPU/files/runtime compatibility and complete observer assurance still need their later bound children. Risks for root: elevated execution, wrong-identity overblocking, delegated DNS leakage, telemetry exposure/loss and crash-time unblocking. If zero unrelated impact or complete observation cannot be established within these limits, preserve the architectural blocker rather than request broad system control.

## Ten-field handoff (coordinate unchanged)

1. 当前坐标: R1 / WP-R1-U3 / S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW / PREPARING_NEXT_STAGE.
2. 本批完成: repository/documentation feasibility review only; six official pages, no tests or implementation acceptance.
3. 最后通过门禁: unchanged UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW, candidate621b1bf, scoped human acceptance only.
4. 当前阻塞门禁: S3_P3B_INDEPENDENT_REVIEW_AND_COMPLETE_PRODUCT_GATE0_PENDING; A06 identity/observer/lifecycle remain design gaps.
5. 全局路线位置: root architecture disposition → separately authorized bounded feasibility → frozen executor contract; Claude P3B correction continues separately.
6. 剩余工作: exact identity/privileges, DNS/observer loss/crash proof, original-workflow/install/rollback lifecycle and final budgets; quality/full12/Gate0/release unchanged.
7. 下一责任人: root architecture/contract/authorization owner; no direct user approval request from this worker.
8. 所需授权: none for this completed read-only review; proposed privilege/validation scope above is not authorized by this report.
9. 证据目录: reports/v0-s3/product-gate0/a06-isolation-design-01/; report.md and receipt.json only.
10. 精确停止原因: bounded investigation complete; no nativeWindows/WSL/PS/parser/hosthash/media/model/GPU/services/firewall/networktest/systemconfig/realledger/claims/checkpoint, no secrets/holdouts/prelabels, no push; retain visible terminal.

## Complete V0–V3 outline (unchanged)

Current product coordinate remains **R1**; this A06 investigation advances no substep. Values below are copied from execution-control at0308ccb; implementation, machine, independent and human states remain distinct.

| Delivery | Stage | Done/total | Implementation | Machine | Independent | Human |
|---|---|---:|---|---|---|---|
|V0|V0-S0|1/2|ARCHIVED|NO_GO_HISTORICAL|COMPLETED_WITH_BLOCKERS|NOT_SIGNED|
|V0-Min|V0-S1|5/5|DELIVERED|ACCEPTED_SCOPE_ONLY|COMPLETED|APPROVED|
|V1前置|R0|1/2|PARTIAL_REUSED|SINGLE_IMAGE_SUBSET_ONLY|NO_SEPARATE_R0_VERDICT|NO_SEPARATE_R0_SIGNOFF|
|V1早期切片|R1a|5/5|DELIVERED|ACCEPTED_SCOPE_ONLY|COMPLETED|APPROVED|
|V0.1|V0-S2|7/8|IMPLEMENTED|COMPLETE_FIXED9_PASSED|COMPLETE_FATAL0_MAJOR0_MINOR0|PENDING|
|V0.2|V0-S3|0/6|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V1|R1|0/4|EARLY_SLICE_IMPLEMENTED_FULL_R1_PENDING|EARLY_SLICE_UM10_ONLY|EARLY_SLICE_FATAL0_MAJOR0|EARLY_SLICE_APPROVED_FULL_R1_PENDING|
|V1|V1-M1|0/3|DESIGN_ONLY|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V1|R2|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V2|R3|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V2|R4|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5a|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5b|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5c|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
