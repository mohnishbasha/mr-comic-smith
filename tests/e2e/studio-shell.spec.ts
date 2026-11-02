import { expect, test } from "@playwright/test";

test("smoke_studio_shell_loads_in_chromium", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("link", { name: "mr-comic-smith" })).toBeVisible();
  await expect(page.getByRole("contentinfo")).toContainText(/Version \d+\.\d+\.\d+/);
  const health = await page.request.get("/v1/healthz");
  const body = (await health.json()) as { status: string; version: string };
  await expect(page.getByText(`Version ${body.version}`)).toBeVisible();
});

test("e2e_US002_empty_home_prompts_for_story_idea", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Start with a story idea, a photo, or both.")).toBeVisible();
  await expect(page.getByRole("button", { name: "New project" })).toBeDisabled();
});

test("e2e_studio_client_route_and_theme_toggle", async ({ page }) => {
  await page.goto("/p/demo/strips");
  await expect(page.getByRole("heading", { level: 1, name: "Strips" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Strips" })).toHaveAttribute("aria-current", "page");
  await page.getByRole("button", { name: "Dark" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});
