import { expect, test } from "@playwright/test";

for (const width of [390, 1440]) {
  test(`free public preview is usable and keeps interactions local at ${width}px`, async ({
    page,
  }, info) => {
    test.skip(!process.env.E2E_DEMO_URL, "Separate static preview deployment check only");
    const requests: string[] = [];
    const errors: string[] = [];
    page.on("request", (request) => requests.push(request.url()));
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(process.env.E2E_DEMO_URL!);
    await expect(page.getByText("INTERACTIVE PREVIEW", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "A clear view of your workforce." }),
    ).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
      width,
    );
    await page.screenshot({ path: info.outputPath("public-preview.png"), fullPage: true });
    await page.getByRole("button", { name: "Chat", exact: true }).click();
    await page.getByRole("button", { name: "How does RAG chat work?" }).click();
    await expect(page.getByRole("log")).toContainText("PostgreSQL/pgvector");
    await expect(page.getByRole("log")).toContainText("scripted answer");
    await page.getByLabel("Choose sample organization").selectOption("Meridian Studio");
    await expect(page.getByRole("heading", { name: "Start with a question." })).toBeVisible();
    await page.getByRole("button", { name: "Knowledge", exact: true }).click();
    await page.getByLabel("Search sample knowledge").fill("row-level");
    await expect(
      page.getByText("Organization access and isolation", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("Orqentra product guide", { exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Tasks & reviews", exact: true }).click();
    await page.getByRole("button", { name: "Mark preview reviewed" }).click();
    await expect(
      page.getByRole("button", { name: "Preview reviewed", exact: true }),
    ).toBeDisabled();
    await page.getByRole("button", { name: "Members", exact: true }).click();
    await page.getByLabel("Search fictional members").fill("Jordan");
    await expect(page.getByText("Jordan Patel", { exact: true })).toBeVisible();
    await expect(page.getByText("Avery Chen", { exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Release status", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Commercial acceptance still pending" }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Commercial acceptance still pending" }),
    ).toBeVisible();
    expect(errors).toEqual([]);
    expect(requests.filter((url) => new URL(url).pathname.startsWith("/api/"))).toEqual([]);
    expect(
      requests.every((url) => new URL(url).origin === new URL(process.env.E2E_DEMO_URL!).origin),
    ).toBe(true);
  });
}
