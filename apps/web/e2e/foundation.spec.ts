import { expect, test } from "@playwright/test";

test("web connects to real API and supports theme and route navigation", async ({ page }) => {
  await page.goto("/status");
  await expect(page.getByText("API connected")).toBeVisible();
  await expect(page.getByText(/External delivery is simulated/)).toBeVisible();
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.getByRole("button", { name: "Switch to dark theme" })).toBeVisible();
  await page.goto("/unknown");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await page.goto("/status");
  await expect(page.getByText("API connected")).toBeVisible();
});

test("protected API rejects unauthenticated requests and identity headers", async ({ request }) => {
  const response = await request.get("/api/v1/me", {
    headers: { "X-User-Id": "user_forged", "X-Role": "OWNER" },
  });
  expect(response.status()).toBe(401);
});

test("unconfigured authentication keeps protected pages closed", async ({ page }) => {
  test.skip(process.env.E2E_EXPECT_UNCONFIGURED !== "1", "Explicit unconfigured deployment check");
  await page.goto("/app");
  await expect(page.getByRole("heading", { name: "Sign-in is not configured" })).toBeVisible();
  await expect(page.getByText("Access remains restricted.", { exact: false })).toBeVisible();
});

for (const width of [375, 1280]) {
  test(`public navigation fits a ${width}px viewport`, async ({ page }) => {
    await page.setViewportSize({ width, height: 850 });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Your workforce,/ })).toBeVisible({
      timeout: 20000,
    });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await page.screenshot({ path: `/tmp/orqentra-ui-${width}.png`, fullPage: true });
    await page.getByRole("link", { name: "Get started" }).click();
    await expect(page).toHaveURL(/sign-up/);
  });
}
test("a fresh browser cannot open protected organization content", async ({ page }) => {
  await page.goto("/app");
  if (process.env.E2E_EXPECT_CONFIGURED === "1")
    await expect(page).toHaveURL(/sign-in/, { timeout: 20000 });
  else await expect(page.getByRole("heading", { name: "Sign-in is not configured" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Workspace navigation" })).toHaveCount(0);
});

for (const width of [375, 1440]) {
  test(`branded authentication is usable at ${width}px`, async ({ page }) => {
    test.skip(
      process.env.E2E_EXPECT_CONFIGURED !== "1",
      "Requires the configured development Clerk application",
    );
    await page.setViewportSize({ width, height: 960 });
    await page.goto("/sign-in");
    await expect(page.locator(".cl-signIn-root")).toBeVisible({ timeout: 25000 });
    await expect(page.getByLabel("Email address", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Back to home" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign in", exact: true })).toHaveCount(0);
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
    await page.screenshot({ path: `/tmp/orqentra-auth-${width}.png`, fullPage: true });
    if (width === 1440) {
      await page.getByRole("button", { name: "Switch to light theme" }).click();
      await expect(page.getByRole("button", { name: "Switch to dark theme" })).toBeVisible();
      await expect(page.getByLabel("Email address", { exact: true })).toBeVisible();
      await expect(page.getByLabel("Email address", { exact: true })).toHaveCSS(
        "background-color",
        "rgb(247, 249, 248)",
      );
      await expect(page.locator(".auth-clerk-primary")).toHaveCSS(
        "background-color",
        "rgb(34, 105, 79)",
      );
      await page.screenshot({ path: "/tmp/orqentra-auth-light.png", fullPage: true });
    }
  });
}
