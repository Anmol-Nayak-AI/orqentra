import { z } from "zod";
import type { HealthResponse } from "@orqentra/contracts";

const healthSchema = z.object({
  status: z.literal("ok"),
  service: z.literal("orqentra-api"),
  checkpoint: z.literal("2A"),
}) satisfies z.ZodType<HealthResponse>;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly correlationId: string | null,
  ) {
    super("The API could not complete this request.");
    this.name = "ApiError";
  }
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch("/api/v1/health", {
    signal,
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new ApiError(response.status, response.headers.get("x-request-id"));
  return healthSchema.parse(await response.json());
}
