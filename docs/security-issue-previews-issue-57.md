# Security Issue Payload Previews For Issue 57

Destination requested: `RattusRex/Kral` GitHub issues.

The repository owner approved these payloads in issue and pull request comments on 2026-07-05. Fresh exact duplicate searches and readback on 2026-07-05 found that all six finding IDs and fingerprints are already tracked in `RattusRex/Kral#60`, so no duplicate issues were created.

## 1. [Security] Players can self-modify karma through authenticated `/me` endpoints

```markdown
## Summary
Any authenticated player can call `/api/me/karma/add` or `/api/me/karma/subtract` and directly change their global player karma without an admin or GM role check.

## Source
Repository: `https://github.com/RattusRex/Kral`
Revision: `e9c2f722955b25a27713ea498ead16caf9879282`
Finding ID: `csf_fce24ba25df05bfd6c568a77`
Fingerprint: `codex-security/v1:sha256:9694be62ca86461d711f850b3b606b8b69d0f81372359371a69a7de1e3da0930`

## Affected Locations
- root_control: `app/api/users.py:160-179` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/users.py#L160-L179
- sink: `app/api/users.py:172-172` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/users.py#L172
- root_control: `app/api/users.py:182-200` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/users.py#L182-L200
- sink: `app/api/users.py:194-194` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/users.py#L194
- source: `app/schemas/user.py:13-14` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/schemas/user.py#L13-L14
- nearby_admin_control: `app/api/admin.py:513-542` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/admin.py#L513-L542

## Validation
- Method: bounded FastAPI TestClient PoC
- Evidence: The `self_karma_add` step returned status 200 and response karma 77 for a non-admin player.
- Counterevidence: The frontend does not expose this button, but direct API access is enough. Admin-only karma endpoints also exist and use `require_admin`.

## Attack Path
1. Register or log in as a normal player.
2. Send a bearer-authenticated POST to `/api/me/karma/add` with a positive amount.
3. The backend updates the player record and commits the new karma value.

## Severity
- Level: `medium`
- Priority: `P2`
- Rationale: The route is remote and authenticated, and the impact is integrity loss for a GM-controlled player currency rather than account compromise.

## Remediation
Remove the self-service karma mutation routes or gate them with the same admin/GM authorization used by `/api/admin/users/{user_id}/karma*`.

## Suggested Tests
- Add an integration test that a normal player receives 403/404 from `/api/me/karma/add` and `/api/me/karma/subtract`.
- Keep an admin test that verifies authorized GM karma updates still work.
```

## 2. [Security] Players can mint inventory currency and items outside shop/admin flows

```markdown
## Summary
Owner-only inventory endpoints let authenticated players add arbitrary items and currency to their own character inventory without shop quote confirmation or admin authorization.

## Source
Repository: `https://github.com/RattusRex/Kral`
Revision: `e9c2f722955b25a27713ea498ead16caf9879282`
Finding ID: `csf_ae69457a2652d52e4e9d74a0`
Fingerprint: `codex-security/v1:sha256:380d90c073ec2069b9585b9a3b45166cade3115adfb36981946c26f43d340273`

## Affected Locations
- root_control: `app/api/inventory.py:684-704` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/inventory.py#L684-L704
- sink: `app/api/inventory.py:694-700` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/inventory.py#L694-L700
- root_control: `app/api/inventory.py:749-768` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/inventory.py#L749-L768
- sink: `app/api/inventory.py:764-764` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/inventory.py#L764
- root_control: `app/api/inventory.py:798-816` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/inventory.py#L798-L816
- sink: `app/api/inventory.py:807-812` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/inventory.py#L807-L812
- source: `app/schemas/inventory.py:28-40` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/schemas/inventory.py#L28-L40
- nearby_admin_control: `app/api/admin.py:203-220` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/admin.py#L203-L220
- nearby_admin_control: `app/api/admin.py:401-419` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/admin.py#L401-L419

## Validation
- Method: bounded FastAPI TestClient PoC
- Evidence: The `self_currency_add` step returned 200 and increased currency; the `self_item_add` step returned 200 and added `Unreviewed Wand` for a non-admin player.
- Counterevidence: Players are allowed to manage inventory, but the first-prototype shop/admin model describes acquisition through shop buys/sells or admin grants; the frontend does not expose these direct add routes.

## Attack Path
1. Log in as a normal player and create or choose an owned character.
2. POST arbitrary currency to `/api/characters/{id}/inventory/currency/add`.
3. POST arbitrary item data to `/api/characters/{id}/inventory/items`.
4. Use the inflated inventory in later shop, transfer, or character-sheet workflows.

