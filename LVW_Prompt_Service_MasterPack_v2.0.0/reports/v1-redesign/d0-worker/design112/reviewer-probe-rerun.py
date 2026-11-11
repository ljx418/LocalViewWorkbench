"""Re-run the reviewer owned probes P01/P02/P05/P22/P23/P24 against the
corrected candidate. The reviewer module is imported read-only; nothing is
written into the review directory. Only the tree copy is trimmed.
"""
import importlib.util, json, shutil, sys, tempfile
from pathlib import Path

REPO = Path("/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0")
REVIEW = REPO / "reports/v1-redesign/d0-review/design111/checks/probes.py"

spec = importlib.util.spec_from_file_location("reviewer_probes", REVIEW)
probes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probes)
probes.OWNER = REPO

KEEP_REPORTS = {
    "v1-redesign/legacy-gates-before-change.json",
    "v1-redesign/product-change-approval.json",
    "v1-redesign/design11-adjudication.json",
    "v1-redesign/design111-adjudication.json",
    "v1-redesign/design112-adjudication.json",
    "unified-media/live-15/video-model-run.json",
}

def ignore(dirpath, names):
    directory = Path(dirpath)
    try:
        rel = directory.relative_to(REPO).as_posix()
    except ValueError:
        return set()
    if rel == "reports":
        return {n for n in names if ("v1-redesign/" + n) not in KEEP_REPORTS and n not in ("v1-redesign", "unified-media")}
    if rel == "reports/v1-redesign":
        return {n for n in names if n not in {"legacy-gates-before-change.json", "product-change-approval.json", "design11-adjudication.json", "design111-adjudication.json", "design112-adjudication.json"}}
    if rel == "reports/unified-media":
        return {n for n in names if n != "live-15"}
    return set()

def fast_build_copy(tmp):
    root = tmp / "pkg"
    shutil.copytree(REPO, root, ignore=ignore, ignore_dangling_symlinks=True)
    return root

probes.build_copy = fast_build_copy

probes.probe("P01-n6-unpinned-alias-drift",
             "N6: rename an unpinned scene hash column alias",
             probes.m_n6_alias_drift, fence=True, expect_code="E_SCENE_HASH_MAPPING")
probes.probe("P02-n6-sql-argument-permutation",
             "N6: permute the lvw_scene_hash arguments",
             probes.m_n6_sql_argument_permutation, fence=True, expect_code="E_SCENE_HASH_MAPPING")
probes.probe("P05-n1-scene-get-body-swapped",
             "N1: the new Scene GET returns another candidate component",
             probes.m_n1_scene_get_body_swapped, fence=True, expect_code="E_SCENE_GET_ENVELOPE")
probes.probe("P22-malformed-overlay-metadata",
             "the overlay metadata_only is a list",
             probes.m_overlay_metadata_is_list, fence=True, expect_code="E_OVERLAY_METADATA_SHAPE")
probes.probe("P23-malformed-overlay-headers",
             "the overlay add_response_headers is a list",
             probes.m_overlay_headers_is_list, fence=True, expect_code="E_OVERLAY_HEADER_SHAPE")
probes.probe("P24-invalid-candidate-schema",
             "the candidate schema carries an invalid regular expression",
             probes.m_invalid_candidate_schema, fence=True, expect_code="E_SCHEMA_PATTERN")
probes.probe("P00-positive-control",
             "the unmodified copy still passes",
             probes.no_mutation, fence=True)

for entry in probes.RESULTS:
    print("%-40s exit=%s codes=%s" % (entry["probe"], entry["exit_code"], entry.get("finding_codes")))
    if entry["exit_code"] != 0:
        print("   stdout:", entry["stdout"].strip().replace("\n", " | ")[:400])
        if entry["stderr"].strip():
            print("   stderr:", entry["stderr"].strip().replace("\n", " | ")[:400])
