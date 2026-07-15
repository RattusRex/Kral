import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("approved homebrew uses a structured responsive table", () => {
  assert.match(source, /function ApprovedHomebrewPage/);
  assert.match(source, /className="responsive-table/);
  for (const heading of ["Название", "Тип", "Кол-во кармы / Бан", "Источник / Ссылка", "Примечания"]) {
    assert.match(source, new RegExp(`label="${heading}"`));
  }
  assert.match(source, />Открыть</);
});

test("homebrew table supports search, filters, and sortable columns", () => {
  assert.match(source, /placeholder="Поиск по названию"/);
  assert.match(source, />Все типы</);
  assert.match(source, />Карма</);
  assert.match(source, />Бан</);
  assert.match(source, /setSort/);
  assert.match(source, /localeCompare/);
});

test("only administrators receive homebrew row management controls", () => {
  assert.match(source, /user\?\.is_admin[^]*Создать запись/);
  assert.match(source, /startEdit/);
  assert.match(source, /remove/);
  assert.match(source, /move\(index, -1\)/);
  assert.match(source, /move\(index, 1\)/);
});
