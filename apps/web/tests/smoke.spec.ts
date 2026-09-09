import { expect, test, type Page } from "@playwright/test";

// Smoke: ranked list renders best-to-worst and each sort mode
// yields its distinct winner (see lib/mockListings.ts).
// The API is force-unreachable here so the test deterministically exercises
// the mock fallback (live backend data varies run to run; see below).
test("homepage ranks best-to-worst in every sort mode", async ({ page }) => {
  await page.route("**/localhost:8000/**", (route) => route.abort());
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Kodud Eestis — parimast halvimani" }),
  ).toBeVisible();

  const sortGroup = page.getByRole("group", { name: "Sorteerimine" });
  await expect(sortGroup.getByRole("button")).toHaveCount(3);
  await expect(page.getByText("3 kodu järjestatud")).toBeVisible();

  const firstCard = () => page.locator("ol > li").first().getByRole("article");

  // combined winner
  await expect(firstCard()).toContainText("Kotzebue 12, Tallinn");

  // deal winner
  await sortGroup.getByRole("button", { name: "Soodne hind" }).click();
  await expect(
    sortGroup.getByRole("button", { name: "Soodne hind" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(firstCard()).toContainText("Tähe 45, Tartu");

  // livability winner
  await sortGroup.getByRole("button", { name: "Elamiskvaliteet" }).click();
  await expect(firstCard()).toContainText("Mere pst 7, Pärnu");
});

// Filters narrow the list through shareable URL params, with a reset path
// out of the empty state (deterministic mock fallback).
test("filters narrow the list and reset", async ({ page }) => {
  await page.route("**/localhost:8000/**", (route) => route.abort());
  await page.goto("/?county=Harju+maakond");

  await expect(page.getByText("Näitan 1 / 3 kuulutusest")).toBeVisible();
  await expect(page.locator("ol > li")).toHaveCount(1);

  // impossible combo -> empty state with reset
  await page.goto("/?minLiv=101");
  await expect(page.getByText("Ükski kuulutus ei vasta filtritele.")).toBeVisible();
  await page.getByRole("button", { name: "Tühjenda filtrid" }).click();
  await expect(page.locator("ol > li")).toHaveCount(3);
});

// The map always labels its data source (live cells vs binned vs demo).
test("map shows a data-source badge", async ({ page }) => {
  await page.route("**/localhost:8000/**", (route) => route.abort());
  await page.goto("/");
  await expect(page.getByText(/Andmeallikas:/)).toBeVisible();
});

// Live-stack tests share one serial lane: they hit the same dev server +
// scoring API, and parallel contention starves page loads into timeouts.
test.describe("seeded stack", () => {
  test.describe.configure({ mode: "serial" });

  async function skipWithoutSeed(page: Page) {
    const res = await page
      .request.get("http://localhost:8000/listings?sort=combined")
      .catch(() => null);
    const api = res ? await res.json().catch(() => null) : null;
    test.skip(!api?.live || (api.items?.length ?? 0) === 0, "needs seeded stack");
  }

// C3: seeded local stack renders the live list plus real heat cells.
// Skips where no PostGIS-backed API runs (CI): the unit suites cover shapes.
test("seeded stack renders live list plus heat cells", async ({ page }) => {
  await skipWithoutSeed(page);

  await page.goto("/");
  await expect(page.getByText(/Näitan \d+ \/ \d+ kuulutusest/)).toBeVisible();
  const mapSection = page.locator('section[aria-label="Piirkondade heatmap"]');
  await expect(mapSection.getByText(/reaalajas/)).toBeVisible();

  const cellsRes = await page.request.get("http://localhost:8000/area-scores");
  const cells = await cellsRes.json();
  expect(cells.live).toBe(true);
  expect(cells.features.length).toBeGreaterThan(3);

  // sort modes reorder the live list without breaking it
  const first = () => page.locator("ol > li").first().innerText();
  const before = await first();
  await page.getByRole("group", { name: "Sorteerimine" }).getByRole("button", { name: "Soodne hind" }).click();
  await expect(page.getByText(/Näitan \d+ \/ \d+ kuulutusest/)).toBeVisible();
  expect(await first()).toContain("€");
  void before;
});

// #71: dragging the map must not snap the camera back to the default view
// once the bbox cell reload lands (the map mounts once; data swaps layers).
// Needs the seeded stack so a real bbox reload changes the heat points.
test("panning the map never snaps the camera back", async ({ page }) => {
  test.slow(); // software WebGL + deck heatmap need room under parallel load
  await skipWithoutSeed(page);

  await page.goto("/");
  const mapSection = page.locator('section[aria-label="Piirkondade heatmap"]');
  // Settle the async cell load first: a layer swap mid-drag drops the gesture.
  await expect(mapSection.getByText(/reaalajas/)).toBeVisible();
  await page.waitForTimeout(1000);
  const mapBox = page.locator(
    'section[aria-label="Piirkondade heatmap"] div[role="application"]',
  );
  await expect(mapBox).toBeVisible();
  // Raw mouse events do not scroll: bring the map into view first so the
  // drag coordinates land on the canvas, then re-measure.
  await mapBox.scrollIntoViewIfNeeded();
  await expect
    .poll(async () => mapBox.getAttribute("data-camera"), { timeout: 15000 })
    .not.toBeNull();
  const before = (await mapBox.getAttribute("data-camera")) as string;
  const box = (await mapBox.boundingBox()) as { x: number; y: number; width: number; height: number };
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  await page.mouse.move(cx + 180, cy + 60, { steps: 12 });
  await page.mouse.up();
  await page.waitForTimeout(3000); // debounce (600ms) + bbox reload + layer swap
  const after = (await mapBox.getAttribute("data-camera")) as string;
  expect(after).not.toBe(before);
  await page.waitForTimeout(2500); // a late reset would land here
  expect(await mapBox.getAttribute("data-camera")).toBe(after);
});
}); // seeded stack (live-API lane ends here)

// #70 + #76 (deterministic mock fallback): cards link to the original
// listing and show a photo, or an honest placeholder when unknown.
test("cards link out and show photos or placeholders", async ({ page }) => {
  await page.route("**/localhost:8000/**", (route) => route.abort());
  await page.goto("/");

  const card = page.getByRole("article", { name: /Kotzebue 12, Tallinn/ });
  await expect(card.getByRole("img", { name: "Foto: Kotzebue 12, Tallinn" })).toBeVisible();
  const link = card.getByRole("link", { name: /Vaata originaalkuulutust/ });
  await expect(link).toHaveAttribute("href", /pindi\.ee/);
  await expect(link).toHaveAttribute("target", "_blank");

  const noPhoto = page.getByRole("article", { name: /Tähe 45, Tartu/ });
  await expect(noPhoto.getByText("Fotot pole")).toBeVisible();
  await expect(
    noPhoto.getByRole("link", { name: /Vaata originaalkuulutust/ }),
  ).toHaveCount(0);
});

// #74 (deterministic mock fallback): the balance slider re-ranks by price
// alone at 0% quality, and a ?poi= address renders travel-time badges.
test("balance slider and POI badges re-score the list", async ({ page }) => {
  await page.route("**/localhost:8000/**", (route) => route.abort());
  await page.goto("/");

  await expect(page.locator("ol > li").first()).toContainText("Kotzebue 12, Tallinn");
  await page.getByLabel("Hinna ja kvaliteedi tasakaal").fill("0");
  await expect(page.locator("ol > li").first()).toContainText("Tähe 45, Tartu");
  await expect(page).toHaveURL(/bal=0/);
  await expect(
    page.locator("ol > li").first().getByText(/Kaalutud \d+\/100/),
  ).toBeVisible();

  await page.goto("/?poi=59.4372,24.7536,Töö");
  const card = page.getByRole("article", { name: /Kotzebue 12, Tallinn/ });
  await expect(card.getByText(/Töö · autoga ~0 min/)).toBeVisible();
});

// #84: keyboard-only flow — tab to a sort button, Enter re-ranks; map
// arrows pan the camera. (Tab order itself: sort, filters, weights, POI,
// map toggles, canvas — verified in the #84 walkthrough, no traps.)
test("keyboard operates sort and map", async ({ page }) => {
  await page.route("**/localhost:8000/**", (route) => route.abort());
  await page.goto("/");
  await page.locator("ol > li").first().waitFor({ timeout: 30000 });

  await page.keyboard.press("Tab");
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toHaveText("Elamiskvaliteet");
  await page.keyboard.press("Enter");
  await expect(page.locator(":focus")).toHaveAttribute("aria-pressed", "true");
  await expect(page).toHaveURL(/sort=livability/);

  const mapBox = page.locator(
    'section[aria-label="Piirkondade heatmap"] div[role="application"]',
  );
  await mapBox.scrollIntoViewIfNeeded();
  await page.locator("canvas.maplibregl-canvas").focus();
  const before = await mapBox.getAttribute("data-camera");
  for (let i = 0; i < 5; i++) await page.keyboard.press("ArrowRight");
  await expect
    .poll(async () => mapBox.getAttribute("data-camera"), { timeout: 10000 })
    .not.toBe(before);
});

// Live backend rendering: whatever the API serves (real import locally,
// mocks where no API runs), the page must render ranked cards with prices.
// This is environment-proof by design: no pinned winners, only structure.
test("homepage renders backend listings with prices", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Kodud Eestis — parimast halvimani" }),
  ).toBeVisible();
  await expect(page.getByText(/kodu järjestatud/)).toBeVisible();

  const firstCard = () => page.locator("ol > li").first().getByRole("article");
  await expect(firstCard()).toBeVisible();
  await expect(firstCard()).toContainText("€");

  // Switching sort mode re-ranks without breaking the list.
  const sortGroup = page.getByRole("group", { name: "Sorteerimine" });
  await sortGroup.getByRole("button", { name: "Soodne hind" }).click();
  await expect(
    sortGroup.getByRole("button", { name: "Soodne hind" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(firstCard()).toContainText("€");
});
