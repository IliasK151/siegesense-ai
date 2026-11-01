import { expect, type Page } from "@playwright/test";

export const appUrl = () => `/?port=${process.env.E2E_ENGINE_PORT}&token=e2e`;

/** Opens the app and completes first-run setup if it hasn't been done yet. */
export async function ensureSetup(page: Page) {
  await page.goto(appUrl());
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
