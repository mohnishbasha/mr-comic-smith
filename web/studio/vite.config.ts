import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const BACKEND = "http://127.0.0.1:7351";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/v1": BACKEND,
      "/healthz": BACKEND,
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2022",
    sourcemap: false,
  },
});
