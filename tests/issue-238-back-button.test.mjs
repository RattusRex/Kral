import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../app/src/styles.css", import.meta.url), "utf8");

const backButton = source.slice(
  source.indexOf("function BackButton()"),
  source.indexOf("function Shell("),
);
const shell = source.slice(
  source.indexOf("function Shell("),
  source.indexOf("function HomePage()"),
);
const header = shell.slice(
  shell.indexOf("<header"),
  shell.indexOf("</header>") + "</header>".length,
);
const app = source.slice(source.indexOf("function App()"));

test("the shared back button is mounted in the authenticated header only", () => {
  assert.match(header, /<BackButton\s*\/>/);
  assert.doesNotMatch(app, /<BackButton\s*\/>/);
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

test("the control participates in the responsive header layout without overlaying content", () => {
  assert.match(styles, /\.back-button\s*\{/);
  const rule = styles.slice(
    styles.indexOf(".back-button"),
    styles.indexOf("}", styles.indexOf(".back-button")) + 1,
  );
  assert.doesNotMatch(rule, /position:\s*(?:fixed|absolute)/);
  assert.doesNotMatch(rule, /(?:top|right|bottom|left):/);
});
