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
   You can either export it in your shell:
   ```bash
   export DATABASE_URL="postgresql://postgres:password@localhost:5432/EpohaTruda"
   ```
   or copy `.env.example` to `.env` and edit it (the backend and `npm run dev`
   both load `.env` automatically):
   ```bash
   cp .env.example .env
   ```
5. Run FastAPI:
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

The Vite dev server proxies `/api` requests to `http://127.0.0.1:8000`. To use a different API target, set `VITE_API_TARGET`.

If you want to run services separately:

```bash
npm run dev:backend
npm run dev:frontend
```

## Test Admin Account

Username: `admin`

Password: `admin123`

The account is created automatically when the backend starts.

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
