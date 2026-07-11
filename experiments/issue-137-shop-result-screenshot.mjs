import { chromium } from "playwright";

const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });

await page.route("**/api/characters", (route) => route.fulfill({
  contentType: "application/json",
  body: JSON.stringify([{
    id: 137,
    name: "Рейна",
    level: 5,
    personal_hireling_enabled: false,
    simulacrum_enabled: false,
  }]),
}));
await page.route("**/api/characters/137/inventory", (route) => route.fulfill({
  contentType: "application/json",
  body: JSON.stringify({ id: 137, gold: 1000, silver: 0, copper: 0, notes: "", items: [] }),
}));
await page.route("**/api/shop/magic-items**", (route) => route.fulfill({
  contentType: "application/json",
  body: JSON.stringify([]),
}));
await page.route("**/api/characters/137/shop/search", (route) => route.fulfill({
  contentType: "application/json",
  body: JSON.stringify({
    quote_id: 137,
    mode: "buy",
    searcher_type: "paid_hireling",
    searcher_label: "Платный наёмник",
    item_name: "Длинный меч +1",
    rarity: "Необычный",
    is_consumable: false,
    success: true,
    search_roll: 17,
    modifier: 8,
    total_roll: 25,
    dc: 15,
    days: 5,
    hireling_cost: 100,
    price_roll: 54,
    multiplier: 1,
    item_price: 500,
    total_cost: 600,
    is_consumed: false,
    inventory: { id: 137, gold: 900, silver: 0, copper: 0, notes: "", items: [] },
  }),
}));

await page.goto("http://127.0.0.1:4173");
await page.evaluate(() => localStorage.setItem("access_token", "screenshot-fixture"));
await page.goto("http://127.0.0.1:4173/shop");
await page.getByLabel("Название предмета").fill("Длинный меч +1");
await page.getByRole("button", { name: "Найти продавца" }).click();
await page.getByText("Сделка найдена").waitFor();
await page.screenshot({ path: "docs/screenshots/issue-137-shop-result.png", fullPage: true });
await browser.close();
