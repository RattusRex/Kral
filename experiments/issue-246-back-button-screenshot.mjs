import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";

const server = spawn("npm", ["run", "preview", "--", "--port", "4173"], {
  stdio: "inherit",
});

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

try {
  await sleep(1_500);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });

  const project = {
    id: 1, name: "Эпоха Катастроф", karma: 0, is_admin: true, can_manage_settings: true,
    features: { karma: false, karma_shop: false, recruitments: true },
  };
  await page.route("**/api/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/me") return route.fulfill({ json: {
      id: 1, username: "admin", email: "admin@example.com", karma: 0, role: "owner", is_admin: true, is_head_admin: true, is_owner: true,
    } });
    if (path === "/api/projects/current/about") return route.fulfill({ json: { posts: [], creator_content: "" } });
    if (path === "/api/projects/current") return route.fulfill({ json: project });
    if (path === "/api/projects") return route.fulfill({ json: [project] });
    return route.fulfill({ json: [] });
  });

  await page.goto("http://127.0.0.1:4173/login");
  if (await page.getByRole("button", { name: "Вернуться на предыдущую страницу" }).count()) {
    throw new Error("Back button must not appear on the login page");
  }

  await page.evaluate(() => {
    localStorage.setItem("access_token", "visual-test-token");
    localStorage.setItem("active_project_id", "1");
  });
  await page.goto("http://127.0.0.1:4173/profile");
  await page.getByRole("button", { name: "Вернуться на предыдущую страницу" }).waitFor();
  await page.waitForTimeout(500);
  await page.screenshot({ path: "docs/screenshots/issue-246-back-button-header-mobile.png", fullPage: true });
  await browser.close();
} finally {
  server.kill("SIGTERM");
}
