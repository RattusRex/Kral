import { chromium } from "playwright";
import { readFile } from "node:fs/promises";

const fixture = JSON.parse(await readFile("/tmp/issue102-research/ui.json", "utf8"));
const browser = await chromium.launch({ executablePath: "/usr/bin/google-chrome", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1400 }, deviceScaleFactor: 1 });
await page.goto("http://127.0.0.1:4173");
await page.evaluate(({ token }) => localStorage.setItem("access_token", token), fixture);
await page.goto(`http://127.0.0.1:4173/characters/${fixture.id}`);
await page.waitForSelector("text=Бонус мастерства");
await page.waitForSelector("text=Компетентность");
await page.screenshot({ path: "docs/screenshots/issue-102-calendar-skills.png", fullPage: true });
await browser.close();
