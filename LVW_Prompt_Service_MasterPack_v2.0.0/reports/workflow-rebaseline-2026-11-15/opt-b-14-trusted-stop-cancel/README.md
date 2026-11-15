# Deferred cancellation correction

CTRL01-M1 is OPEN pending source readiness and short runtime proof. Original opt-b-13 files/plan remain preserved and unexecuted. Current194 functional/CPUcleanup evidence stays supported; old hard-control qualification is unchanged.

TERM/INT handlers now only record a pending cancellation. They never throw across Popen construction, child ownership publication or cleanup entry. After the exact Popen/PID/recovery journal is retained, cancellation is consumed before further waiting. Running waits poll at most50ms to observe pending cancellation; repeated signals cannot bypass mandatory bounded TERM/KILL/reap. A known pre-launch cancellation returns without launching. No signal masks are inherited by the child. CLI uses real Popen; the keyword-only factory seam is solely for the frozen trusted-control regression.

Selftest02 preserves the original four normal/nonzero/TERM/KILL cases and adds a real created-before-publication cancellation regression. Its instance-local factory forwards the actual Popen call, retains that exact child independently, sends realTERM+INT to the controller before returning the same Popen, then validates retained PID/cancellation/reap. No replacement lifecycle or mock child. Adapter fallback is bounded and always invalidates the regression. No candidate/guard/194 execution is authorized by this preparation.

Same limits: Linux cooperative single child only, no descendants/native/adversarial/parentSIGKILL proof; scheduling/Popen latency is not hard-real-time. Existing guard must refuse spawning. Cleanup graces count inside future runtime envelope. Source review and root activation are necessary before the five short processes may launch.
