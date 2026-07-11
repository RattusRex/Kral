import { chromium } from "playwright";

const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });

const character = {
  id: 143,
  project_id: 1,
  name: "Элария",
  class_name: "Волшебник",
  class_levels: [{ class_name: "Волшебник", level: 10 }],
  subclass: "Школа прорицания",
  race: "Эльф",
  background: "Мудрец",
  route: "Исследователь",
  level: 10,
  xp: 4,
  hp: 54,
  temp_hp: 0,
  armor_class: 16,
  speed: 30,
  strength: 8,
  dexterity: 14,
  constitution: 14,
  intelligence: 20,
  wisdom: 12,
  charisma: 10,
  investigation: 8,
  skill_proficiencies: [],
  skill_expertise: [],
  saving_throw_proficiencies: [],
  personal_hireling_enabled: true,
  simulacrum_enabled: true,
  is_dead: false,
};

const entries = {
  character: [{ id: 1, character_id: 143, start_date: "2026-07-01", end_date: "2026-10-08", days: 100, reason: "Долгое исследование", source: "manual", agent_type: "character" }],
  personal_hireling: [{ id: 2, character_id: 143, start_date: "2026-06-10", end_date: "2026-06-16", days: 7, reason: "Поиск редких компонентов", source: "manual", agent_type: "personal_hireling" }],
  simulacrum: [{ id: 3, character_id: 143, start_date: "2026-05-20", end_date: "2026-05-22", days: 3, reason: "Помощь в лаборатории", source: "manual", agent_type: "simulacrum" }],
};

await page.route("**/api/**", (route) => {
  const url = new URL(route.request().url());
  let body = {};
  if (url.pathname.endsWith("/api/me")) body = { id: 1, username: "admin", email: "admin@example.com", karma: 0, role: "admin", is_admin: true };
  else if (url.pathname.endsWith("/api/projects")) body = [{ id: 1, name: "Эпоха Катастрофы", slug: "epoch", role: "admin", features: {}, is_admin: true, can_manage_settings: true, can_manage_roles: true }];
  else if (url.pathname.endsWith("/api/characters")) body = [character];
  else if (url.pathname.endsWith("/transfer-targets")) body = [];
  else if (url.pathname.endsWith("/inventory")) body = { id: 1, character_id: 143, gold: 100, silver: 0, copper: 0, notes: "", items: [] };
  else if (url.pathname.endsWith("/attacks")) body = [];
  else if (url.pathname.includes("/calendar")) {
    const actor = url.pathname.includes("personal_hireling") ? "personal_hireling" : url.pathname.includes("simulacrum") ? "simulacrum" : "character";
    body = { game_epoch: "2025-06-01", created_at: "2025-06-01", current_date: "2026-10-09", total_days: 495, busy_days: entries[actor][0].days, free_days: 495 - entries[actor][0].days, can_manage: true, page: 1, page_size: 10, total_entries: 1, pages: 1, entries: entries[actor] };
  }
  return route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
});

await page.goto("http://127.0.0.1:4173");
await page.evaluate(() => localStorage.setItem("access_token", "screenshot-fixture"));
await page.goto("http://127.0.0.1:4173/characters/143");
await page.getByText("01.07.2026 — 08.10.2026").waitFor();
await page.screenshot({ path: "docs/screenshots/issue-143-calendar-ranges.png", fullPage: true });
await browser.close();
