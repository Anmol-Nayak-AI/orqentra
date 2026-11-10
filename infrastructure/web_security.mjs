import { readFileSync, writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { parsePublishableKey } from "@clerk/shared/keys";

export function configuration(template, key, environment = "development") {
  if (!["development", "test", "staging", "production"].includes(environment)) throw new Error("Unknown deployment environment");
  if (["staging", "production"].includes(environment) && !key) throw new Error("Hosted builds require configured authentication");
  if (environment === "production" && !key?.startsWith("pk_live_")) throw new Error("Production builds require a live Clerk publishable key");
  if (!key) return template;
  if (!key.startsWith("pk_test_") && !key.startsWith("pk_live_")) throw new Error("A Clerk publishable key is required");
  const parsed = parsePublishableKey(key, { fatal: true });
  if (!parsed || !/^[a-z0-9.-]+$/i.test(parsed.frontendApi)) throw new Error("Invalid Clerk frontend host");
  const origin = `https://${parsed.frontendApi}`;
  const policy = [
    "default-src 'self'", `script-src 'self' ${origin} https://challenges.cloudflare.com https://*.protect.clerk.com`,
    `connect-src 'self' ${origin} https://*.protect.clerk.com:* https://clerk-telemetry.com https://*.clerk-telemetry.com`,
    "img-src 'self' data: https://img.clerk.com", "style-src 'self' 'unsafe-inline'", "worker-src 'self' blob:",
    `frame-src 'self' ${origin} https://challenges.cloudflare.com https://*.protect.clerk.com`,
    "font-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "base-uri 'self'", "form-action 'self'",
  ].join("; ");
  return template.replace(/add_header Content-Security-Policy "[^"]*" always;/,
    `add_header Content-Security-Policy "${policy}" always;`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  writeFileSync(process.argv[3], configuration(readFileSync(process.argv[2], "utf8"), process.env.VITE_CLERK_PUBLISHABLE_KEY, process.env.ORQENTRA_DEPLOYMENT_ENV));
}
