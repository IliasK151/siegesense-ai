import { expect, test } from "@playwright/test";

const url = () => `/?port=${process.env.E2E_ENGINE_PORT}&token=e2e`;

test("first run completes setup and shows home", async ({ page }) => {
  await page.goto(url());
  await expect(page.getByTestId("setup-wizard")).toBeVisible();
  await page.screenshot({ path: "test-results/01-welcome.png" });
  await page.getByRole("button", { name: "Get started" }).click();
  await page.getByLabel("In-game name").fill("Ash.Main");
  await page.getByRole("button", { name: "Next" }).click();

  await expect(page.getByText("Found your Siege settings")).toBeVisible();
  await expect(page.getByText(process.env.E2E_SETTINGS_PATH!)).toBeVisible();
  await page.getByRole("button", { name: "Import" }).click();
  await expect(page.getByLabel("Horizontal sensitivity")).toHaveValue("12");
  await page.getByLabel("Mouse DPI").fill("800");
  await page.waitForTimeout(300);
  await page.screenshot({ path: "test-results/02-sensitivity.png" });
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Skip for now" }).click();

  await expect(page.getByText(/Borderless is perfect/)).toBeVisible();
  await page.screenshot({ path: "test-results/03-display.png" });
  await page.getByRole("button", { name: "Next" }).click();
  await page.getByRole("button", { name: "Skip HUD check" }).click();
  await page.getByRole("button", { name: "Save profile" }).click();

  await expect(page.getByText("Let's get better, Ash.Main.")).toBeVisible();
  await expect(page.getByTestId("edpi")).toHaveText("9600");
  await expect(page.getByTestId("status-card").getByTestId("status-light")).toHaveCount(6);
  await page.waitForTimeout(400);
  await page.screenshot({ path: "test-results/04-home.png" });

  await page.reload();
  await expect(page.getByText("Let's get better, Ash.Main.")).toBeVisible();
});