## Severity
- Level: `medium`
- Priority: `P2`
- Rationale: The issue is remotely reachable by any player and directly changes campaign economy state, but it is limited to the attacker's own characters.

## Remediation
Restrict direct item/currency grant endpoints to admins or replace them with shop-confirm/admin flows; leave player inventory notes, deletion, and transfer behavior on explicitly intended player endpoints.

## Suggested Tests
- Assert normal players cannot call direct item and currency add endpoints.
- Assert shop confirmation and admin grant endpoints remain authorized and functional.
```

## 3. [Security] Player character update can self-grant progression and clear death state

```markdown
## Summary
The player-owned character PATCH route accepts `xp`, `level`, and `is_dead`, allowing a player to bypass GM XP and revive workflows.

## Source
Repository: `https://github.com/RattusRex/Kral`
Revision: `e9c2f722955b25a27713ea498ead16caf9879282`
Finding ID: `csf_ee72b36158077bd9712e332f`
Fingerprint: `codex-security/v1:sha256:c4147b4d5fd397032bba15ed9c83e3d498bba745b59ea05a93f551eb2a23f4d5`

## Affected Locations
- source: `app/schemas/character.py:27-48` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/schemas/character.py#L27-L48
- root_control: `app/api/characters.py:147-179` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/characters.py#L147-L179
- sink: `app/api/characters.py:164-170` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/characters.py#L164-L170
- sink: `app/api/characters.py:177-178` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/characters.py#L177-L178
- model: `app/models/character.py:79-90` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/models/character.py#L79-L90
- nearby_admin_control: `app/api/admin.py:174-185` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/admin.py#L174-L185
- nearby_admin_control: `app/api/admin.py:368-379` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/admin.py#L368-L379

## Validation
- Method: bounded FastAPI TestClient PoC
- Evidence: The `self_character_progression_patch` step returned status 200 with level 20 and `is_dead` false for a non-admin player.
- Counterevidence: Players are allowed to edit some own character fields, but AGENTS/README assign XP grants and revival to game-master/admin workflows.

## Attack Path
1. Log in as a normal player and create or select an owned character.
2. PATCH `/api/characters/{id}` with `xp`, `level`, or `is_dead` values.
3. The server persists the modified progression/status fields.

## Severity
- Level: `medium`
- Priority: `P2`
- Rationale: The route is reachable by any player for owned characters and changes GM-controlled progression/status state, but it does not grant application admin privileges.

## Remediation
Use a player update schema that excludes `xp`, `level`, and `is_dead`; keep progression and revive mutations on admin routes with explicit role checks.

## Suggested Tests
- Assert normal player PATCH requests cannot change `xp`, `level`, or `is_dead`.
- Assert admin XP and revive endpoints continue to update those fields.
```

## 4. [Security] Stored attack damage formula can allocate unbounded dice rolls

```markdown
## Summary
A player-controlled attack `damage` string is parsed into dice count and sides, then the damage roll route allocates one random roll per count without bounds.

## Source
Repository: `https://github.com/RattusRex/Kral`
Revision: `e9c2f722955b25a27713ea498ead16caf9879282`
Finding ID: `csf_dc2d5b0c7163a53dcf656f97`
Fingerprint: `codex-security/v1:sha256:04da2e7df1e1c1e9c7b658a232c97426a03fad0cd1819fe23542fb5af566e66a`

## Affected Locations
- parser: `app/api/attacks.py:19-22` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/attacks.py#L19-L22
- source: `app/api/attacks.py:95-107` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/attacks.py#L95-L107
- source: `app/api/attacks.py:114-132` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/attacks.py#L114-L132
- sink: `app/api/attacks.py:207-232` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/attacks.py#L207-L232
- source: `app/schemas/character.py:50-59` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/schemas/character.py#L50-L59

## Validation
- Method: bounded FastAPI TestClient PoC
- Evidence: The `roll_oversized_damage` step returned 200 with `roll_count` 5000 from a player-created `5000d1` attack.
- Counterevidence: The PoC intentionally used a bounded count and did not crash the service; larger values follow the same unbounded path.

## Attack Path
1. Log in as a normal player and create or update an owned attack with a very large damage formula.
2. POST to `/api/characters/{id}/attacks/{attack_id}/roll-damage`.
3. The backend creates a list with one random roll per attacker-supplied count and stores/renders the result.

## Severity
- Level: `medium`
- Priority: `P2`
- Rationale: Any authenticated player can trigger CPU/memory work on the API service. Impact is availability, bounded by authentication and per-request execution.

