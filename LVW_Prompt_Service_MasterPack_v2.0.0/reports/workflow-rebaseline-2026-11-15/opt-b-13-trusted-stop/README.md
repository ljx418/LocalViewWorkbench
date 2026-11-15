# Trusted stop correction (CPU harness only)

CP10-M1 remains open. Both fresh194 functional datasets and their CPU cleanup remain supported; neither old attempt becomes a hard-controlled PASS.

`bounded_exec.py` owns one Popen child, an absolute monotonic execution deadline, TERM grace, KILL grace and bounded waitpid/reap. It signals only that unreaped child; SIGCHLD auto-reaping is disabled in the controller process. It records intended command/cwd/environment, child PID/birth/session/group, actual signals and return/reap state. A timeout is a failed workload even when cleanup succeeds. Unknown reap is STOP_UNPROVEN. Caller return/background behavior is not the deadline owner.

This is Linux cooperative, single-child control only. Use with the existing guard that refuses spawning/native loading, not arbitrary programs with descendants. No parent SIGKILL/crash, hostile/native containment, Windows process tree or hard real-time scheduling guarantee is added. Parent handlers perform bounded cleanup on ordinary TERM/INT, but abrupt parent death is outside proof. PID/birth is diagnostic; kernel ownership of the unreaped child supplies signal targeting.

Production admission must freeze the exact request/tool/interpreter and actual command/cwd/env. Its budget must include wall limit plus both cleanup graces (for a290s envelope choose wall288s, TERM0.5s and KILL1s, leaving scheduling margin); caller wait caps never replace this owner. No runtime or production use is admitted by source presence.

The four-case selftest is separately frozen in control-selftest-01. No selftest process may start before independent source readiness and root activation ACK. Cases: normal exit0, exit13, TERM-responsive deadline expiry, TERM-ignoring deadline expiry requiring KILL. Each requires real child ready/identity, actual expected signal/exit/waitpid reap and exact owned /proc identity no longer present. Negative control outcomes never count as successful workload results. This batch does not rerun194 or consume a product checkpoint slot.
