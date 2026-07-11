import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";

const apiSource = fs.readFileSync("app/src/api.ts", "utf8");
const mainSource = fs.readFileSync("app/src/main.tsx", "utf8");

test("expired API sessions store a clear login notice before logging out", () => {
  assert.match(apiSource, /error\.response\?\.data\?\.detail\?\.code === "token_expired"/);
  assert.match(apiSource, /sessionStorage\.setItem\(AUTH_NOTICE_KEY, SESSION_EXPIRED_MESSAGE\)/);
  assert.match(apiSource, /window\.dispatchEvent\(new Event\("auth:logout"\)\)/);
});

test("the login page consumes and displays the expired-session notice", () => {
  assert.match(mainSource, /sessionStorage\.getItem\(AUTH_NOTICE_KEY\)/);
  assert.match(mainSource, /sessionStorage\.removeItem\(AUTH_NOTICE_KEY\)/);
  assert.match(apiSource, /SESSION_EXPIRED_MESSAGE = "Сессия истекла\. Войдите снова\."/);
  assert.match(mainSource, /\{notice && <p className="text-sm text-amber-200">\{notice\}<\/p>\}/);
});
