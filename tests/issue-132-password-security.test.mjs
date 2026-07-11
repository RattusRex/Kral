import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const registerSource = source.slice(
  source.indexOf("function Register()"),
  source.indexOf("function AuthPanel("),
);

test("registration password is only submitted to the registration endpoint", () => {
  assert.match(registerSource, /api\.post\("\/users", form\)/);
  assert.doesNotMatch(registerSource, /localStorage\.(?:setItem|getItem)\([^)]*password/i);
  assert.doesNotMatch(registerSource, /sessionStorage\.(?:setItem|getItem)\([^)]*password/i);
  assert.doesNotMatch(registerSource, /document\.cookie/);
  assert.doesNotMatch(registerSource, /console\./);
  assert.doesNotMatch(registerSource, /response[^\n]*(?:password|form)/i);
});

test("registration form exposes the server password policy to users", () => {
  assert.match(registerSource, /minLength=\{12\}/);
  assert.match(registerSource, /maxLength=\{72\}/);
  assert.match(registerSource, /autoComplete="new-password"/);
  assert.match(registerSource, /Пароль должен содержать/);
  assert.match(registerSource, /requestError\.response\?\.data\?\.detail/);
});
