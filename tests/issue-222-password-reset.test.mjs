import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const mainSource = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");

test("login links to the forgot-password form and both public routes exist", () => {
  assert.match(mainSource, /to="\/forgot-password"[^>]*>Забыли пароль\?/);
  assert.match(mainSource, /path="\/forgot-password" element=\{<ForgotPassword \/>\}/);
  assert.match(mainSource, /path="\/reset-password" element=\{<ResetPassword \/>\}/);
});

test("forgot-password form submits email and shows a neutral response", () => {
  assert.match(mainSource, /api\.post\("\/password\/forgot", \{ email \}\)/);
  assert.match(mainSource, /Если аккаунт с указанным адресом существует/);
});

test("reset form submits token, password, and confirmation with current policy", () => {
  assert.match(mainSource, /api\.post\("\/password\/reset", \{ token, password, password_confirmation/);
  assert.match(mainSource, /Подтверждение нового пароля/);
  assert.match(mainSource, /minLength=\{6\}/);
  assert.match(mainSource, /maxLength=\{72\}/);
  assert.match(mainSource, /Пароль успешно изменён/);
});
