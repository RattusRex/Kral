import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const adminMenu = source.slice(
  source.indexOf("function AdminMenuPage()"),
  source.indexOf("function ProjectSettingsPage()"),
);
const profilesPage = source.slice(
  source.indexOf("function PlayerProfilesPage()"),
  source.indexOf("function AdminPage()"),
);

test("admin menu and routes expose project player profiles", () => {
  assert.match(adminMenu, /to="\/admin\/player-profiles"[^>]*>[\s\S]*?Профили игроков<\/Link>/);
  assert.match(source, /path="\/admin\/player-profiles" element=\{<AdminProtected>/);
});

test("player profiles support search and render karma, characters, and openers", () => {
  assert.match(profilesPage, /api\.get<PlayerProfile\[]>\("\/admin\/player-profiles"/);
  assert.match(profilesPage, /placeholder="Поиск по логину или электронной почте"/);
  assert.match(profilesPage, /profile\.karma/);
  assert.match(profilesPage, /profile\.characters\.map/);
  assert.match(profilesPage, /profile\.openers\.map/);
  assert.match(profilesPage, /Открывашек пока нет/);
});

test("legacy approval wording is absent from the opener catalog UI", () => {
  assert.doesNotMatch(source, /Условия применения проверяются администрацией или мастером/);
});
