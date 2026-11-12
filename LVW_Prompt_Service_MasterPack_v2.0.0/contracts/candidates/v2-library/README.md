# V2 library candidate 0.2

Design snapshot only; canonical contracts and current Stage remain unchanged. See docs33–35/ADR15 and plans/candidates/v2-library/activation.json. library.schema.json defines strict new DTOs; openapi-overlay.json merges disjoint paths and Library_ components in memory; storage-additions.sql compiles only over isolated baseline fixtures; mcp-additions.json has no apply/undo tools.

CANDIDATE_MANIFEST.sha256 pins root-relative design files. Snapshot hash is review identity, not StageGate0 or product PASS. Run `python3 -B tools/verify_v2_library_design.py --self-test` from MasterPack; no real database, source media or model is touched. Final V1 schema and native Windows capability require later explicit rebase/validation before activation.

Design0.2 corrects independent M01/M02/m01–m04 together: strong head ETag headers, duplicate-target preview rows plus separate executable reservations, summary-only plan GET, typed Job projection, explicit retry lineage and bounded accounting. See semantic-rules.json/job-compatibility.json; old review/failing observations stay immutable.
