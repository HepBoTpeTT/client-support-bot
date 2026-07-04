import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "client/src"),
      "@assets": path.resolve(__dirname, "client/public"),
    },
  },
  root: path.resolve(__dirname, "client"),
  build: {
    outDir: path.resolve(__dirname, "dist"),
    emptyOutDir: true,
  },
  base: "./",
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: true,
    hmr: {
      clientPort: 80,
    },
  },
});
