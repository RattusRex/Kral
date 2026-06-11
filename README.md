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
5. Run FastAPI (development):
   ```bash
   uvicorn app.main:app --reload
   ```

Swagger documentation: http://localhost:8000/docs

Notable protected API routes:

- `GET /api/leaderboard` returns users ranked by karma.
- `GET/POST /api/chat/messages` stores general chat messages and `/r` roll commands.
- `POST /api/dice/roll` rolls formulas such as `/r 2d6` or `/r 1d37` and stores the result in the rolls channel.
- `PATCH /api/characters/{id}/inventory/notes` saves free-form inventory notes.
- `GET/POST /api/characters/{id}/attacks` manages attack rows, and `POST /api/characters/{id}/attacks/{attack_id}/roll` records attack rolls.
- `GET /api/shop/magic-items` searches `magicvariants.json` and returns shop-eligible common, uncommon, and rare magic items.
- `POST /api/admin/users/{id}/role` lets an **owner** assign a user role (`owner`, `admin`, or `player`).

## User Roles

Access is controlled by three roles:

- **👑 Owner** — full control, including managing users and assigning roles, plus everything an admin can do.
- **🛠 Admin** — game-master tools: add/remove karma, grant items and currency, view logs, and manage game data. Cannot manage roles.
- **🎮 Player** — default role for new accounts: manage own characters, chat, roll dice, and use the inventory.

The seeded `admin` account is an **owner**. New accounts are created as **players**. Only an owner can change another user's role from the admin panel.

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

`npm run dev` starts FastAPI on `http://localhost:8000`, waits for it to be reachable, then starts Vite. It loads variables from a project-level `.env` file automatically, so defining `DATABASE_URL` there is enough. If `DATABASE_URL` is not set in the environment or in `.env`, it falls back to the default development database `postgresql://postgres:GalU5TA1@localhost:5432/EpohaTruda` (which must be running locally).

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
