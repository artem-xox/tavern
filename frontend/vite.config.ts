import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/ws": { target: "http://127.0.0.1:8000", ws: true },
      "/api": { target: "http://127.0.0.1:8000" },
      "/health": { target: "http://127.0.0.1:8000" },
    },
  },
});
