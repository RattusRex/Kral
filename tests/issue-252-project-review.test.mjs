import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const review = readFileSync("docs/project-review.md", "utf8");
const frontend = readFileSync("app/src/main.tsx", "utf8");
const inventoryApi = readFileSync("app/api/inventory.py", "utf8");

test("project review documents every registered frontend route", () => {
  const routes = [...frontend.matchAll(/<Route path="([^"]+)"/g)]
    .map((match) => match[1])
    .filter((route) => route !== "*");

  assert.ok(routes.length >= 25, "route extraction should cover the current SPA");
  for (const route of routes) {
    assert.match(review, new RegExp(`\`${route.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\``));
  }
});

test("project review preserves the implemented shop constants", () => {
  for (const expected of [
    '"Обычный": {"dc": 5, "days_dice": 4, "base_price": 100}',
    '"Необычный": {"dc": 10, "days_dice": 8, "base_price": 500}',
    '"Редкий": {"dc": 15, "days_dice": 12, "base_price": 5000}',
    '"Плохой": 1',
    '"Хороший": 5',
    '"Компетентный": 10',
    '"Эксперт": 25',
  ]) {
    assert.ok(inventoryApi.includes(expected), `missing source constant: ${expected}`);
  }

  for (const documentedValue of ["| Обычный | 5 |", "| Необычный | 10 |", "| Редкий | 15 |", "| Эксперт | +8 | 25 зм |"])
    assert.ok(review.includes(documentedValue), `missing documented rule: ${documentedValue}`);
});

test("project review covers the cross-cutting agent context requested by issue 252", () => {
  for (const heading of [
    "Техническая архитектура",
    "Сквозные правила безопасности и области данных",
    "Карта экранов и поведения",
    "Основные сущности БД",
    "API по модулям",
    "Что важно учитывать при следующих изменениях",
    "Известные технические особенности и риски",
  ]) {
    assert.ok(review.includes(heading), `missing review section: ${heading}`);
  }
});
