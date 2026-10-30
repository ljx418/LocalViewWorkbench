#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

import httpx
from playwright.sync_api import sync_playwright


EXPECTED_SAMPLE_SHA256 = "b4bbd08a0fad67cc04e55d15bf2c48e9a76dcfd6dda147d8cc504452dfc78a42"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Verify the LVW browser experience")
    parser.add_argument("--base-url", default="http://127.0.0.1:18765")
    parser.add_argument("--sample", type=Path,
                        default=root.parent.parent / "testSource" / "图片-4.jpg")
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path not in {"", "/"}:
        print(json.dumps({"status": "FAIL", "code": "BASE_URL_NOT_LOOPBACK"}))
        return 1
    if not args.sample.is_file() or hashlib.sha256(args.sample.read_bytes()).hexdigest() != EXPECTED_SAMPLE_SHA256:
        print(json.dumps({"status": "FAIL", "code": "SAMPLE_IDENTITY_INVALID"}))
        return 1

    started = False
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.goto(args.base_url, wait_until="networkidle")
            page.get_by_test_id("ollama-state").wait_for(timeout=10000)
            if page.get_by_test_id("runtime-start").is_enabled():
                page.get_by_test_id("runtime-start").click()
                started = True
            page.get_by_test_id("ollama-state").wait_for(state="visible", timeout=45000)
            page.get_by_test_id("model-state").get_by_text("可用", exact=True).wait_for(timeout=45000)
            page.get_by_test_id("image-input").set_input_files(str(args.sample))
            page.get_by_test_id("content-profile").select_option("faithful")
            page.get_by_test_id("custom-guidance").fill("重点描述构图、光线和可见材质，不添加画面外事实。")
            page.get_by_test_id("analyze").click()
            page.wait_for_function("""() => {
              const text = document.querySelector('.status')?.textContent || '';
              return text.includes('分析完成，等待你采纳') || text.includes('本次分析未完成');
            }""", timeout=240000)
            if "本次分析未完成" in page.locator(".status").inner_text():
                raise RuntimeError(page.locator(".error[role=alert]").last.inner_text())
            page.get_by_role("button", name="采纳到人工稿").click()
            values = {
                "text_zh": page.locator("#draft-natural-zh").input_value(),
                "text_en": page.locator("#draft-natural-en").input_value(),
                "image_prompt": page.locator("#draft-image-prompt").input_value(),
                "negative": page.locator("#draft-negative").input_value(),
                "tags": page.locator(".tag-field input").input_value(),
            }
            if not all(value.strip() for value in values.values()):
                raise RuntimeError(f"OUTPUT_DENOMINATOR_INCOMPLETE:{values}")
            if page.get_by_test_id("runtime-stop").is_enabled():
                page.get_by_test_id("runtime-stop").click()
                page.get_by_test_id("ollama-state").get_by_text("stopped", exact=True).wait_for(timeout=20000)
                started = False
            browser.close()
        print(json.dumps({"status": "PASS", "sample_sha256": EXPECTED_SAMPLE_SHA256,
                          "outputs_nonempty": {key: True for key in values}}, ensure_ascii=False,
                         sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "code": "UI_EXPERIENCE_FAILED",
                          "error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False,
                         sort_keys=True))
        return 1
    finally:
        if started:
            try:
                with httpx.Client(timeout=15, trust_env=False) as client:
                    status = client.get(args.base_url.rstrip("/") + "/api/v1/runtime/status").json()["data"]
                    if status["ollama"]["managed"]:
                        client.post(args.base_url.rstrip("/") + "/api/v1/runtime/ollama/stop",
                                    headers={"X-LVW-Control": "local-ui"})
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
