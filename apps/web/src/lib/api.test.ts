import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getHealth } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("health API boundary", () => {
  it("rejects malformed responses instead of displaying a false connected state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok" }))),
    );
    await expect(getHealth()).rejects.toThrow();
  });
  it("exposes a safe error with request correlation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("private provider detail", {
          status: 503,
          headers: { "x-request-id": "request-123" },
        }),
      ),
    );
    await expect(getHealth()).rejects.toEqual(new ApiError(503, "request-123"));
    await expect(getHealth()).rejects.not.toThrow("private provider detail");
  });
});
