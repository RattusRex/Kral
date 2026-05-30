import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  root: "app/frontend",
  plugins: [react()],
  resolve: {
    alias: {
      "/src": fileURLToPath(new URL("./app/src", import.meta.url))
    }
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000"
    }
  },
  build: {
    outDir: "../../dist",
    emptyOutDir: true
  }
});
