import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const characterPage = source.slice(
  source.indexOf("function CharacterPage()"),
  source.indexOf("function CharacterFormPage()")
);
const karmaShopPage = source.slice(
  source.indexOf("function KarmaShopPage()"),
  source.indexOf("function LeaderboardPage()")
);

test("character sheet always displays the life status", () => {
  assert.match(characterPage, /Статус/);
  assert.match(characterPage, /character\.is_dead \? "Мёртв" : "Жив"/);
});

test("karma shop only offers eligible dead characters for resurrection", () => {
  assert.match(karmaShopPage, /resurrectionCharacters = characters\.filter/);
  assert.match(karmaShopPage, /character\.is_dead && character\.level <= 10/);
  assert.match(karmaShopPage, /resurrectionCost/);
  assert.match(karmaShopPage, /user\?\.karma \?\? 0/);
  assert.match(karmaShopPage, /Недостаточно кармы для воскрешения/);
});
