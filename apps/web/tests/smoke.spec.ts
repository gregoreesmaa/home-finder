import { expect, test } from "@playwright/test";

// Smoke: ranked list renders best-to-worst and each sort mode
// yields its distinct winner (see lib/mockListings.ts).
test("homepage ranks best-to-worst in every sort mode", async ({ page }) => {
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
