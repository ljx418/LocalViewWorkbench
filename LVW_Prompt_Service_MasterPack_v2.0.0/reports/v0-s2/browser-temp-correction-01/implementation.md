# Chromium Linux scratch correction

full-v0-auto-02 remains NO_GO. Its public phase passed15/15, but Chromium launch under DrvFS terminated with SIGTRAP before any browser case. Native services/sampler stopped; original root is retained because independent browser ownership was never established. No old result is promoted to complete Stage acceptance.

Finite browser-launch-diagnostic-01 sealed candidate a8d12a242c1dfd41693fbb60835485ba5d84ccb7, exact Node/Chromium/Playwright hashes and two launches. Same flags/environment, only fresh scratch filesystem differs: DrvFS SIGTRAP versus Linux /tmp successful blank launch. Both original process groups and owned scratch roots cleaned. No media, model, service, cloud or download. The experiment supports filesystem incompatibility without claiming an exact Chromium internal crash cause.

Only browser scratch moves to unique /tmp/lvw-s2-browser-* mode0700. Persist candidate/run/authorization/device/inode/UID lease before Node. Product data and raw evidence remain in the bound run root. Existing worker/browser birth, executable, fresh profile, loopback driver and independent cleanup proofs remain. After independent browser and Node/callback closure, identity-checked fd-based deletion removes scratch. Lease-write failure removes unused empty root; no-Node failures clean with explicit NODE_NEVER_STARTED proof. Unknown post-launch ownership preserves scratch and flags cleanup unproven.

No public contract, denominator, sample, model, context, token/resource/latency/cancellation limit or retry rule changes. Existing V0 parent permits this finite verification correction; human signoff remains separate.
