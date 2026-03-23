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
    port: 5173,
    proxy: {                                                                       //
      "/api": { target: "http://backend:8000", changeOrigin: true },               //  Для развёртки в Docker
      "/widget.js": { target: "http://backend:8000", changeOrigin: true },         //
      "/chat-widget": { target: "http://backend:8000", changeOrigin: true },       //
    }, 
    // proxy: {
    //   "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    //   "/widget.js": { target: "http://127.0.0.1:8000", changeOrigin: true },
    //   "/chat-widget": { target: "http://127.0.0.1:8000", changeOrigin: true },
    // },
  },
});
