import assert from "node:assert/strict";
import { chromium } from "playwright";

const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: true
});
const page = await browser.newPage({ viewport: { width: 960, height: 720 } });

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
        simulacrums: true,
        leaderboard: true,
        karma: true
      }
    }],
    "/api/projects/current": {
      id: 1,
      name: "Эпоха Катастроф",
      slug: "epoch-of-catastrophe",
      role: "player",
      is_admin: false,
      can_manage_settings: false,
      features: {}
    }
  };
  await route.fulfill({
    contentType: "application/json",
    status: responses[pathname] ? 200 : 404,
    body: JSON.stringify(responses[pathname] ?? { detail: "Not found" })
  });
});

await page.addInitScript(() => localStorage.setItem("access_token", "screenshot-fixture"));
await page.goto("http://127.0.0.1:4173");

const title = page.getByRole("link", { name: "Эпоха Катастроф" });
await title.waitFor();
const wrapping = await title.evaluate((element) => {
  const range = document.createRange();
  range.selectNodeContents(element);
  return {
    text: element.textContent,
    lineCount: new Set([...range.getClientRects()].map((rect) => Math.round(rect.top))).size,
    overflowWrap: getComputedStyle(element).overflowWrap,
    wordBreak: getComputedStyle(element).wordBreak
  };
});

assert.equal(wrapping.text, "Эпоха Катастроф");
assert.equal(wrapping.overflowWrap, "normal");
assert.equal(wrapping.wordBreak, "normal");
assert.ok(wrapping.lineCount <= 2, "the two-word title must use at most one line per word");

await page.locator("header").screenshot({ path: "docs/screenshots/issue-173-project-title.png" });
await browser.close();
