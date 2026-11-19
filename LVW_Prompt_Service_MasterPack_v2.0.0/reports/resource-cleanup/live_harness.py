"""Finite public-UI cleanup check. Fixture and real runs have separate receipts."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "lvw/backend")]

from tools import local_program_authority as authority


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


class FixtureProvider:
    """Fixture-only evidence: never counted as a real model release."""
    model = "gemma4:26b"

    def __init__(self):
        self._lease = ("fixture_retained_lease", {})
        self.rows = [{"name": self.model}]
        self.fail = False

    async def readiness(self):
        return dict(ready=True, model=self.model, reason=None, loaded=bool(self.rows))

    async def _inventory(self): return self.rows

    async def release(self, _):
        await asyncio.sleep(0.35)
        if self.fail: return False
        self.rows = []
        self._lease = None
        return True


async def main(child_path: Path):
    # All imports that create product state occur only after the source/child seal exists.
    from app.config import Settings
    from app.main import create_app
    from app.provider import OllamaProvider
    from app.runtime import OllamaRuntime
    from app import resources
    import httpx
    import uvicorn
    from playwright.async_api import async_playwright

    child = json.loads(child_path.read_text())
    out = child_path.parent
    fixture = child["fixture"]
    data = Path(child["data_root"])
    checks, errors, external = [], [], []
    result = {"fixture": fixture, "candidate_sha": child["candidate_sha"], "checks": checks,
              "status": "NOT_COMPLETED", "actual_model_actions": 0, "cleanup": {}}
    provider = FixtureProvider() if fixture else OllamaProvider(
        "http://127.0.0.1:11434/api/chat", "gemma4:26b", 110, ledger_path=out / "provider.jsonl")
    exe = Path("/mnt/c/Users/Administrator/AppData/Local/Programs/Ollama/ollama.exe")
    runtime = OllamaRuntime(provider, exe if exe.is_file() else None, data)
    app = create_app(Settings(data_root=data, static_root=ROOT / "lvw/frontend/dist"), provider, runtime)
    server, server_task, sock = None, None, None
    browser = context = None

    def check(name, passed, detail=None):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        save(out / "progress.json", result)
        if not passed: raise AssertionError(name)

    try:
        async with asyncio.timeout(240):
            if not fixture:
                ready = await provider.readiness()
                save(out / "preflight.json", {"readiness": ready, "resources": await resources.snapshot()})
                if ready["reason"] == "OLLAMA_UNAVAILABLE":
                    await runtime.start()
                check("installed real model ready", (await provider.readiness())["ready"])
                # Empty inventory is mandatory before creating our own retained lease.
                await provider.acquire("cleanup_live_retained")
                authority.model_action(child_path)
                result["actual_model_actions"] += 1
                provider._sent = True
                async with httpx.AsyncClient(timeout=95, trust_env=False) as client:
                    response = await client.post("http://127.0.0.1:11434/api/generate",
                        json={"model": provider.model, "keep_alive": 120})
                    response.raise_for_status()
                loaded = await provider._inventory()
                check("own preload actually present", any(provider.model in {r.get("name"), r.get("model")} for r in loaded), loaded)

            sock = socket.socket()
            sock.bind(("127.0.0.1", child["port"]))
            server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="on"))
            server_task = asyncio.create_task(server.serve(sockets=[sock]))
            for _ in range(100):
                if server.started: break
                if server_task.done(): await server_task
                await asyncio.sleep(0.05)
            check("isolated API started", server.started)
            base = f"http://127.0.0.1:{child['port']}"
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True, executable_path=child["chromium_executable"])
                context = await browser.new_context(viewport={"width": 1440, "height": 1000})
                async def route(request_route):
                    url = request_route.request.url
                    if not url.startswith(base + "/"):
                        external.append(url)
                        await request_route.abort()
                    else: await request_route.continue_()
                await context.route("**/*", route)
                page = await context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                await page.goto(base, wait_until="networkidle")
                button = page.get_by_test_id("resource-cleanup")
                await button.wait_for()
                draft = page.locator("#draft-natural-zh")
                sentinel = "资源清理验证：保留我的人工稿，不自动覆盖。"
                await draft.fill(sentinel)
                async with page.expect_response(lambda r: r.url.endswith("/runtime/resources/cleanup")) as pending:
                    await button.click()
                    check("button disabled during cleanup", await button.is_disabled())
                response = await pending.value
                release = (await response.json())["data"]
                save(out / "cleanup-response.json", release)
                check("public cleanup actually released retained lease", release["status"] == "released" and release["verified"], release)
                await page.get_by_test_id("cleanup-result").get_by_text("已确认释放", exact=False).wait_for()
                check("manual draft preserved", await draft.input_value() == sentinel)
                check("lease actually cleared", provider._lease is None)
                check("real inventory target absent", not any(provider.model in {r.get("name"), r.get("model")} for r in await provider._inventory()))
                await page.screenshot(path=str(out / "cleanup-desktop.png"), full_page=True)

                async with page.expect_response(lambda r: r.url.endswith("/runtime/resources/cleanup")) as pending:
                    await button.click()
                check("repeat cleanup is noop", (await (await pending.value).json())["data"]["status"] == "noop")
                await page.get_by_role("button", name="再次检查服务").click()

                if fixture:
                    provider._lease = ("fixture_failed_lease", {})
                    provider.rows = [{"name": provider.model}]
                    provider.fail = True
                    await button.click()
                    await page.get_by_test_id("cleanup-result").get_by_text("未能确认", exact=False).wait_for()
                    check("failure displayed and lease retained", provider._lease is not None)
                    provider._lease = None
                    await button.click()
                    await page.get_by_test_id("cleanup-result").get_by_text("未执行清理", exact=False).wait_for()
                    check("external loaded model not touched", bool(provider.rows))
                else:
                    # Exactly one real fixed non-private image analysis after cleanup.
                    sample = ROOT / child["samples"][0]["path"]
                    await page.get_by_test_id("image-input").set_input_files(str(sample))
                    await page.get_by_test_id("analyze").click()
                    check("cleanup disabled during analysis", await button.is_disabled())
                    for _ in range(220):
                        jobs = list(app.state.analysis.jobs.values())
                        if jobs and jobs[-1].status in {"succeeded", "partial", "failed", "cancelled", "interrupted"}: break
                        await asyncio.sleep(0.5)
                    job = list(app.state.analysis.jobs.values())[-1]
                    save(out / "analysis-job.json", job.model_dump(mode="json"))
                    result["actual_model_actions"] += sum(json.loads(line).get("event") == "provider_call_started" for line in (out / "provider.jsonl").read_text().splitlines())
                    check("real image analysis after cleanup succeeds", job.status == "succeeded" and job.resource_state == "released", job.model_dump(mode="json"))
                    run = app.state.analysis.get_run(job.result_ref)
                    save(out / "analysis-result.json", run.model_dump(mode="json"))
                    check("machine suggestion does not replace manual draft", await draft.input_value() == sentinel)
                await page.set_viewport_size({"width": 390, "height": 844})
                check("mobile control panel has no horizontal overflow", await page.evaluate("document.documentElement.scrollWidth <= innerWidth"))
                await page.screenshot(path=str(out / "cleanup-mobile.png"), full_page=True)
                check("no JavaScript errors or external browser traffic", not errors and not external, {"errors": errors, "external": external})
                await context.close(); context = None
                await browser.close(); browser = None
            result["status"] = "PASS_FIXTURE_ONLY" if fixture else "PASS_REAL_LOCAL_CLEANUP_AND_IMAGE_REGRESSION"
    except Exception as error:
        result.update(status="FAIL_OR_BLOCKED", error_type=type(error).__name__, error=str(error))
    finally:
        if context: await context.close()
        if browser: await browser.close()
        if not fixture and provider._lease is not None:
            result["cleanup"]["remaining_lease_release"] = await provider.release(provider._lease[0])
        if fixture: provider._lease = None
        if server:
            server.should_exit = True
            await asyncio.wait_for(server_task, timeout=15)
        else:
            await app.state.analysis.close()
            await runtime.close()
        if sock: sock.close()
        result["cleanup"].update(api_task_finished=server_task is None or server_task.done(),
                                  browser_closed=browser is None, lease_cleared=provider._lease is None,
                                  runtime_owned_process_remaining=runtime._owned())
        terminal_known = all(result["cleanup"].get(k) is True for k in ["api_task_finished", "browser_closed", "lease_cleared"]) and not runtime._owned()
        if terminal_known:
            result["authorization_terminal"] = authority.settle(child["run_id"], result["actual_model_actions"])
        else:
            authority.close_retaining_reservation(child["run_id"])
            result["authorization_terminal"] = "CLEANUP_UNKNOWN_RESERVATION_RETAINED"
        save(out / "receipt.json", result)
        print(json.dumps({"status": result["status"], "checks": len(checks), "cleanup": result["cleanup"]}, ensure_ascii=False))
    return 0 if result["status"].startswith("PASS") and terminal_known else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(Path(sys.argv[1]).resolve())))
