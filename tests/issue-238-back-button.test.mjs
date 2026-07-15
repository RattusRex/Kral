import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../app/src/styles.css", import.meta.url), "utf8");

const backButton = source.slice(
  source.indexOf("function BackButton()"),
  source.indexOf("function Shell("),
);
const app = source.slice(source.indexOf("function App()"));

test("a single shared back button is mounted for every route", () => {
  assert.match(app, /<BackButton\s*\/>/);
  assert.match(backButton, /Назад/);
  assert.match(backButton, /ArrowLeft/);
  assert.match(backButton, /className="back-button btn-secondary"/);
});

test("back navigation uses in-app history and safely falls back home", () => {
  assert.match(backButton, /sessionStorage\.getItem\(NAVIGATION_HISTORY_KEY\)/);
  assert.match(backButton, /window\.history\.state\?\.idx/);
  assert.match(backButton, /navigate\(-1\)/);
  assert.match(backButton, /navigate\("\/",\s*\{\s*replace:\s*true\s*\}\)/);
});

test("the control keeps a consistent responsive position", () => {
  assert.match(styles, /\.back-button\s*\{/);
  assert.match(styles, /@media \(max-width:\s*639px\)[\s\S]*\.back-button\s*\{/);
});
