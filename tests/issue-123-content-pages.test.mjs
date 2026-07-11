import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("main menu and router expose both informational pages", () => {
  assert.match(source, /to="\/server-rules"[^>]*>.*Правила сервера/);
  assert.match(source, /to="\/approved-homebrew"[^>]*>.*Одобренное ХБ/);
  assert.match(source, /path="\/server-rules"/);
  assert.match(source, /path="\/approved-homebrew"/);
});

test("content page supports admin editing and read-only player rendering", () => {
  assert.match(source, /function ContentPage/);
  assert.match(source, /user\?\.is_admin/);
  assert.match(source, /Создать блок/);
  assert.match(source, /Редактировать/);
  assert.match(source, /Удалить/);
});

test("admin panels collapse independently and persist their state", () => {
  assert.match(source, /admin-panel-state/);
  assert.match(source, /localStorage\.setItem/);
  for (const panel of ["master", "character", "karma", "interface"]) {
    assert.match(source, new RegExp(`${panel}:`));
  }
  assert.match(source, /aria-expanded/);
});
