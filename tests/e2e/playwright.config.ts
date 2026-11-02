import { defineConfig, devices } from "@playwright/test";

const PORT = 7399;

export default defineConfig({
  testDir: ".",
  testMatch: "*.spec.ts",
  fullyParallel: true,
  forbidOnly: Boolean(process.env["CI"]),
  retries: process.env["CI"] ? 1 : 0,
  reporter: process.env["CI"] ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://127.0.0.1:${String(PORT)}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // Build the Studio into the bundled static dir first (`make studio-build`), then serve it.
  webServer: {
    command: `uv run mr-comic-smith studio --no-browser --port ${String(PORT)}`,
    cwd: "../..",
    url: `http://127.0.0.1:${String(PORT)}/v1/healthz`,
    reuseExistingServer: !process.env["CI"],
    timeout: 60_000,
  },
});
