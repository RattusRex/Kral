import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const main = readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../app/src/api.ts", import.meta.url), "utf8");

test("chat exposes deletion only to administrators and removes deleted rows locally", () => {
  assert.match(main, /user\?\.is_admin/);
  assert.match(main, /api\.delete\(`\/chat\/messages\/\$\{messageId\}`\)/);
  assert.match(main, /setMessages\(\(current\) => current\.filter/);
  assert.match(main, /Удалить сообщение/);
});

test("character forms and sheets expose persisted class levels", () => {
  assert.match(api, /class_levels: CharacterClassLevel\[\]/);
  assert.match(main, /Дополнительные классы/);
  assert.match(main, /Добавить класс/);
  assert.match(main, /Общий уровень/);
});
