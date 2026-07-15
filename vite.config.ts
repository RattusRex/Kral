import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { loadEnv as loadProjectEnv } from "./scripts/load-env.mjs";

loadProjectEnv(fileURLToPath(new URL(".", import.meta.url)));

const apiTarget = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  root: "app/frontend",
  plugins: [react()],
  resolve: {
    alias: {
      "/src": fileURLToPath(new URL("./app/src", import.meta.url))
    }
  },
  server: {
    host: true,
    allowedHosts: 'all',
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        ws: true
      }
    }
  },
  build: {
    outDir: "../../dist",
    emptyOutDir: true
  }
});
