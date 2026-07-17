import puppeteer from "puppeteer-core";

const browser = await puppeteer.launch({ headless: true, executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
await page.goto("http://127.0.0.1:5173/login");
await page.waitForSelector('input[placeholder="email"]');
await page.type('input[placeholder="email"]', "admin");
await page.type('input[type="password"]', "admin123");
await Promise.all([page.waitForNavigation(), page.click('button[type="submit"]')]);
await page.waitForFunction(() => document.body.innerText.includes("Эпоха Катастроф"));
await page.evaluate(() => localStorage.setItem("active_project_id", "1"));
await page.goto("http://127.0.0.1:5173/admin/player-profiles");
await page.waitForFunction(() => document.body.innerText.includes("Profile Hero")).catch(async () => {
  console.error("URL:", page.url());
  console.error(await page.evaluate(() => document.body.innerText));
  throw new Error("Player profile data did not render");
});
await page.screenshot({ path: "docs/screenshots/issue-247-player-profiles.png", fullPage: true });
await browser.close();
