# Epoch of Catastrophe Assistant

Prototype web application for D&D 2014 open-table bookkeeping: characters, inventory, currency, karma, shop searches, and GM administration.

## Backend Setup

1. Install Python 3.11+.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create PostgreSQL database `EpohaTruda` or set a custom `DATABASE_URL`.
   Copy `.env.example` to `.env` and fill in all required values:
   ```bash
   cp .env.example .env
   ```
   The required variables are:
   - `DATABASE_URL` — PostgreSQL connection string.
   - `SECRET_KEY` — secret used to sign JWT tokens. Generate one with:
     ```bash
     python -c "import secrets; print(secrets.token_hex(32))"
     ```
   - `ADMIN_PASSWORD` — password for the default `admin` owner account.
   - `ALLOWED_ORIGINS` — comma-separated list of allowed CORS origins (e.g. `https://yourdomain.com`).
   - `FRONTEND_URL` — public frontend origin placed in confirmation links.
   - `EMAIL_BACKEND` — use `console` locally or `smtp` with the SMTP variables from `.env.example` in production.
5. Run FastAPI (development):
   ```bash
   uvicorn app.main:app --reload
   ```

Swagger documentation: http://localhost:8000/docs

Notable protected API routes:

- `GET /api/leaderboard` returns users ranked by karma.
- `GET/POST /api/chat/messages` stores general chat messages and `/r` roll commands.
- `DELETE /api/chat/messages/{id}` lets an administrator, head administrator, or owner remove any chat message; players are rejected by the backend.
- `GET/POST /api/game-recruitments` lists game announcements and lets administrators publish them. Players enroll an owned living character through `/applications`; only the announcement author can publish the selected roster through `/participants`. Enrollment and selection notices are persisted in the announcement chat.
- `POST /api/dice/roll` rolls formulas such as `/r 2d6` or `/r 1d37` and stores the result in the rolls channel.
- `PATCH /api/characters/{id}/inventory/notes` saves free-form inventory notes.
- `GET/POST /api/characters/{id}/attacks` manages attack rows, and `POST /api/characters/{id}/attacks/{attack_id}/roll` records attack rolls.
- `GET /api/shop/magic-items` searches `magicvariants.json` and returns shop-eligible common, uncommon, and rare magic items.
- `POST /api/admin/users/{id}/role` lets an **owner** assign any user role (`owner`, `head_admin`, `admin`, or `player`). A **head admin** may use the same endpoint to manage `admin` and `player` roles only.
- `GET /api/content-pages/{server-rules|approved-homebrew}` returns the ordered informational blocks for authenticated users. Administrative roles may create, edit, delete, and reorder blocks on these pages.
- `GET /api/characters/{id}/calendar` and `POST /api/characters/{id}/calendar/downtime` let players view their character calendar and **add** character busy days. `PATCH`/`DELETE /api/characters/{id}/calendar/downtime/{entry_id}` edit or remove entries and are **restricted to administrators** — a player request is rejected with `403`. Admins may manage the calendar of *any* character.
- `POST /api/characters/{id}/calendar/work` reserves a work period, calculates earnings from the campaign tool-proficiency table, credits the character wallet, and records the operation in the finance log. Players cannot cancel completed work. Administrators may delete it to release the occupied days; the exact credited income is deducted atomically and the correction is recorded in the calendar audit log. Deletion is rejected if the character has already spent that income.
- Manual calendar entries cannot overlap another entry for the same character or unit calendar. Duplicate and intersecting spans return `409 Conflict`; adjacent spans and the same dates on separate actor calendars remain valid.
- `GET /api/characters/{id}/calendar/agents/{personal_hireling|simulacrum}` shows a granted unit's own calendar. `POST`/`PATCH`/`DELETE /api/characters/{id}/calendar/agents/{agent}/downtime...` are admin-only manual busy-day controls for those units.
- `GET /api/admin/calendar-logs` returns the audit trail of administrative calendar changes (who, which character, action type, timestamp), filterable by `character_id`, `user_id`, `action`, and date range.
- `GET /api/admin/grant-logs` returns the administrator resource-grant audit trail (karma, XP, gold, and items), filterable by player, character, administrator, operation type, and date. Every grant request requires a non-empty `reason`.
- `POST /api/karma-shop/xp`, `/purchases`, and `/resurrect` atomically spend the authenticated player's karma on XP, persistent goods/openers, or an eligible dead character's resurrection. `GET /api/karma-shop/purchases` returns the player's saved goods and openers.
- `GET /api/admin/karma-shop-logs` returns the complete Karma Shop audit trail, including the user, optional character, purchase type, cost, timestamp, and character level captured for character purchases.
- `GET /api/admin/characters` includes each character's assembled date and free-day totals, plus separate free-day totals for a personal hireling and simulacrum when those units are enabled.
- `PATCH /api/admin/characters/{id}` lets administrators correct a character's appearance date; calendar totals are recalculated from that date. Only owners and head administrators may delete characters.

