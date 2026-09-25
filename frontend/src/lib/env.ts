import { z } from "zod";


const serverEnvSchema = z.object({
  BACKEND_INTERNAL_URL: z.url(),
});

export type ServerEnv = z.infer<typeof serverEnvSchema>;

export function parseServerEnv(environment: Record<string, string | undefined>): ServerEnv {
  return serverEnvSchema.parse(environment);
}

export function getServerEnv(): ServerEnv {
  return parseServerEnv({ BACKEND_INTERNAL_URL: process.env.BACKEND_INTERNAL_URL });
}
