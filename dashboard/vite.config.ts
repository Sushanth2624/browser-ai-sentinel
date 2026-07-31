import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api to the Go daemon so the browser never needs CORS headers — the daemon stays exactly
// as loopback-scoped as every other Phase 1-3 service (see the plan's "no CORS" design note).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api": "http://127.0.0.1:8090",
    },
  },
});