## Calendar Permissions

The character calendar (busy/free-day tracking) keeps the game timeline
immutable for players so already-spent time cannot be rewritten:

- **🎮 Player** — may view their character calendar, free days and busy-day
  history, and **add** character busy days, but **cannot** delete or edit
  existing entries. A player cannot grant, remove, or manually spend personal
  hireling or simulacrum time.
- **🛠 Admin / 🛡 Head Admin / 👑 Owner** — may add, edit and delete busy days
  for **any** character, personal hireling, or simulacrum in order to correct
  calendar mistakes.

These rules are enforced on the backend, so hiding the buttons in the UI is not
the only safeguard — a direct API call from a player is rejected. Every
administrative change (create, edit, delete) is written to a calendar audit log
recording who acted, on which character, the action type, and the timestamp.

## Shop Search Actors

Market searches can be performed by four actors:

| Actor | Spends days | Spends whose days | Gold cost |
| --- | --- | --- | --- |
| Character | yes | the character's own calendar | no |
| Personal hireling | yes | the personal hireling's own calendar | no |
| Simulacrum | yes | the simulacrum's own calendar | no |
| Paid hireling | no | none | hireling daily rate |

The personal hireling and simulacrum each have their own appearance date,
`Расследование` modifier, and busy-day journal. Admins can enable them, edit
these values, and manually add/edit/delete unit busy-day records from the admin
character page. Players cannot self-grant or remove these units. Paid hirelings
are external services: they charge gold for the rolled search duration, but
they never consume character, personal-hireling, or simulacrum free days.

## User Roles

Access is controlled by four roles, from most to least privileged:

- **👑 Owner** — full, unrestricted control, including managing every user, assigning and revoking the head-admin role, plus everything a head admin and admin can do.
- **🛡 Head Admin** (Главный Администратор) — a trusted deputy of the owner. Has every administrative power of the owner **except** managing the owner (cannot change, block, delete, or appoint owners) and cannot grant the `owner` or `head_admin` roles. Can grant and revoke the `admin` role and manage players.
- **🛠 Admin** — game-master tools: add/remove karma, grant items and currency, view logs, and manage game data. Cannot manage roles.
- **🎮 Player** — default role for new accounts: manage own characters, chat, roll dice, and use the inventory.

The hierarchy is:

```text
Owner
└── Head Admin
    └── Admin
        └── Player
```

The seeded `admin` account is an **owner**. New accounts are created as **players**. Owners and head admins can change another user's role from the admin panel, subject to the restrictions above. These restrictions are enforced on the backend, so a direct API call cannot bypass them.

Character sheets support proficiency for each of the six saving throws. A proficient saving throw adds the level-based proficiency bonus automatically. The available classes also include **Егерь** with a `d8` hit die.

Character sheets also support multiclass characters. Each class stores its own level, the first entry is the primary class, and the total character level is always derived from the sum of all class levels (maximum 20). Character owners and administrators can edit this list through their existing character editors.

## Authentication Abuse Controls

The public login and registration endpoints include backend throttles to reduce
brute-force and account-spam abuse:

- new passwords must contain at least 12 characters, including uppercase and
  lowercase letters, a number, and a special character;
- a local deny-list rejects obvious passwords known to be commonly compromised;
  the application does not send passwords to an external breach-checking API;
