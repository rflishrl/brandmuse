import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

/**
 * Injects <link rel="preload" as="font" ...> for the hashed Latin Inter WOFF2 asset
 * during production builds so the browser fetches the font in parallel with CSS.
 */
function preloadLatinInterFont(): Plugin {
  return {
    name: "preload-latin-inter-font",
    apply: "build",
    transformIndexHtml: {
      order: "post",
      handler(_html, ctx) {
        if (!ctx.bundle) return;
        const fontAsset = Object.values(ctx.bundle).find(
          (item) =>
            item.type === "asset" &&
            item.fileName.includes("inter-latin-wght-normal") &&
            item.fileName.endsWith(".woff2")
        );
        if (!fontAsset) return;
        return [
          {
            tag: "link",
            attrs: {
              rel: "preload",
              as: "font",
              type: "font/woff2",
              href: `/${fontAsset.fileName}`,
              crossorigin: "",
            },
            injectTo: "head",
          },
        ];
      },
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), preloadLatinInterFont()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    sourcemap: "hidden", // Generates .map files without exposing sourceMappingURL comment in production
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router"],
          "vendor-query": ["@tanstack/react-query"],
        },
      },
    },
  },
});
