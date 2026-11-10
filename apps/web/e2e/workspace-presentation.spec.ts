import { test, expect } from "@playwright/test";
import { pathToFileURL } from "node:url";
import path from "node:path";
for (const [view, width] of [
  ["directory", 1440],
  ["directory", 375],
  ["overview", 1440],
  ["settings", 1440],
  ["audit", 1440],
  ["audit", 375],
] as const) {
  test(`synthetic workspace presentation: ${view} at ${width}px`, async ({ page }) => {
    test.skip(
      !process.env.E2E_WORKSPACE_PREVIEW_DIR,
      "Explicit static presentation preview; not live authentication evidence",
    );
    await page.setViewportSize({ width, height: 960 });
    await page.goto(
      pathToFileURL(path.join(process.env.E2E_WORKSPACE_PREVIEW_DIR!, `${view}.html`)).href,
    );
    await expect(page.getByText("Design preview · synthetic data")).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await page.screenshot({ path: `/tmp/orqentra-workspace-${view}-${width}.png`, fullPage: true });
  });
}
