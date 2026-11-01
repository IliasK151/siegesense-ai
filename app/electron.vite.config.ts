import { resolve } from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "electron-vite";

const shared = { "@shared": resolve(import.meta.dirname, "src/shared") };

export default defineConfig({
  main: { resolve: { alias: shared } },
  preload: { resolve: { alias: shared } },
  renderer: {
    root: resolve(import.meta.dirname, "src/renderer"),
    resolve: { alias: { ...shared, "@": resolve(import.meta.dirname, "src/renderer/src") } },
    plugins: [react(), tailwindcss()],
  },
});
