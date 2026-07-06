# Security Audit Report For Issue 77

Source issue: https://github.com/RattusRex/Kral/issues/77

Prepared branch: `issue-77-6187f28aec49`

This report summarizes the repository-wide security audit of the FastAPI backend,
React frontend, and Docker deployment configuration. Each validated vulnerability
has been opened as a separate GitHub issue so it can be fixed and closed
independently.

## Scope

Reviewed areas:

- Authentication, registration, JWT creation, and current-user loading.
- Player-owned character, inventory, shop, chat, calendar, and attack APIs.
- Admin APIs for XP, currency, karma, roles, item grants, revives, and state edits.
- SQLAlchemy models, Pydantic schemas, and request validation boundaries.
- React frontend rendering and API client behavior.
- Docker Compose, nginx, README deployment paths, and development scripts.

Threat classes checked:

- SQL injection and request-controlled raw SQL.
- XSS through stored or reflected user content.
- CSRF with the bearer-token authentication model.
- Command injection, path traversal, SSRF, and unsafe deserialization.
- Authorization bypasses, ownership bypasses, and IDOR.
- Business-logic abuse in campaign economy and character progression.
- Rate limiting and abuse controls.
- DoS through unbounded input or expensive computation.
- Sensitive information and deployment configuration exposure.

## Validated Findings

| ID | Severity | Finding | Tracking issue |
| --- | --- | --- | --- |
| AUTH-001 | Medium | Login and registration lack abuse controls | https://github.com/RattusRex/Kral/issues/79 |
| CHAR-001 | Medium | Player-controlled `investigation` can bypass shop search rules | https://github.com/RattusRex/Kral/issues/80 |
| CHAR-002 | Medium | Character creation accepts arbitrary level values | https://github.com/RattusRex/Kral/issues/81 |
| SHOP-001 | Medium | Shop quote confirmation is not atomic | https://github.com/RattusRex/Kral/issues/82 |
| DOS-001 | Medium | Persisted chat messages and inventory notes are unbounded | https://github.com/RattusRex/Kral/issues/83 |
| DOS-002 | Low | Overlapping downtime entries amplify calendar computation cost | https://github.com/RattusRex/Kral/issues/84 |
| UI-001 | Medium | SPA responses lack anti-framing headers | https://github.com/RattusRex/Kral/issues/85 |
| DEPLOY-001 | Low | Default compose deployment publishes FastAPI directly | https://github.com/RattusRex/Kral/issues/86 |

## Finding Details

### AUTH-001: Login And Registration Lack Abuse Controls

Severity: Medium

Tracking issue: https://github.com/RattusRex/Kral/issues/79

Representative code:

- `app/api/users.py:37` public registration endpoint.
- `app/api/users.py:67` bcrypt hashing on registration.
- `app/api/users.py:92` public login endpoint.
- `app/api/users.py:108` password verification on login.

The authentication endpoints are public and do not apply rate limits, account
lockout, exponential backoff, registration quotas, invite controls, or
password-length limits before bcrypt work. An unauthenticated attacker can brute
force known usernames such as `admin`, create many accounts, and force repeated
password hashing work.

Recommended fix: add IP and username/email keyed rate limiting, failed-login
backoff or temporary lockout, registration throttling or invites, password size
bounds before bcrypt, and audit logging for repeated failures.

### CHAR-001: Player-Controlled Investigation Bypasses Shop Rules

Severity: Medium

Tracking issue: https://github.com/RattusRex/Kral/issues/80

Representative code:

- `app/schemas/character.py:23` unbounded `CharacterCreate.investigation`.
- `app/schemas/character.py:42` player-editable `investigation`.
- `app/api/characters.py:85` submitted value stored during creation.
- `app/api/characters.py:177` player patch applies allowed fields directly.
- `app/api/inventory.py:507` shop modifier reads `character.investigation`.
- `app/api/inventory.py:564` shop success uses `d20 + modifier >= DC`.

Players can set arbitrary `investigation` values on their own characters. The
shop search code then trusts that value as the search modifier, allowing a player
to reliably pass marketplace rarity DCs and bypass intended campaign economy
rules.

Recommended fix: bound the stat to campaign-valid values or separate
player-editable sheet data from GM-approved mechanical modifiers before using it
in automation.

### CHAR-002: Character Creation Accepts Arbitrary Levels

Severity: Medium

Tracking issue: https://github.com/RattusRex/Kral/issues/81

Representative code:

- `app/schemas/character.py:11` unbounded `CharacterCreate.level`.
- `app/api/characters.py:90` submitted level stored directly.
- `app/api/admin.py:151` XP grant loop assumes sane level values.
- `app/api/admin.py:213` admin patch clamps level, but player creation does not.

Players can create characters with arbitrary high, zero, or negative levels. High
levels bypass the progression model, while malformed low values can stress admin
XP grant logic that advances levels in a loop.

Recommended fix: validate creation levels with lower and upper bounds, or set the
initial level server-side. Harden XP grants against legacy malformed rows and add
a database check constraint where possible.

### SHOP-001: Shop Quote Confirmation Is Not Atomic

Severity: Medium

Tracking issue: https://github.com/RattusRex/Kral/issues/82

Representative code:

