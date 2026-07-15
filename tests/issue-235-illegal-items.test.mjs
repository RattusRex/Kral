import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("menu and router expose the illegal items page", () => {
  assert.match(source, /to="\/illegal-items"[^>]*>[\s\S]*?Нелегальные предметы<\/Link>/);
  assert.match(source, /path="\/illegal-items"[^\n]*IllegalItemsPage/);
});

test("illegal items use the requested responsive table fields", () => {
  assert.match(source, /function IllegalItemsPage/);
  assert.match(source, /className="responsive-table/);
  for (const heading of ["Название", "Редкость"]) assert.match(source, new RegExp(`label="${heading}"`));
  for (const heading of ["Ссылка", "Источник"]) assert.match(source, new RegExp(`<th[^>]*>${heading}</th>`));
  assert.match(source, />Открыть</);
});

test("illegal items support search, rarity filtering and sorting", () => {
  assert.match(source, /placeholder="Поиск по названию"/);
  assert.match(source, />Все редкости</);
  assert.match(source, /illegalItemRarities/);
  assert.match(source, /setSort/);
  assert.match(source, /localeCompare/);
});

test("only technician-level users receive illegal item management controls", () => {
  assert.match(source, /user\?\.is_admin[^]*Создать предмет/);
  assert.match(source, /startEdit/);
  assert.match(source, /remove/);
  assert.match(source, /move\(index, -1\)/);
  assert.match(source, /move\(index, 1\)/);
});
