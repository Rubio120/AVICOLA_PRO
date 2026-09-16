import { z } from "zod";


const readyResponseSchema = z.object({
  status: z.literal("ready"),
  database: z.literal("available"),
});

export type BackendHealth = { available: true } | { available: false };

export async function getBackendHealth(baseUrl: string): Promise<BackendHealth> {
  try {
    const response = await fetch(`${baseUrl.replace(/\/$/, "")}/health/ready`, {
      cache: "no-store",
      signal: AbortSignal.timeout(2_000),
    });
    if (!response.ok) {
      return { available: false };
    }
    readyResponseSchema.parse(await response.json());
    return { available: true };
  } catch {
    return { available: false };
  }
}
