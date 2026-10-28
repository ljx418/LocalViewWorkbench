#!/usr/bin/env python3
"""One-shot, loopback-only V0-Min experience audit wrapper."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


PACK = Path(__file__).resolve().parents[2]
HARNESS = PACK / "reports/v0-s1/wp-s1-03-phase-a/live_probe.py"
AUTHORIZATION_ID = "AUTH-V0-MIN-EXPERIENCE-AUDIT-01"
RUN_ID = "v0-min-experience-audit-01"
EVIDENCE_RELATIVE = "reports/v0-min-experience-audit-01/evidence/live"
SAMPLE_SHA256 = "b129104984043dfbc4338dd16652d5e6440ea61936c61db434259a57a291e5b2"
PRODUCT_CANDIDATE = "1d48142b95466954ca4da264fa06762abf1522f2"
HARNESS_SHA256 = "94953202138267ca988818a5ba75704d845c15e288fb406d8f7af21d1af4af52"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_harness():
    spec = importlib.util.spec_from_file_location("lvw_experience_live_probe", HARNESS)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    module.AUTHORIZATION_ID = AUTHORIZATION_ID
    module.AUTHORIZED_SAMPLE_SHA256 = SAMPLE_SHA256
    module.AUTHORIZED_EVIDENCE_RELATIVE = EVIDENCE_RELATIVE
    module.AUTHORIZED_RUN_ID = RUN_ID
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", required=True)
    parser.add_argument("--comfy-main", required=True)
    parser.add_argument("--comfy-python", required=True)
    parser.add_argument("--ollama-exe", required=True)
    parser.add_argument("--temp-parent", required=True)
    args = parser.parse_args()
    sample = Path(args.sample).resolve(strict=True)
    if file_sha256(sample) != SAMPLE_SHA256:
        raise SystemExit("sample hash mismatch")
    if file_sha256(HARNESS) != HARNESS_SHA256:
        raise SystemExit("harness hash mismatch")

    probe = load_harness()
    live_args = argparse.Namespace(
        authorization_id=AUTHORIZATION_ID,
        candidate_sha=PRODUCT_CANDIDATE,
        harness_sha256=HARNESS_SHA256,
        harness_relative="reports/v0-s1/wp-s1-03-phase-a/live_probe.py",
        repo=str(PACK),
        sample=str(sample),
        sample_sha256=SAMPLE_SHA256,
        comfy_main=args.comfy_main,
        comfy_python=args.comfy_python,
        ollama_exe=args.ollama_exe,
        powershell="powershell.exe",
        temp_parent=args.temp_parent,
        evidence_root=str(PACK / EVIDENCE_RELATIVE),
        run_id=RUN_ID,
    )
    probe.validate_live_boundaries(live_args, reserve_evidence=True)
    code, result = probe.execute(live_args)

    trace = result.get("evidence", {}).get("public_image_trace", {})
    texts = trace.get("history_ui_text", [])
    raw = json.loads(texts[0]) if len(texts) > 0 else None
    suggestion = json.loads(texts[1]) if len(texts) > 1 else None
    evidence = result.get("evidence", {})
    minimized = {
        "schema_version": "lvw.experience-audit-result/1",
        "run_id": RUN_ID,
        "authorization_id": AUTHORIZATION_ID,
        "authorization_status": "EXPIRED_TERMINAL",
        "decision": result.get("decision"),
        "exact_stop_reason": result.get("exact_stop_reason"),
        "product_candidate": PRODUCT_CANDIDATE,
        "sample_sha256": SAMPLE_SHA256,
        "attempts": result.get("attempts"),
        "service_starts": result.get("service_starts"),
        "public_submissions": result.get("public_submissions"),
        "external_cost": result.get("external_cost"),
        "raw_model_result": raw,
        "prompt_spec": suggestion,
        "machine_facts": {
            "preflight": evidence.get("preflight"),
            "network_gate": evidence.get("network_gate"),
            "model_identity": evidence.get("model_identity"),
            "image_oracle": evidence.get("image_oracle"),
            "runtime_guard": evidence.get("runtime_guard"),
            "model_cleanup": evidence.get("model_cleanup"),
            "target_integrity": evidence.get("target_integrity"),
            "post_cleanup_snapshot": evidence.get("post_cleanup_snapshot"),
            "state_transitions": evidence.get("state_transitions"),
        },
        "cleanup": result.get("cleanup"),
        "raw_service_logs_persisted": False,
        "formal_product_gate_effect": "none"
    }
    out = PACK / EVIDENCE_RELATIVE / "result.json"
    out.write_text(json.dumps(minimized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {"result.json": file_sha256(out)}
    (out.parent / "artifact-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "decision": minimized["decision"],
        "exact_stop_reason": minimized["exact_stop_reason"],
        "evidence": str(out.relative_to(PACK)),
    }, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
