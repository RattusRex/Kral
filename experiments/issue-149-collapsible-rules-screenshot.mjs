import assert from "node:assert/strict";
import { chromium } from "playwright";

const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: true
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

await page.route("**/api/**", async (route) => {
  const pathname = new URL(route.request().url()).pathname;
  const responses = {
    "/api/me": {
      id: 7,
      username: "Игрок",
      email: "player@example.com",
      karma: 3,
      role: "player",
      is_admin: false,
      is_owner: false
    },
    "/api/projects": [{
      id: 1,
      name: "Эпоха Катастроф",
      slug: "epoch-of-catastrophe",
      role: "player",
      is_admin: false,
      can_manage_settings: false,
      features: {
        shop: true,
        market: true,
        karma_shop: true,
        recruitments: true,
        personal_hirelings: true,
        simulacrums: true
      }
    }],
    "/api/content-pages/server-rules": [
      { id: 11, page_slug: "server-rules", title: "Создание персонажа", content: "Персонаж начинает игру с первого уровня. Используйте разрешённые книги и укажите предысторию героя.", position: 0 },
      { id: 12, page_slug: "server-rules", title: "Правила поведения", content: "Уважайте других игроков и ведущих. Спорные ситуации обсуждаются после игровой сцены.", position: 1 },
      { id: 13, page_slug: "server-rules", title: "Межсессионная деятельность", content: "Работа, поиск предметов и другие занятия расходуют свободные дни персонажа согласно календарю кампании.", position: 2 },
      { id: 14, page_slug: "server-rules", title: "Торговля и передача предметов", content: "Все операции с валютой и предметами фиксируются в инвентаре выбранного персонажа.", position: 3 },
      { id: 15, page_slug: "server-rules", title: "Карма", content: "Карма принадлежит игроку, а не отдельному персонажу, и начисляется после игры.", position: 4 }
    ]
  };
  await route.fulfill({
    contentType: "application/json",
    status: responses[pathname] ? 200 : 404,
    body: JSON.stringify(responses[pathname] ?? { detail: "Not found" })
  });
});

await page.goto("http://127.0.0.1:4173");
await page.evaluate(() => localStorage.setItem("access_token", "screenshot-fixture"));
await page.goto("http://127.0.0.1:4173/server-rules");

assert.equal(await page.getByRole("button", { name: "Развернуть публикацию «Правила поведения»" }).getAttribute("aria-expanded"), "false");
assert.equal(await page.getByText("Уважайте других игроков и ведущих.", { exact: false }).count(), 0);

await page.getByRole("button", { name: "Развернуть публикацию «Правила поведения»" }).click();
assert.equal(await page.getByRole("button", { name: "Свернуть публикацию «Правила поведения»" }).getAttribute("aria-expanded"), "true");
assert.equal(await page.getByText("Уважайте других игроков и ведущих.", { exact: false }).count(), 1);

await page.reload();
assert.equal(await page.getByRole("button", { name: "Свернуть публикацию «Правила поведения»" }).getAttribute("aria-expanded"), "true");

await page.getByRole("button", { name: "Свернуть публикацию «Правила поведения»" }).click();
await page.screenshot({ path: "docs/screenshots/issue-161-collapsed-rules-default.png", fullPage: true });
await browser.close();
