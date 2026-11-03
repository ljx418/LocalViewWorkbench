# WP-S2-01 file owner progress

Status: IN_PROGRESS. Contract changes: none. External actions: zero.

Added video_files.py: root-relative MP4/MOV reference resolution; reject traversal, UNC/URL/drive/ADS syntax, symlinks and Windows reparse attributes; open a regular file and compare descriptor identity; stream at most the frozen byte cap plus one detection byte into an exclusive run directory; bind copy hash/size; reject source mutation; always clean only the generated run directory. Snapshot I/O and cleanup failures use stable frozen codes without exposing absolute paths.

Directed tests: test_s2_video_files plus test_s2_video_input, 16/16 PASS. Fixtures are synthetic bytes in temporary directories and are never decoded. Includes exact/one-over, growth during copy, consumer failure, sibling-directory preservation, symlink paths and mocked Windows reparse attributes.

Limitations: native Windows/NTFS reparse and concurrent rename behavior still require target-machine evidence. The root and temporary parent are trusted application configuration. No FFmpeg process, real video, Comfy node or model was run. Public workflow integration and bounded decoder remain pending; no product acceptance PASS.

Next: bounded subprocess runner and actual FFmpeg frame/PTS adapter under the same snapshot lifetime, followed by resource/cancel integration and public Comfy workflow.
