#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid
from urllib.parse import urlsplit

import httpx


EXPECTED_SAMPLE_SHA256 = "b4bbd08a0fad67cc04e55d15bf2c48e9a76dcfd6dda147d8cc504452dfc78a42"


def stop(code: str, **details) -> int:
    print(json.dumps({"status": "FAIL", "code": code, "details": details},
                     ensure_ascii=False, sort_keys=True))
    return 1


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    default_sample = root.parent.parent / "testSource" / "图片-4.jpg"
    parser = argparse.ArgumentParser(description="Verify the public LVW image-analysis experience")
    parser.add_argument("--base-url", default="http://127.0.0.1:18765")
    parser.add_argument("--sample", type=Path, default=default_sample)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path not in {"", "/"}:
        return stop("BASE_URL_NOT_LOOPBACK", base_url=args.base_url)
    if not args.sample.is_file():
        return stop("SAMPLE_MISSING", sample=str(args.sample))
    sample_bytes = args.sample.read_bytes()
    sample_sha256 = hashlib.sha256(sample_bytes).hexdigest()
    if sample_sha256 != EXPECTED_SAMPLE_SHA256:
        return stop("SAMPLE_HASH_MISMATCH", expected=EXPECTED_SAMPLE_SHA256,
                    actual=sample_sha256)

    base = args.base_url.rstrip("/")
    try:
        with httpx.Client(timeout=10, trust_env=False) as client:
            readiness = client.get(f"{base}/api/v1/readiness")
            readiness.raise_for_status()
            ready = readiness.json()["data"]
            if not ready.get("ready") or ready.get("model") != "gemma4:26b":
                return stop("ANALYSIS_NOT_READY", readiness=ready)
            upload = client.post(f"{base}/api/v1/media",
                headers={"Idempotency-Key": f"experience-upload-{uuid.uuid4().hex}"},
                files={"file": ("fixed-sample.jpg", sample_bytes, "image/jpeg")})
            upload.raise_for_status()
            media = upload.json()["data"]
            if media["sha256"] != sample_sha256:
                return stop("UPLOAD_HASH_MISMATCH", expected=sample_sha256,
                            actual=media.get("sha256"))
            submitted = client.post(f"{base}/api/v1/jobs/analyze",
                headers={"Idempotency-Key": f"experience-analysis-{uuid.uuid4().hex}"},
                json={"media_ref_id": media["id"], "shot_id": None, "mode": "realistic",
                      "config_profile": "local-default"})
            submitted.raise_for_status()
            job = submitted.json()["data"]
            deadline = time.monotonic() + args.timeout
            while job["status"] not in {"succeeded", "partial", "failed", "cancelled", "interrupted"}:
                if time.monotonic() >= deadline:
                    return stop("ANALYSIS_TIMEOUT", job_id=job["id"])
                time.sleep(0.5)
                response = client.get(f"{base}/api/v1/jobs/{job['id']}")
                response.raise_for_status()
                job = response.json()["data"]
            if job["status"] != "succeeded" or not job["result_ref"]:
                return stop("ANALYSIS_TERMINAL_FAILURE", job=job)
            response = client.get(f"{base}/api/v1/model-runs/{job['result_ref']}")
            response.raise_for_status()
            run = response.json()["data"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        return stop("PUBLIC_PATH_ERROR", error=type(exc).__name__, message=str(exc))

    spec = run.get("parsed_spec") or {}
    required = {
        "observation": bool((spec.get("domains") or {}).get("observation")),
        "text_zh": bool(spec.get("text_zh")),
        "text_en": bool(spec.get("text_en")),
        "negative": bool(spec.get("negative")),
        "tags": bool(spec.get("tags")),
    }
    if not all(required.values()):
        return stop("OUTPUT_DENOMINATOR_INCOMPLETE", required=required, run_id=run.get("id"))
    print(json.dumps({"status": "PASS", "model": ready["model"],
        "sample_sha256": sample_sha256, "job_id": job["id"], "run_id": run["id"],
        "required_outputs": required}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
