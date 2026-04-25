import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// During dev (`pnpm dev`) we proxy /api → the FastAPI server so the
// React app and the Python backend can run independently.
// In production the Python wheel ships dist/ and FastAPI mounts it
// directly — no proxy needed at runtime.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8090",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
  },
});
