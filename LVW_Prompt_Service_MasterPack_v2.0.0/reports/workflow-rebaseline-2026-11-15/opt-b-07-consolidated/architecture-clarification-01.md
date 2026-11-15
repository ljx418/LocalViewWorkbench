# Clarification of existing F06-M4 and offline boundary

The parent custody `_ParentReplyPump` (`zero_session._pump`) and the channel `_WindowsPipeWorker` whose `is_alive` is faulted are distinct owners. Exact identity obligations apply to the corresponding resource, never across these classes. Preserve parent-pump/context/background-owner proof separately. Capture the actual relevant pipe worker independently at the real zero channel reader/session observation seam before the final query; compare the injected receiver with that held reference. Expected reference cannot come from the injected receiver itself. Startup owner/thread must likewise be captured independently before faults.

Prefer a scoped/default-inert fixture-only observation callback, restored and reset per case, rather than stale global retained references. This clarifies the frozen identity requirement; it adds no production API or permission.

The implementation packet permits AST-only source analysis and no compile/import/collect/test execution. A transcript displayed `compile ok`; the producer must state any actual command and its limited effect accurately if such a check happened, avoid further prohibited checks, and never equate shell exit0 or syntax checking with successful patch application or test execution. Historical output stays intact. This note does not authorize an exception or root product implementation takeover.

Root guidance was sent as msg_7de2c844d218 to original implementation dispatch ctx_c929a8f6bdee. Source remains the implementer owner; guard03 actual owncanary evidence is separate.
