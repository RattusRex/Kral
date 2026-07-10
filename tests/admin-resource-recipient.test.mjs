import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const adminPage = source.slice(
  source.indexOf("function AdminPage()"),
  source.indexOf("function AdminCharacterPage()")
);

test("admin resource forms do not automatically select a recipient", () => {
  assert.doesNotMatch(adminPage, /items\[0\]\?\.id/);
});

test("admin resource forms require an explicit recipient selection", () => {
  assert.match(adminPage, /<option value="">Выберите персонажа<\/option>/);
  assert.match(adminPage, /<option value="">Выберите пользователя<\/option>/);
  assert.equal(
    adminPage.match(/disabled=\{!selected \|\| !reason\.trim\(\)\}/g)?.length,
    3
  );
  assert.match(adminPage, /disabled=\{!selected\} onClick=\{\(\) => action\("revive"\)\}/);
  assert.match(adminPage, /disabled=\{!karmaUserId \|\| !reason\.trim\(\)\}/);
});
