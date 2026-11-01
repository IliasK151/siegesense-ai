import { expect, type Page, test } from "@playwright/test";

const url = () => `/?port=${process.env.E2E_ENGINE_PORT}&token=e2e`;

async function ensureSetup(page: Page) {
  await page.goto(url());
  const wizard = page.getByTestId("setup-wizard");
  const home = page.getByText(/Let's get better/);
  await expect(wizard.or(home)).toBeVisible();
  if (!(await wizard.isVisible())) return;
  await page.getByRole("button", { name: "Get started" }).click();
  await page.getByLabel("In-game name").fill("Ash.Main");
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Import" }).click();
  await page.getByLabel("Mouse DPI").fill("800");
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Skip for now" }).click();
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Skip HUD check" }).click();
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(home).toBeVisible();
}

test("warm-up counts flicks and shows summary", async ({ page }) => {
  test.setTimeout(60_000);
  await ensureSetup(page);
  await page.getByRole("button", { name: "Warm-up", exact: true }).click();
  await expect(page.getByText("Estimated — calibrate in Settings")).toBeVisible();
  await page.getByRole("button", { name: "Start warm-up" }).click();
  await expect(page.getByText("LIVE", { exact: true })).toBeVisible();

  // The engine replays 12 recorded flicks (5 overshoots) through the real detector.
  await expect(page.getByTestId("tile-flicks")).toHaveText("12", { timeout: 25_000 });
  await expect(page.getByTestId("tile-overshoot")).toHaveText("42%");
  await expect(page.getByTestId("flick-chart")).toBeVisible();
  await page.waitForTimeout(400);
  await page.screenshot({ path: "test-results/05-warmup-live.png" });

  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.getByTestId("summary-score")).toHaveText("58");
  await expect(page.getByText("Overshooting your flicks")).toBeVisible();
  await page.waitForTimeout(300);
  await page.screenshot({ path: "test-results/06-warmup-summary.png" });
});
