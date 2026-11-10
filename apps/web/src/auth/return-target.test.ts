import { beforeEach, expect, it } from "vitest";
import { authReturnTarget, rememberAuthTarget, clearAuthTarget } from "./return-target";
beforeEach(() => sessionStorage.clear());
it("preserves an internal invitation fragment through login and can clear it", () => {
  rememberAuthTarget("/app/join#synthetic-invitation");
  expect(authReturnTarget()).toBe("/app/join#synthetic-invitation");
  clearAuthTarget();
  expect(authReturnTarget()).toBe("/app");
});
it.each([
  "https://example.invalid",
  "//example.invalid",
  "/app\\evil",
  "/application",
  "/app/\ninvalid",
])("rejects an unsafe return destination %s", (path) => {
  rememberAuthTarget(path);
  expect(authReturnTarget()).toBe("/app");
});
