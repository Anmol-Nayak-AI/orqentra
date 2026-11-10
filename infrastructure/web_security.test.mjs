import { strict as assert } from "node:assert";
import test from "node:test";
import { buildPublishableKey } from "@clerk/shared/keys";
import { configuration } from "./web_security.mjs";
const template = 'add_header Content-Security-Policy "default-src \'self\'" always;';
test("unconfigured build retains strict policy", () => assert.equal(configuration(template, ""), template));
test("configured policy binds the selected frontend host", () => {
  const result = configuration(template, buildPublishableKey("unit-test.clerk.invalid"));
  assert.ok(result.includes("https://unit-test.clerk.invalid"));
  assert.ok(result.includes("https://*.protect.clerk.com:*"));
  assert.ok(!result.includes("unsafe-eval"));
  assert.ok(!result.includes("https://*.clerk.accounts.dev"));
});
test("secret key cannot be used as a frontend public key", () => assert.throws(() => configuration(template, "sk_not_a_publishable_key")));
test("hosted builds require authentication and production rejects development keys", () => {
  const testKey = buildPublishableKey("unit-test.clerk.accounts.dev").replace(/^pk_live_/, "pk_test_");
  assert.throws(() => configuration(template, "", "staging"));
  assert.throws(() => configuration(template, testKey, "production"));
  assert.ok(configuration(template, testKey, "staging").includes("unit-test.clerk.accounts.dev"));
  assert.throws(() => configuration(template, testKey, "unknown"));
});
