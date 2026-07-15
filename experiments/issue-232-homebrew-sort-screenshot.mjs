import { chromium } from "playwright";

const baseURL = process.env.APP_URL ?? "http://127.0.0.1:4173";
const browser = await chromium.launch({ executablePath: "/usr/bin/google-chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 780 }, deviceScaleFactor: 1 });
page.setDefaultTimeout(10_000);

await page.addInitScript(() => {
  localStorage.setItem("access_token", "test-token");
  localStorage.setItem("active_project_id", "1");
});
await page.route("**/api/users/me", (route) => route.fulfill({ json: { id: 1, username: "tester", email: "tester@example.com", karma: 0, is_admin: false } }));
await page.route("**/api/projects/current", (route) => route.fulfill({ json: { id: 1, name: "Эпоха Катастроф", karma: 0, role: "player", features: {} } }));
await page.route("**/api/content-pages/approved-homebrew", (route) => route.fulfill({ json: [
  { id: 1, title: "Стоимость 5", content: "", content_type: "Класс", karma_cost: 5, is_banned: false, source_url: "https://example.com/5", notes: "", position: 0 },
  { id: 2, title: "Стоимость 60", content: "", content_type: "Класс", karma_cost: 60, is_banned: false, source_url: "https://example.com/60", notes: "", position: 1 },
  { id: 3, title: "Стоимость 35", content: "", content_type: "Класс", karma_cost: 35, is_banned: false, source_url: "https://example.com/35", notes: "", position: 2 },
  { id: 4, title: "Запрещено", content: "", content_type: "Класс", karma_cost: null, is_banned: true, source_url: "https://example.com/ban", notes: "", position: 3 },
] }));

await page.goto(`${baseURL}/approved-homebrew`);
const karmaHeading = page.getByRole("button", { name: /Карма \/ Бан/ });
await karmaHeading.click();
await page.locator('th[aria-sort="descending"]').getByText("Карма / Бан").waitFor();
const costs = await page.locator("tbody tr td:nth-child(3)").allTextContents();
if (costs.join("|") !== "60 кармы|35 кармы|5 кармы|Бан") throw new Error(`Unexpected descending order: ${costs.join("|")}`);
await page.screenshot({ path: "docs/screenshots/issue-232-homebrew-karma-sort.png", fullPage: true });

await karmaHeading.click();
const ascendingCosts = await page.locator("tbody tr td:nth-child(3)").allTextContents();
if (ascendingCosts.join("|") !== "5 кармы|35 кармы|60 кармы|Бан") throw new Error(`Unexpected ascending order: ${ascendingCosts.join("|")}`);

await browser.close();
