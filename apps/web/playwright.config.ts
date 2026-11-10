import { defineConfig, devices } from "@playwright/test";

// Test an existing container deployment without occupying host dev-server ports.
const existingBaseURL = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: "list",
  use: { baseURL: existingBaseURL ?? "http://127.0.0.1:5173", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: existingBaseURL
    ? undefined
    : [
        {
          command:
            "uv run --project ../.. --package orqentra-api uvicorn orqentra.main:app --host 127.0.0.1 --port 8000 --no-access-log",
          url: "http://127.0.0.1:8000/api/v1/health",
          reuseExistingServer: false,
        },
        { command: "npm run dev", url: "http://127.0.0.1:5173", reuseExistingServer: false },
      ],
});
