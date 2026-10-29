const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

function arg(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) throw new Error(`missing ${name}`);
  return process.argv[index + 1];
}

(async () => {
  let browser;
  try {
    const url = arg("--url");
    const sample = arg("--sample");
    const evidence = arg("--evidence");
    fs.mkdirSync(evidence, { recursive: true });
    const ledgerPath = path.join(evidence, "browser-ledger.json");
    const ledger = { analysis_submissions: 0, manual_export_before_analysis: false, completed: false };
    const saveLedger = () => fs.writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2) + "\n");
    saveLedger();

    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      viewport: { width: 1280, height: 900 }, locale: "zh-CN", acceptDownloads: true,
      reducedMotion: "reduce",
    });
    await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: url });
    const page = await context.newPage();
    const blockedNonLoopback = [];
    await page.route("**/*", async route => {
      const target = new URL(route.request().url());
      const local = ["127.0.0.1", "::1"].includes(target.hostname);
      if (local || ["blob:", "data:"].includes(target.protocol)) return route.continue();
      blockedNonLoopback.push(`${target.protocol}//${target.host}`);
      return route.abort("blockedbyclient");
    });

    await page.goto(url, { waitUntil: "networkidle" });
    const draftFields = page.locator(".draft-grid textarea");
    const manual = {
      natural_zh: "人工中文描述：蓝色陶瓷杯",
      natural_en: "Manual English draft: blue ceramic cup",
      image_prompt: "Manual image prompt, cobalt ceramic cup",
      negative: "blur, watermark",
    };
    await draftFields.nth(0).fill(manual.natural_zh);
    await draftFields.nth(1).fill(manual.natural_en);
    await draftFields.nth(2).fill(manual.image_prompt);
    await draftFields.nth(3).fill(manual.negative);
    await page.locator(".tag-field input").fill("manual, unicode-蓝色");

    const manualDownloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "导出 JSON" }).click();
    const manualDownload = await manualDownloadPromise;
    const manualPath = path.join(evidence, "manual-export.json");
    await manualDownload.saveAs(manualPath);
    const manualExport = JSON.parse(fs.readFileSync(manualPath, "utf8"));
    if (manualExport.source.type !== "manual") throw new Error("manual export source mismatch");
    for (const [field, value] of Object.entries(manual)) {
      if (manualExport.outputs[field] !== value) throw new Error(`manual export mismatch: ${field}`);
    }
    ledger.manual_export_before_analysis = true;
    saveLedger();

    await page.locator('input[type="file"]').setInputFiles(sample);
    ledger.analysis_submissions = 1;
    saveLedger();
    const analyze = page.getByRole("button", { name: "分析这张图片" });
    await analyze.focus();
    await page.keyboard.press("Enter");
    await page.getByText("分析完成，等待你采纳").waitFor({ timeout: 180000 });
    if (await draftFields.nth(1).inputValue() !== manual.natural_en) {
      throw new Error("machine result overwrote dirty draft before adoption");
    }

    const observations = await page.locator(".evidence-grid article").nth(0).locator("li").allTextContents();
    const inferences = await page.locator(".evidence-grid article").nth(1).locator("li").allTextContents();
    const unknowns = await page.locator(".evidence-grid article").nth(2).locator("li").allTextContents();
    if (!observations.length) throw new Error("no observations rendered");
    const rawCollapsedByDefault = await page.locator("details.raw").evaluate(element => !element.open);
    if (!rawCollapsedByDefault) throw new Error("raw model response is expanded by default");

    page.once("dialog", dialog => dialog.accept());
    await page.getByRole("button", { name: "采纳到人工稿" }).click();
    const adopted = {
      natural_zh: await draftFields.nth(0).inputValue(),
      natural_en: await draftFields.nth(1).inputValue(),
      image_prompt: await draftFields.nth(2).inputValue(),
      negative: await draftFields.nth(3).inputValue(),
    };
    if (Object.values(adopted).some(value => !value.trim()) || adopted.image_prompt !== adopted.natural_en) {
      throw new Error("adopted four-output prompt fields are incomplete or inconsistent");
    }

    await page.getByRole("button", { name: "复制 English prompt", exact: true }).click();
    const clipboard = await page.evaluate(() => navigator.clipboard.readText());
    if (clipboard !== adopted.natural_en) throw new Error("clipboard mismatch");

    const jsonDownloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "导出 JSON" }).click();
    const jsonDownload = await jsonDownloadPromise;
    const jsonPath = path.join(evidence, "export.json");
    await jsonDownload.saveAs(jsonPath);
    const exported = JSON.parse(fs.readFileSync(jsonPath, "utf8"));
    for (const [field, value] of Object.entries(adopted)) {
      if (exported.outputs[field] !== value) throw new Error(`adopted JSON mismatch: ${field}`);
    }

    const txtDownloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "导出 TXT" }).click();
    const txtDownload = await txtDownloadPromise;
    const txtPath = path.join(evidence, "export.txt");
    await txtDownload.saveAs(txtPath);
    const txt = fs.readFileSync(txtPath, "utf8");
    for (const value of Object.values(adopted)) {
      if (value && !txt.includes(value)) throw new Error("TXT export mismatch");
    }

    const viewports = [[360, 800], [1280, 900], [1920, 1080]];
    const layouts = [];
    for (const [width, height] of viewports) {
      await page.setViewportSize({ width, height });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
      if (overflow) throw new Error(`horizontal overflow at ${width}`);
      const screenshot = path.join(evidence, `ui-${width}.png`);
      await page.screenshot({ path: screenshot, fullPage: true });
      layouts.push({ width, height, horizontal_overflow: overflow, screenshot: path.basename(screenshot) });
    }

    const result = {
      kind: "R1A_HEADLESS_PRODUCT_PATH_V2",
      observations, inferences, unknowns, manual_export: manualExport.outputs,
      adopted_outputs: adopted, clipboard_match: true, json_export_valid: true,
      txt_export_valid: true, dirty_draft_preserved_before_adoption: true,
      explicit_adoption_confirmed: true, raw_collapsed_by_default: true,
      keyboard_analysis_activation: true, reduced_motion_context: true,
      layouts, blocked_non_loopback_requests: blockedNonLoopback,
      passed: blockedNonLoopback.length === 0,
    };
    fs.writeFileSync(path.join(evidence, "browser-result.json"), JSON.stringify(result, null, 2) + "\n");
    ledger.completed = true;
    saveLedger();
    if (!result.passed) process.exitCode = 1;
  } catch (error) {
    console.error(error.stack || String(error));
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
  }
})().catch(error => {
  console.error(error.stack || String(error));
  process.exitCode = 1;
});
