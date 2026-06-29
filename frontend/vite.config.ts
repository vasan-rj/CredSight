import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // Proxy API calls to the CredSight backend (MCP/decisioning service) in dev.
    proxy: {
      "/api":     { target: "http://localhost:8000", changeOrigin: true },
      "/samples": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
