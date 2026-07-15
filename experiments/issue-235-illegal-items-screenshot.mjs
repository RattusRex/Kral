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
await page.goto(`${baseURL}/illegal-items`);
await page.getByRole("heading", { name: "Нелегальные предметы" }).waitFor();

for (const item of [
  ["Кольцо трёх желаний", "Легендарный", "Dungeon Master's Guide"],
  ["Клинок вечной ночи", "Артефакт", "Griffon's Saddlebag"],
]) {
  await page.getByRole("button", { name: "Создать предмет" }).click();
  const form = page.locator("form");
  await form.locator("input").nth(0).fill(item[0]);
  await form.locator("select").selectOption({ label: item[1] });
  await form.locator("input").nth(1).fill(`https://example.com/items/${encodeURIComponent(item[0])}`);
  await form.locator("input").nth(2).fill(item[2]);
  await page.getByRole("button", { name: "Сохранить" }).click();
  await page.getByRole("cell", { name: item[0] }).waitFor();
}

await page.screenshot({ path: "docs/screenshots/issue-235-illegal-items.png", fullPage: true });

await page.setViewportSize({ width: 768, height: 780 });
const tableRegion = page.getByRole("region", { name: "Таблица нелегальных предметов" });
const dimensions = await tableRegion.evaluate((element) => ({
  clientWidth: element.clientWidth,
  scrollWidth: element.scrollWidth,
  bodyWidth: document.documentElement.scrollWidth,
  viewportWidth: window.innerWidth,
}));
if (dimensions.scrollWidth <= dimensions.clientWidth || dimensions.bodyWidth > dimensions.viewportWidth) {
  throw new Error(`Responsive table assertion failed: ${JSON.stringify(dimensions)}`);
}

await browser.close();
