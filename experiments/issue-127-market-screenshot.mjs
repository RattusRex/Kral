import { chromium } from "playwright";

const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
await page.goto("http://127.0.0.1:5173/login");
await page.getByPlaceholder("email").fill("admin");
await page.getByPlaceholder("password").fill("admin123");
await page.getByRole("button", { name: "Войти" }).click();
await page.waitForURL("http://127.0.0.1:5173/characters");

const token = await page.evaluate(() => localStorage.getItem("access_token"));
const response = await page.request.post("http://127.0.0.1:8000/api/characters", {
  headers: { Authorization: `Bearer ${token}` },
  data: { name: "Рейна", class_name: "Воин", level: 3, route: "Путь стали" },
});
if (!response.ok()) throw new Error(`Character setup failed: ${response.status()} ${await response.text()}`);

await page.goto("http://127.0.0.1:5173/market");
await page.getByLabel("Наименование предмета").fill("Длинный меч");
await page.getByLabel("Полученная сумма, зм").fill("8");
await page.getByRole("button", { name: "Продать предмет" }).click();
await page.getByText("Продажа записана").waitFor();
await page.screenshot({ path: "docs/screenshots/issue-127-market-sale.png", fullPage: true });
await browser.close();
