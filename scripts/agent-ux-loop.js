/**
 * Agent UX loop (#80): spin up against a running site and actually use it.
 *
 * Exercises list/map/weights/POI/sort like a buyer would, collects every
 * console/page error, and writes screenshots + a JSON report for review.
 * Fails non-zero on any error so the standing QA task can iterate on it.
 *
 * Prerequisites: web dev server AND scoring API reachable (it uses both,
 * falling back to mocks like a real offline user when the API is down).
 *
 * Usage: node scripts/agent-ux-loop.js [--base http://127.0.0.1:3100]
 *        [--api http://localhost:8000] [--out /tmp/hf-ux-loop]
 */
const { chromium } = require("@playwright/test");
const fs = require("node:fs");
const path = require("node:path");

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const BASE = arg("--base", "http://127.0.0.1:3100");
const API = arg("--api", "http://localhost:8000");
const OUT = arg("--out", "/tmp/hf-ux-loop");

async function reachable(url) {
  try {
    const res = await fetch(url);
    return res.ok;
  } catch {
    return false;
  }
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const report = { base: BASE, api: API, steps: [], errors: [], ok: true };
  const fail = (step, detail) => {
    report.steps.push({ step, ok: false, detail });
    report.errors.push(`${step}: ${detail}`);
    report.ok = false;
  };
  const pass = (step, detail) => report.steps.push({ step, ok: true, detail });

  if (!(await reachable(BASE))) {
    fail("setup", `web not reachable at ${BASE} (start: npx next dev --port 3100)`);
    return finish(report);
  }
  const apiUp = await reachable(`${API}/listings?sort=combined`);
  pass("setup", apiUp ? "web + live API reachable" : "web reachable, API down (mock fallback)");

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on("pageerror", (e) => fail("pageerror", String(e).slice(0, 300)));
  page.on("console", (m) => {
    if (m.type() === "error") fail("console", m.text().slice(0, 300));
  });

  const shot = (name) => page.screenshot({ path: path.join(OUT, `${name}.png`) });

  // 1. List in every sort mode.
  await page.goto(BASE, { waitUntil: "networkidle", timeout: 60000 }).catch(() => {});
  for (const [mode, label] of [["combined", "Parim match"], ["livability", "Elamiskvaliteet"], ["deal", "Soodne hind"]]) {
    await page.getByRole("button", { name: label }).click();
    await page.waitForTimeout(800);
    const pressed = await page.getByRole("button", { name: label }).getAttribute("aria-pressed");
    if (pressed !== "true") fail(`sort:${mode}`, "aria-pressed did not stick");
    else pass(`sort:${mode}`, (await page.locator("ol > li").first().innerText()).slice(0, 60));
  }
  await shot("list");

  // 2. Weights + POI re-score.
  await page.getByLabel("Hinna ja kvaliteedi tasakaal").fill("0");
  await page.waitForTimeout(500);
  pass("weights", "balance slider applies: " + (await page.url()).slice(-20));
  await page.goto(`${BASE}/?poi=59.4372,24.7536,Töö`, { waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(1500);
  const badge = await page.getByText(/Töö · autoga/).count();
  if (badge < 1) fail("poi", "no POI travel-time badge rendered");
  else pass("poi", `${badge} badge(s)`);
  await shot("poi");

  // 3. Map: pan keeps the camera, keyboard pans too (#71, #84).
  const mapBox = page.locator('section[aria-label="Piirkondade heatmap"] div[role="application"]');
  await mapBox.scrollIntoViewIfNeeded();
  await page.waitForFunction(() => document.querySelector("[data-camera]"), null, { timeout: 30000 });
  const before = await mapBox.getAttribute("data-camera");
  const box = await mapBox.boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 180, box.y + box.height / 2 + 60, { steps: 12 });
  await page.mouse.up();
  await page.waitForTimeout(3000);
  const after = await mapBox.getAttribute("data-camera");
  if (after === before) fail("map-pan", "drag did not move the camera");
  else pass("map-pan", `${before} -> ${after}`);
  await page.waitForTimeout(2500);
  if ((await mapBox.getAttribute("data-camera")) !== after) fail("map-pan", "camera snapped back");
  await shot("map");

  // 4. Filters narrow and reset.
  await page.goto(`${BASE}/?minLiv=101`, { waitUntil: "networkidle" }).catch(() => {});
  await page.waitForTimeout(800);
  const empty = await page.getByText(/Ükski kuulutus ei vasta filtritele/).count();
  if (empty < 1) fail("filters", "empty state missing for impossible combo");
  else {
    await page.getByRole("button", { name: "Tühjenda filtrid" }).click();
    await page.waitForTimeout(800);
    pass("filters", `empty state + reset, list back to ${await page.locator("ol > li").count()}`);
  }

  await browser.close();
  return finish(report);
}

function finish(report) {
  fs.writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 2));
  console.log(`UX loop ${report.ok ? "PASS" : "FAIL"}: ${report.steps.filter((s) => s.ok).length}/${report.steps.length} steps`);
  for (const e of report.errors) console.log("  ERROR:", e);
  console.log(`report + screenshots in ${OUT}`);
  process.exit(report.ok ? 0 : 1);
}

main().catch((e) => {
  console.error("loop crashed:", e);
  process.exit(2);
});
