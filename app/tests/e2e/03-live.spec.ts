import { expect, test } from "@playwright/test";
import { ensureSetup } from "./helpers";

test("live mode detects rounds and death clip", async ({ page }) => {
  test.setTimeout(90_000);
  await ensureSetup(page);
  await page.getByRole("button", { name: "Live", exact: true }).click();
  await expect(page.getByTestId("live-checklist")).toBeVisible();
  await page.getByRole("button", { name: "Start Live Mode" }).click();
  await expect(page.getByText("LIVE", { exact: true })).toBeVisible({ timeout: 20_000 });

  // The engine is "watching" a replayed two-round match through the real HUD reader.
  const card = page.getByTestId("death-card");
  await expect(card).toBeVisible({ timeout: 40_000 });
  await expect(card.getByText(/Killed by Bandit.X/)).toBeVisible();
  await expect(card.locator("video")).toHaveAttribute("src", /^clip:\/\/media\/.+-r1-death\.mp4$/);
  await expect(page.getByTestId("event-feed").getByText(/You eliminated Thermite_1 — first blood/)).toBeVisible();
  await expect(page.getByTestId("round-2")).toContainText("W", { timeout: 30_000 });
  await page.waitForTimeout(300);
  await page.screenshot({ path: "test-results/07-live.png" });

  await page.getByRole("button", { name: "Stop" }).click();
  const summary = page.getByTestId("match-summary");
  await expect(summary.getByTestId("stat-rounds")).toHaveText("1–1");
  await expect(summary.getByTestId("stat-deaths")).toHaveText("1");
  await expect(summary.getByTestId("stat-kills")).toHaveText("1");
  await page.waitForTimeout(300);
  await page.screenshot({ path: "test-results/08-live-summary.png" });
});