## Remediation
Apply maximum dice count, sides, and total response-size limits to attack damage formulas before rolling, matching or reusing the chat dice constraints.

## Suggested Tests
- Assert large damage formulas are rejected at create/update or roll time.
- Assert normal D&D damage formulas still roll successfully.
```

## 5. [Security] Manual downtime entries accept unbounded day spans

```markdown
## Summary
The manual downtime route checks only `days > 0` and a valid start date, then calendar summaries expand each busy day with `range(entry.days)`.

## Source
Repository: `https://github.com/RattusRex/Kral`
Revision: `e9c2f722955b25a27713ea498ead16caf9879282`
Finding ID: `csf_bc8c0a72d0653d1ec0706067`
Fingerprint: `codex-security/v1:sha256:1fdc977e01577070e9fa2349c70fd8cad37b5313c80ffa85b14eee56b9631e5d`

## Affected Locations
- source: `app/schemas/character.py:105-108` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/schemas/character.py#L105-L108
- root_control: `app/api/calendar.py:185-211` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/calendar.py#L185-L211
- entrypoint: `app/api/calendar.py:228-259` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/api/calendar.py#L228-L259
- sink: `app/core/calendar.py:35-41` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/core/calendar.py#L35-L41
- sink: `app/core/calendar.py:116-125` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/core/calendar.py#L116-L125

## Validation
- Method: bounded FastAPI TestClient PoC plus static trace
- Evidence: The `oversized_downtime` step returned 200 for a 10,000-day entry. Static code shows `range(entry.days)` is used for each summary.
- Counterevidence: The bounded PoC did not cause visible latency; the risk depends on larger values and repeated calendar access.

## Attack Path
1. Log in as a normal player and select an owned character.
2. POST a downtime entry with a very large `days` value and a valid past start date.
3. The server commits the entry and calendar summaries later expand each day in the stored span.

## Severity
- Level: `medium`
- Priority: `P2`
- Rationale: A remote authenticated player can persist a large entry that repeatedly creates CPU/memory work for calendar views. Impact is availability and scoped to calendar processing.

## Remediation
Set a maximum downtime span and reject entries whose end date exceeds the active calendar window or a campaign-approved cap; avoid expanding days outside the active window.

## Suggested Tests
- Assert oversized downtime spans are rejected.
- Assert ordinary downtime entries still reduce free days correctly.
```

## 6. [Security] Backend falls back to a committed PostgreSQL credential

```markdown
## Summary
If `DATABASE_URL` is unset, the backend and dev launcher use a committed PostgreSQL URL containing the password `GalU5TA1`.

## Source
Repository: `https://github.com/RattusRex/Kral`
Revision: `e9c2f722955b25a27713ea498ead16caf9879282`
Finding ID: `csf_6e6041873a58f334609ef647`
Fingerprint: `codex-security/v1:sha256:f39dfabe6e0f8608c25b2c195090876b39fba2476a24924e9f3d7c6e58e89e90`

## Affected Locations
- root_control: `app/db/database.py:14-16` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/db/database.py#L14-L16
- sink: `app/db/database.py:29-29` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/app/db/database.py#L29
- supporting_default: `scripts/dev.mjs:17-19` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/scripts/dev.mjs#L17-L19
- documentation: `README.md:96-96` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/README.md#L96
- counterevidence: `docker-compose.yml:43-45` - https://github.com/RattusRex/Kral/blob/e9c2f722955b25a27713ea498ead16caf9879282/docker-compose.yml#L43-L45

## Validation
- Method: static config trace
- Evidence: `app/db/database.py` uses the fallback when `DATABASE_URL` is absent; `scripts/dev.mjs` carries the same default.
- Counterevidence: The host is localhost, README calls it a development database, `.env.example` uses placeholders, and Docker composes `DATABASE_URL` from required `POSTGRES_PASSWORD`.

## Attack Path
1. Read the repository or README to learn the default PostgreSQL password.
2. Find a direct/dev deployment, exposed local database, or reused database password where `DATABASE_URL` was omitted.
3. Authenticate to PostgreSQL and read or modify application tables.

## Severity
- Level: `low`
- Priority: `P3`
- Rationale: The secret is real and committed, but repository evidence frames it as a local development default and Docker production paths require explicit credentials.

## Remediation
Remove the hardcoded password fallback; require `DATABASE_URL` or generate a clearly local-only development secret outside source control.

## Suggested Tests
- Assert importing database config without `DATABASE_URL` fails closed outside a named test/dev mode.
- Assert dev setup documentation uses `.env.example` placeholders rather than a reusable password.
```
