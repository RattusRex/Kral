import { chromium } from "playwright";

const baseURL = process.env.APP_URL ?? "http://127.0.0.1:5173";
const browser = await chromium.launch({ executablePath: "/usr/bin/google-chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 780 }, deviceScaleFactor: 1 });
page.setDefaultTimeout(10_000);

await page.goto(`${baseURL}/login`);
await page.locator('input[placeholder="email"]').fill("admin");
await page.locator('input[type="password"]').fill("admin123");
await page.getByRole("button", { name: "Войти" }).click();
await page.waitForURL(/\/projects/, { waitUntil: "domcontentloaded" });
await page.getByRole("button", { name: "Эпоха Катастроф" }).click();
await page.goto(`${baseURL}/approved-homebrew`);
await page.getByRole("heading", { name: "Одобренное ХБ" }).waitFor();
await page.getByRole("cell", { name: "Клятва Мора" }).waitFor();
await page.screenshot({ path: "docs/screenshots/issue-225-homebrew-table.png", fullPage: true });

await browser.close();
