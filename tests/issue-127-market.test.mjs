import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("menu and router expose the market page", () => {
  assert.match(source, /to="\/market"[^>]*>.*Рынок/);
  assert.match(source, /path="\/market"/);
  assert.match(source, /function MarketPage/);
});

test("market form captures the required sale fields and displays the new balance", () => {
  const market = source.slice(
    source.indexOf("function MarketPage()"),
    source.indexOf("function AdminPage()"),
  );
  assert.match(market, />Персонаж</);
  assert.match(market, />Наименование предмета</);
  assert.match(market, />Полученная сумма, зм</);
  assert.match(market, /\/market\/sales/);
  assert.match(market, /inventory\?\.gold/);
});

test("administrators can open the market audit journal", () => {
  assert.match(source, /to="\/admin\/market-sales"/);
  assert.match(source, /path="\/admin\/market-sales"/);
  assert.match(source, /function MarketSalesPage/);
});