- passwords longer than 72 UTF-8 bytes are rejected before bcrypt hashing or
  verification;
- repeated failed login attempts are tracked by submitted username/email and by
  client IP, then temporarily return `429 Too Many Requests` with `Retry-After`;
- registration attempts are tracked by client IP before database uniqueness
  checks and bcrypt hashing run;
- repeated failures and blocked attempts are written to the application log.

The default backend limits can be tuned with:

```text
AUTH_LOGIN_FAILURE_LIMIT=5
AUTH_LOGIN_IP_FAILURE_LIMIT=25
AUTH_LOGIN_WINDOW_SECONDS=900
AUTH_LOGIN_LOCKOUT_SECONDS=300
AUTH_REGISTRATION_IP_LIMIT=10
AUTH_REGISTRATION_WINDOW_SECONDS=3600
```

Docker deployments also apply nginx `limit_req` throttling to `/api/login` and
`/api/users` before requests reach FastAPI.

Browser warnings such as “this password appeared in a data leak” are generated
by the browser or password manager when the password entered by a user matches
its breached-password data. Registration sends the password only over HTTPS to
`POST /api/users`; it is bcrypt-hashed before persistence, omitted from API
responses and logs, and never written to local storage, session storage, or
cookies. Only the JWT access token is stored in browser local storage after a
successful login.

## Email Verification

New accounts cannot log in until their email address is confirmed. Registration
sends a 24-hour, single-use link; requesting a new message invalidates the old
link. The application stores only a SHA-256 hash of each random token. For local
development, `EMAIL_BACKEND=console` writes the link to the backend log. Set
`EMAIL_BACKEND=smtp`, `SMTP_HOST`, `SMTP_FROM_EMAIL`, and any provider-specific
SMTP credentials for real delivery. Administrators can see each user's status
and manually confirm an address in the admin panel. Accounts that existed before
this feature are migrated as already verified.

## Persisted Text and Request Limits

The backend rejects request bodies larger than 1 MiB, including requests sent
directly to FastAPI. Persisted user text is also bounded independently:

- chat messages: 2,000 characters;
- inventory notes: 10,000 characters.

Chat history is returned in pages of at most 200 messages. These application
limits do not depend on nginx and therefore also apply during local development.

## Frontend Setup

1. Install Node.js 20+.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development stack:
   ```bash
   npm run dev
   ```

`npm run dev` starts FastAPI on `http://localhost:8000`, waits for it to be reachable, then starts Vite. It loads variables from a project-level `.env` file automatically, so defining `DATABASE_URL` there is enough. If `DATABASE_URL` is not set in the environment or in `.env`, FastAPI startup fails with a configuration error instead of using an implicit database credential.

The Vite dev server proxies `/api` requests to `http://127.0.0.1:8000`. To use a different backend origin, set `VITE_API_TARGET`.

If you want to run services separately:

```bash
npm run dev:backend
npm run dev:frontend
```

## Production Deployment

1. Build the frontend:
   ```bash
   npm run build
   ```
2. Fill in all variables in `.env` (see Backend Setup step 4 above).
   In production `ALLOWED_ORIGINS` must list only your actual domain(s).
   The frontend build reads project-level `.env` values too:
   - same-origin deployments can keep the default `/api` base and proxy `/api` to FastAPI;
   - static builds served locally from `localhost` automatically call `http://127.0.0.1:8000/api`;
   - static builds served from a different origin can set `VITE_API_TARGET=https://backend.example.com`;
   - non-standard API paths can set `VITE_API_BASE_URL=https://backend.example.com/api`.
3. Start the backend without `--reload`:
   ```bash
   npm run start:backend
   # or directly:
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   # or with gunicorn for multi-worker production:
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```
4. Serve the built frontend from `dist/` with nginx (or another static server)
   and proxy `/api` requests to the backend.

For a local production smoke test without a reverse proxy, set `ALLOWED_ORIGINS`
to the static frontend origin, start the backend, build the frontend, and serve `dist/`:

```bash
ALLOWED_ORIGINS=http://localhost:3000 npm run start:backend
npm run build
npx serve -s dist -l 3000
```

