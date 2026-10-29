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
  const ledger = { analysis_submissions: 0, completed: false };
  fs.writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2) + "\n");
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, locale: "zh-CN", acceptDownloads: true });
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: url });
  const page = await context.newPage();
  const nonLoopback = [];
  page.on("request", request => {
    const target = new URL(request.url());
    if (!["127.0.0.1", "::1"].includes(target.hostname)) nonLoopback.push(request.url());
  });
  await page.goto(url, { waitUntil: "networkidle" });
  await page.locator('input[type="file"]').setInputFiles(sample);
  ledger.analysis_submissions = 1;
  fs.writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2) + "\n");
  await page.getByRole("button", { name: "分析这张图片" }).click();
  await page.getByText("分析完成，等待你采纳").waitFor({ timeout: 150000 });
  const observations = await page.locator(".evidence-grid article").nth(0).locator("li").allTextContents();
  const inferences = await page.locator(".evidence-grid article").nth(1).locator("li").allTextContents();
  const unknowns = await page.locator(".evidence-grid article").nth(2).locator("li").allTextContents();
  if (!observations.length) throw new Error("no observations rendered");
  await page.getByRole("button", { name: "采纳到人工稿" }).click();
  const english = page.getByLabel("English prompt 复制");
  const englishValue = await english.inputValue();
  if (!englishValue.trim()) throw new Error("adopted English prompt is empty");
  await page.getByRole("button", { name: "复制", exact: true }).nth(1).click();
  const clipboard = await page.evaluate(() => navigator.clipboard.readText());
  if (clipboard !== englishValue) throw new Error("clipboard mismatch");
  const jsonDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 JSON" }).click();
  const jsonDownload = await jsonDownloadPromise;
  const jsonPath = path.join(evidence, "export.json");
  await jsonDownload.saveAs(jsonPath);
  const exported = JSON.parse(fs.readFileSync(jsonPath, "utf8"));
  if (exported.outputs.natural_en !== englishValue) throw new Error("JSON export mismatch");
  const txtDownloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出 TXT" }).click();
  const txtDownload = await txtDownloadPromise;
  const txtPath = path.join(evidence, "export.txt");
  await txtDownload.saveAs(txtPath);
  if (!fs.readFileSync(txtPath, "utf8").includes(englishValue)) throw new Error("TXT export mismatch");

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
  const rawCollapsedByDefault = await page.locator("details.raw").evaluate(element => !element.open);
  const result = {
    kind: "R1A_HEADLESS_PRODUCT_PATH",
    observations, inferences, unknowns,
    english_prompt: englishValue,
    clipboard_match: true,
    json_export_valid: true,
    txt_export_valid: true,
    raw_collapsed_by_default: rawCollapsedByDefault,
    layouts,
    non_loopback_requests: nonLoopback,
    passed: nonLoopback.length === 0,
  };
  if (!rawCollapsedByDefault) throw new Error("raw model response is expanded by default");
  fs.writeFileSync(path.join(evidence, "browser-result.json"), JSON.stringify(result, null, 2) + "\n");
  ledger.completed = true;
  fs.writeFileSync(ledgerPath, JSON.stringify(ledger, null, 2) + "\n");
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
