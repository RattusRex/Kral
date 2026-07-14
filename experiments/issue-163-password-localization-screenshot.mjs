import assert from "node:assert/strict";
import { chromium } from "playwright";

const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

await page.route("**/api/users", (route) => route.fulfill({
  contentType: "application/json",
  status: 422,
  body: JSON.stringify({
    detail: "Пароль должен содержать не менее 6 символов",
  }),
}));

await page.goto("http://127.0.0.1:4173/register");
await page.getByPlaceholder("username").fill("новый-игрок");
await page.getByPlaceholder("email").fill("player@example.com");
await page.getByPlaceholder("Пароль").fill("Слабый-пароль");
await page.getByRole("button", { name: "Создать аккаунт" }).click();

await page.getByText("Пароль должен содержать не менее 6 символов", { exact: false }).first().waitFor();
assert.equal(await page.getByPlaceholder("Пароль").count(), 1);
assert.equal(await page.getByPlaceholder("password").count(), 0);

await page.screenshot({
  path: "docs/screenshots/issue-163-password-localization.png",
  fullPage: true,
});
await browser.close();
