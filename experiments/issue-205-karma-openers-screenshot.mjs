import { chromium } from "playwright";

const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });

await page.route("**/api/me", (route) => route.fulfill({
  contentType: "application/json",
  body: JSON.stringify({
    id: 205,
    username: "Игрок",
    email: "player@example.com",
    karma: 50,
    role: "player",
  }),
}));
await page.route("**/api/projects/current", (route) => route.fulfill({
  contentType: "application/json",
  body: JSON.stringify({
    id: 1,
    name: "Эпоха Катастроф",
    role: "player",
    features: { karma: true, karma_shop: true },
  }),
}));
await page.route("**/api/characters", (route) => route.fulfill({
  contentType: "application/json",
  body: JSON.stringify([]),
}));
await page.route("**/api/karma-shop/openers", (route) => route.fulfill({
  contentType: "application/json",
  body: JSON.stringify([
    { name: "Смена расы", cost: 10, note: "Условия применения проверяются администрацией или мастером." },
    { name: "Смена класса", cost: 20, note: "Условия применения проверяются администрацией или мастером." },
    { name: "Смена подкласса", cost: 15, note: "Условия применения проверяются администрацией или мастером." },
    { name: "Открыть заклинание", cost: 5, note: "Условия применения проверяются администрацией или мастером." },
  ]),
}));

await page.goto("http://127.0.0.1:4173");
await page.evaluate(() => localStorage.setItem("access_token", "screenshot-fixture"));
await page.goto("http://127.0.0.1:4173/karma-shop");
await page.getByLabel("Открывашка").selectOption("Смена класса");
await page.getByText("Купить за 20 кармы").waitFor();
await page.screenshot({ path: "docs/screenshots/issue-205-karma-openers.png", fullPage: true });
await browser.close();
