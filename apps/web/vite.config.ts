import { fileURLToPath } from "node:url";
import { loadEnv } from "vite";
import { parsePublishableKey } from "@clerk/shared/keys";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const envDir = fileURLToPath(new URL("../../", import.meta.url));
  const key =
    loadEnv(mode, envDir, "VITE_").VITE_CLERK_PUBLISHABLE_KEY ||
    process.env.VITE_CLERK_PUBLISHABLE_KEY;
  if (key && !/^pk_(test|live)_/.test(key)) throw new Error("A Clerk publishable key is required.");
  if (key) parsePublishableKey(key, { fatal: true });
  return {
    envDir,
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        "/api": { target: process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000" },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      include: ["src/**/*.test.{ts,tsx}"],
      clearMocks: true,
      restoreMocks: true,
    },
  };
});
