import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const resultPanel = source.slice(
  source.indexOf("function ResultPanel("),
  source.indexOf("function ProfilePage()"),
);

test("shop result presents only the purchase decision details", () => {
  assert.match(resultPanel, /<Stat label="Время поиска" value=\{`\$\{result\.days\} дн\.`\} \/>/);
  assert.match(resultPanel, /<Stat label="Цена" value=\{`\$\{result\.item_price\} зм`\} \/>/);
  assert.match(resultPanel, /result\.searcher_type === "paid_hireling"[\s\S]*<Stat label="Плата наёмнику" value=\{`\$\{result\.hireling_cost\} зм`\} \/>/);

  assert.doesNotMatch(resultPanel, /result\.rarity/);
  assert.doesNotMatch(resultPanel, /result\.search_roll/);
  assert.doesNotMatch(resultPanel, /result\.modifier/);
  assert.doesNotMatch(resultPanel, /result\.total_roll/);
  assert.doesNotMatch(resultPanel, /result\.dc/);
  assert.doesNotMatch(resultPanel, /result\.searcher_label/);
  assert.doesNotMatch(resultPanel, /result\.price_roll/);
  assert.doesNotMatch(resultPanel, /result\.multiplier/);
  assert.doesNotMatch(resultPanel, /result\.total_cost/);
});

test("non-paid searchers do not render a hireling payment", () => {
  assert.match(resultPanel, /result\.searcher_type === "paid_hireling"/);
  assert.doesNotMatch(resultPanel, /result\.hireling_cost > 0/);
});
