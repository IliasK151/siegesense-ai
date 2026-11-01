// Renderer-only dev server (no Electron), used by the end-to-end tests.
import { resolve } from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  root: resolve(__dirname, "src/renderer"),
  resolve: {
    alias: {
      "@shared": resolve(__dirname, "src/shared"),
      "@": resolve(__dirname, "src/renderer/src"),
    },
  },
  plugins: [react(), tailwindcss()],
  server: { port: 5199, strictPort: true },
});
