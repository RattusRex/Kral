import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const karmaShopPage = source.slice(
  source.indexOf("function KarmaShopPage()"),
  source.indexOf("function LeaderboardPage()"),
);

test("karma shop loads and renders the preset opener catalog", () => {
  assert.match(karmaShopPage, /api\.get<KarmaOpener\[]>\("\/karma-shop\/openers"\)/);
  assert.match(karmaShopPage, /<option value="">Выберите открывашку<\/option>/);
  assert.match(karmaShopPage, /openers\.map\(\(opener\) =>/);
  assert.match(karmaShopPage, /opener\.name.*opener\.cost.*кармы/s);
});

test("preset cost is automatic while a custom opener keeps manual fields", () => {
  assert.match(karmaShopPage, /value="custom">Нестандартная открывашка<\/option>/);
  assert.match(karmaShopPage, /selectedOpener === "custom"/);
  assert.match(karmaShopPage, /customOpenerName/);
  assert.match(karmaShopPage, /customOpenerCost/);
  assert.match(karmaShopPage, /selectedOpenerDefinition\?\.cost/);
});

test("openers are granted immediately without approval guidance", () => {
  assert.doesNotMatch(karmaShopPage, /selectedOpenerDefinition\?\.note/);
  assert.doesNotMatch(karmaShopPage, /проверяются администрацией или мастером/);
});