- `app/models/inventory.py:154` quote consumption uses a boolean flag.
- `app/api/inventory.py:699` quote lookup checks `is_consumed`.
- `app/api/inventory.py:1080` buy confirmation endpoint.
- `app/api/inventory.py:1111` sell confirmation endpoint.

The buy and sell endpoints check whether a quote is consumed, then later mutate
inventory/currency and mark the quote consumed. There is no row lock,
compare-and-set update, version check, or idempotency guard. Concurrent
confirmation requests can observe the same quote as unconsumed and settle it more
than once.

Recommended fix: consume quotes with an atomic conditional update or row lock in
the same transaction, then re-check currency and item ownership under that
transaction.

### DOS-001: Persisted Chat And Inventory Text Is Unbounded

Severity: Medium

Tracking issue: https://github.com/RattusRex/Kral/issues/83

Representative code:

- `app/schemas/chat.py:6` unbounded chat message content.
- `app/api/chat.py:83` chat validation only rejects empty content.
- `app/api/chat.py:148` chat content stored directly.
- `app/schemas/inventory.py:42` unbounded inventory notes.
- `app/api/inventory.py:819` notes stored directly.
- `docker-compose.yml:51` backend port published directly, bypassing nginx body
  limits.

Authenticated users can persist very large chat messages and inventory notes.
Repeated writes can grow the database and force large response rendering for
other users or admins. The nginx `client_max_body_size` setting is not sufficient
because the default compose file also publishes the backend directly.

Recommended fix: add Pydantic `max_length` validation, backend request-body
limits, per-user write quotas, and retention or pruning for chat history.

### DOS-002: Downtime Entries Amplify Calendar Work

Severity: Low

Tracking issue: https://github.com/RattusRex/Kral/issues/84

Representative code:

- `app/schemas/character.py:120` downtime entry creation schema.
- `app/api/calendar.py:263` validates windows but not overlap count.
- `app/api/calendar.py:382` player downtime creation endpoint.
- `app/core/calendar.py:35` calendar summary expands entries by day.
- `app/api/admin.py:183` admin character listing serializes calendar summaries.

Date spans are bounded, but the application does not cap duplicate or overlapping
downtime entries per character/day. A player can create many overlapping entries
and increase calendar summary cost, especially when admin views serialize
summaries for many characters.

Recommended fix: reject or cap overlapping entries, add per-character/day limits,
and avoid eager calendar summary expansion in broad admin list endpoints.

### UI-001: Anti-Framing Headers Are Missing

Severity: Medium

Tracking issue: https://github.com/RattusRex/Kral/issues/85

Representative code:

- `docker/nginx.conf:16` nginx serves the SPA and proxies API requests.
- `docker/nginx.conf:44` cache headers exist, but no anti-framing header exists.
- `app/src/api.ts:262` authenticated requests use the browser-held bearer token.
- `app/src/main.tsx:1541` admin UI exposes state-changing actions.

The deployed SPA can be framed by another site because responses do not set
`Content-Security-Policy: frame-ancestors` or `X-Frame-Options`. A logged-in
victim can be tricked into clicking framed authenticated UI actions.

Recommended fix: set `Content-Security-Policy: frame-ancestors 'self'` or
`'none'`, plus `X-Frame-Options` as a legacy fallback, using nginx `add_header
... always`.

### DEPLOY-001: Backend Port Is Published Directly

Severity: Low

Tracking issue: https://github.com/RattusRex/Kral/issues/86

Representative code:

- `docker-compose.yml:51` backend service publishes `8000:8000`.
- `docker/nginx.conf:20` nginx is configured as the frontend/API proxy.
- `docker/nginx.conf:23` nginx applies request size limits.
- `README.md:208` documentation points directly to `http://localhost:8000/docs`.

The default compose stack exposes FastAPI directly while nginx is also configured
as the intended public frontend/API proxy. Direct backend access bypasses
nginx-layer controls such as request-size limits, headers, and any future
proxy-only protections.

Recommended fix: make the backend internal-only in the default/production compose
file, move host port publishing to a development override, and document proxy-only
production traffic.

## Suppressed Or Below-Threshold Findings

- SQL injection: reviewed request-controlled database paths use SQLAlchemy filters
  or hardcoded migration SQL. No request data reaches raw SQL in the reviewed
  scope.
- XSS: reviewed frontend paths render user-controlled text through React text
  nodes. No `dangerouslySetInnerHTML` or equivalent HTML execution sink was found.
- CSRF: authenticated API calls use bearer `Authorization` headers, not ambient
  cookies. Cross-site forms cannot attach the token by default.
- Legacy `app/api/shop.py`: not reportable because the router is not included from
  `app/main.py`; active shop routes are implemented in `app/api/inventory.py`.
- Development Vite host settings: below threshold because they affect the dev
  server, not the production nginx deployment.
- JWT in localStorage: noted as hardening work, but not reported as a standalone
  vulnerability because no XSS execution sink was found during this audit.
- Frontend admin route visibility: backend admin dependencies enforce
  authorization, so missing client-side role hiding is not an authorization bypass.

## Local Scan Artifacts

Detailed local artifacts were written under:

`/tmp/codex-security-scans/gh-issue-solver-1783340582668/ae4e04ae9adb_20260706T122502Z/`

The local artifact set includes:

- Threat model and seed research.
- Per-file work ledger.
- Raw and deduplicated candidate lists.
- Coverage ledger.
- Per-finding validation and attack-path reports.
- Final scan report.
