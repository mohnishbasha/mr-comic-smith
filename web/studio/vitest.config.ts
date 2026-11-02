import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    // Node 25+ ships a global localStorage that shadows jsdom's when no file is configured.
    execArgv: ["--no-experimental-webstorage"],
    setupFiles: ["tests/setup.ts"],
    include: ["tests/**/*.test.ts", "tests/**/*.test.tsx"],
    restoreMocks: true,
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts", "src/**/*.tsx"],
      exclude: ["src/main.tsx"],
      reporter: ["text", "json-summary"],
      // Floors from the typescript section of .coverage-thresholds.toml.
      thresholds: {
        "src/stores/**": { lines: 85 },
        "src/components/**": { lines: 75 },
      },
    },
  },
});
