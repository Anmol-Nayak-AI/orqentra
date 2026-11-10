import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Separate entry and empty env prefix: no Clerk, API client or backend credentials in this preview.
export default defineConfig({
  plugins: [react()],
  envDir: false,
  envPrefix: "ORQENTRA_PUBLIC_DEMO_",
  build: { outDir: "dist-demo", rollupOptions: { input: "demo.html" } },
});
