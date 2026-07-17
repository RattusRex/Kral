import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const profilesPage = source.slice(
  source.indexOf("function PlayerProfilesPage()"),
  source.indexOf("function AdminPage()"),
);

test("player profiles let administrators add and remove openers", () => {
  assert.match(profilesPage, /api\.post<KarmaPurchase>\(`\/admin\/users\/\$\{profileId\}\/openers`/);
  assert.match(profilesPage, /api\.delete\(`\/admin\/users\/\$\{profileId\}\/openers\/\$\{openerId\}`/);
  assert.match(profilesPage, /Добавить открывашку/);
  assert.match(profilesPage, /Удалить открывашку/);
});

test("successful opener changes update the profile immediately", () => {
  assert.match(profilesPage, /setProfiles\(\(current\) =>/);
  assert.match(profilesPage, /openers: \[created, \.\.\.profile\.openers\]/);
  assert.match(profilesPage, /profile\.openers\.filter\(\(opener\) => opener\.id !== openerId\)/);
});
