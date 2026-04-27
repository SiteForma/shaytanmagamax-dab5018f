import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

const apiProxyTarget = (
  process.env.VITE_DEV_PROXY_TARGET ??
  process.env.VITE_API_BASE_URL?.replace(/\/api\/?$/, "") ??
  "http://127.0.0.1:8001"
);

// https://vitejs.dev/config/
export default defineConfig(() => ({
  server: {
    host: "::",
    port: 8090,
    hmr: {
      overlay: false,
    },
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime", "@tanstack/react-query", "@tanstack/query-core"],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return;
          }
          if (id.includes("react-router")) {
            return "router";
          }
          if (id.includes("@tanstack")) {
            return "query";
          }
          if (id.includes("recharts")) {
            return "charts";
          }
          if (id.includes("@radix-ui")) {
            return "radix";
          }
          if (id.includes("lucide-react")) {
            return "icons";
          }
          if (id.includes("react") || id.includes("scheduler")) {
            return "react-vendor";
          }
          return "vendor";
        },
      },
    },
  },
}));
