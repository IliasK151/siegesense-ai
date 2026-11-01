import { expect, test } from "@playwright/test";
import { ensureSetup } from "./helpers";

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
