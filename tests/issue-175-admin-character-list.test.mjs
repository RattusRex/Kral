import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const adminPage = source.slice(
  source.indexOf("function AdminPage()"),
  source.indexOf("function AdminCharacterPage()")
);
const adminCharacterPage = source.slice(
  source.indexOf("function AdminCharacterPage()"),
  source.indexOf("function AdminGrantLogsPage()")
);

test("admin character list omits calendar details", () => {
  assert.doesNotMatch(adminPage, /Дата сбора/);
  assert.doesNotMatch(adminPage, /Свободные дни/);
  assert.doesNotMatch(adminPage, /character\.game_created_at/);
  assert.doesNotMatch(adminPage, /character\.free_days/);
});

test("admin character sheet keeps calendar details", () => {
  assert.match(adminCharacterPage, /Дата создания/);
  assert.match(adminCharacterPage, /Свободные дни/);
  assert.match(adminCharacterPage, /character\.game_created_at/);
  assert.match(adminCharacterPage, /character\.free_days/);
});