> **Security checklist before going live:**
> - `SECRET_KEY` is a long random string (≥32 bytes), not `CHANGE_ME`.
> - `ADMIN_PASSWORD` is a strong unique password, not `CHANGE_ME`.
> - `ALLOWED_ORIGINS` lists only your production domain — no wildcards.
> - `.env` is not committed to git (it is already in `.gitignore`).

## Docker Deployment

The whole stack — PostgreSQL, the FastAPI backend, and the nginx‑served
frontend — can be run with Docker Compose. The browser talks to a single origin
(nginx), which serves the built SPA and reverse‑proxies `/api` to the backend,
so no CORS configuration or API‑URL build flags are needed.

```text
frontend (nginx) ──/api──▶ backend (FastAPI) ──▶ db (PostgreSQL, volume: pgdata)
```

For the full analysis, container architecture, risks, and the rollout plan see
[`docs/docker-plan.md`](docs/docker-plan.md).

### Requirements

- Docker Engine 24+
- Docker Compose v2 (`docker compose`, bundled with recent Docker)

### First run

1. Create your environment file and fill in the secrets:
   ```bash
   cp .env.example .env
   ```
   At minimum set strong values for:
   - `SECRET_KEY` — `python -c "import secrets; print(secrets.token_hex(32))"`
   - `ADMIN_PASSWORD` — password for the seeded `admin` owner account
   - `POSTGRES_PASSWORD` — password for the bundled PostgreSQL service

   When running via Docker you do **not** edit `DATABASE_URL` — the backend
   container builds it from the `POSTGRES_*` values and targets the `db`
   service automatically.

2. Build and start the stack:
   ```bash
   docker compose up -d --build
   ```

3. Open the app:
   - Frontend: <http://localhost:8080>

   The database schema and the `admin` account are created automatically on the
   first backend start. PostgreSQL data is persisted in the named volume
   `pgdata` and survives container recreation.

   The default deployment does not publish FastAPI's port on the host. All
   production traffic should enter through nginx (or a tunnel targeting nginx),
   so nginx request limits and security headers cannot be bypassed.

### Direct backend access for development

If a local debugger or API client needs direct access to FastAPI and Swagger on
<http://localhost:8000>, opt in with the development override:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

Do not use this override for production deployments because it bypasses the
nginx proxy controls.

### Updating after code changes

Rebuild the affected images and restart:

```bash
docker compose up -d --build
```

To stop the stack (data is kept):

```bash
docker compose down
```

To also remove the database volume (**deletes all data**):

```bash
docker compose down -v
```

### Required environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | yes | Signs JWT tokens; backend refuses to start if empty |
| `ADMIN_PASSWORD` | yes | Password for the seeded `admin` owner account |
| `POSTGRES_PASSWORD` | yes | Password for the bundled PostgreSQL service |
| `POSTGRES_USER` | no (default `postgres`) | PostgreSQL user |
| `POSTGRES_DB` | no (default `EpohaTruda`) | PostgreSQL database name |
| `ALLOWED_ORIGINS` | recommended | CORS origins; for local Docker use `http://localhost:8080`, in production your domain |
| `WEB_CONCURRENCY` | no (default `2`) | Number of uvicorn workers in the backend container |
| `CLOUDFLARE_TUNNEL_TOKEN` | only for `tunnel` profile | Cloudflare Tunnel token |

### Production via Cloudflare Tunnel

Publish the stack without opening inbound ports by enabling the optional
`cloudflared` service. Create a tunnel in the Cloudflare Zero Trust dashboard,
point its public hostname at `http://frontend:80`, put the token in `.env` as
`CLOUDFLARE_TUNNEL_TOKEN`, set `ALLOWED_ORIGINS` to your public domain, then:

```bash
docker compose --profile tunnel up -d --build
```

The same `docker-compose.yml` moves unchanged to a VPS or a home server — only
the `.env` (domain and secrets) differs.

## Admin Account

The `admin` account is created automatically on first backend start using the
password from the `ADMIN_PASSWORD` environment variable. Set a strong password
in `.env` before the first run.

## VS Code

Recommended extensions:

- Python
- Pylance
- ESLint
- Prettier

## Tests

```bash
pytest
npm test
npm run build
```
