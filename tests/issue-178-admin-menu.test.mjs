import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const source = fs.readFileSync(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const header = source.slice(
  source.indexOf("<header"),
  source.indexOf("</header>") + "</header>".length,
);
const adminMenu = source.slice(
  source.indexOf("function AdminMenuPage()"),
  source.indexOf("function ProjectSettingsPage()"),
);

const adminDestinations = [
  ["/admin/shop-logs", "Логи"],
  ["/admin/market-sales", "Рынок-логи"],
  ["/admin/transfer-logs", "Передачи"],
  ["/admin/karma-shop-logs", "Карма-логи"],
  ["/admin/grant-logs", "Журнал выдач"],
];

test("header exposes one administrative menu entry without individual log links", () => {
  assert.match(header, /to="\/admin-menu"[^>]*>[\s\S]*?Админ-Меню<\/Link>/);
  for (const [route] of adminDestinations) {
    assert.doesNotMatch(header, new RegExp(`to="${route}"`));
  }
});

test("admin menu contains every requested destination", () => {
  for (const [route, label] of adminDestinations) {
    assert.match(adminMenu, new RegExp(`to="${route}"[^>]*>[\\s\\S]*?${label}<\\/Link>`));
  }
});

test("moved log pages return to the administrative menu", () => {
  assert.equal(
    source.match(/to="\/admin-menu">Назад<\/Link>/g)?.length,
    adminDestinations.length,
  );
});

test("admin routes use the project-aware administrative guard", () => {
  assert.match(source, /function AdminProtected\(/);
  for (const route of ["/admin-menu", "/admin", ...adminDestinations.map(([route]) => route)]) {
    assert.match(source, new RegExp(`path="${route}" element=\\{<AdminProtected>`));
  }
  assert.match(source, /if \(!project\.is_admin\) return <Navigate to="\/" replace \/>/);
});
