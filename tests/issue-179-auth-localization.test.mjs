import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const mainSource = await readFile(new URL("../app/src/main.tsx", import.meta.url), "utf8");
const usersSource = await readFile(new URL("../app/api/users.py", import.meta.url), "utf8");

test("registration delivery failure keeps the created email available for resend", () => {
  assert.match(mainSource, /verification_email_delivery_failed/);
  assert.match(mainSource, /setRegisteredEmail\((?:detail\.email \?\? )?form\.email\)/);
  assert.match(mainSource, /Отправить письмо повторно/);
});

test("authentication API messages shown to users are localized", () => {
  const englishMessages = [
    "Username already taken",
    "Email already registered",
    "Username or email already exists",
    "Account created, but verification email could not be sent",
    "Verification email sent",
    "Invalid or expired verification token",
    "Email verified",
    "Verification email could not be sent",
    "Invalid credentials",
    "User not found"
  ];

  for (const message of englishMessages) {
    assert.doesNotMatch(usersSource, new RegExp(message));
  }
});
