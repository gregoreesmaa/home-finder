import { expect, test } from "@playwright/test";

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
