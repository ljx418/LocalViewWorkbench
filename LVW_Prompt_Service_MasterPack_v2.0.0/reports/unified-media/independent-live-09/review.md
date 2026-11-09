# Independent live-09 terminal review

Decision: **NO_GO — WAIT_RESOURCE**. This is a terminal evidence audit of candidate `fd9044e29ea923d4b1c7e1a1d9f5af47b35b9a81`, not a human signature or full R1/V1 approval.

The sole original provider event is `admission_snapshot`: GPU free18515MiB, used5624MiB, RAM10215MiB. Frozen `provider.py` rejects free<19047MiB before `lease_acquired` or `provider_call_started`. The public job ends failed/RESOURCE_BUSY/released with null result. Thus zero model sends/load actions and zero effective full checkpoint are correct. The grant is explicitly approved and bound; no new authorization or budget increase is indicated.

Independent recomputation verified111 frozen/source/sample bindings against working files and candidate git blobs where tracked, actual executable hashes, packet1.0.3, COMPLETE03 request/approval hashes and API build `f3cb7a34e6f4863a46e21672b4ac4daa667de774db3f6282a2680ed42bc83d26`. Raw real negatives show VIDEO_DURATION_LIMIT and MEDIA_INVALID before model start.

Native owner nonce8812e3b7d30740bb85fabe109e83468e, PID7984/birth639298154327977341 is exited/listener_owned=false. Original API PID3269072/birth9558204 has a matching finished-server log and run-owned-temp removal. Stop receipt says unreachable/stopped, browser finally closed with no external requests/page errors, and terminal receipt proves absent listeners/temp. Native logs show OLLAMA_NO_CLOUD:true and loopback host. No post-inference release claim is made because no lease was acquired.

Read-only SQLite independently shows live09 calls0/checkpoint0/active0/elapsed12, matching child and binding hashes. Historical program02 carry-forward rows are unchanged. Snapshot actual totals:9/1024 model actions,3/24 effective full checkpoints,406/172800 production seconds. No active reservation existed at that snapshot; later readiness children are outside this audit.

The independent gitblob CPU snapshot passed54 controlled tests with4 real-process/probe tests deselected. Socket connect/connect_ex and subprocess.Popen were denied; no new model/service/browser/media probe/decode occurred. Tests retain production file/input/decoder owners, clear error/cancel/PTS/cleanup oracles and controlled transports. Initial collection/missing-tools errors are preserved, followed by a successful run; only review scaffolding was corrected. These tests supplement approved RUNTIME01 obligations and do not turn missing real video evidence into acceptance.

UM-04 remains NOT_RUN. There is no real sampled-frame or model-output artifact for live09; four complete source F frames, explicitly derived absRGB D panels, and whether output incorrectly claims constant grid/red-box relative position cannot be judged this run. No historical model output or prior independent conclusion substitutes for it. Adoption/export, real running cancel, offline manual export and full image/video browser combination were not reached. `coverage.json` records exactly10 frozen rows,2 PASS and8 incomplete/blocked.

Reproduce CPU-only terminal audit: `python3 -B reports/unified-media/independent-live-09/recompute.py`. Raw evidence hashes and recomputed ledger snapshot are retained alongside this review. Only this review directory was written; candidate, live09 evidence and real ledger were not modified.
