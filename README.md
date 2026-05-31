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
4. Create PostgreSQL database `EpohaTruda` or set a custom `DATABASE_URL`:
   ```bash
   export DATABASE_URL="postgresql://postgres:password@localhost:5432/EpohaTruda"
   ```
5. Run FastAPI:
   ```bash
   uvicorn app.main:app --reload
   ```

Swagger documentation: http://localhost:8000/docs

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

`npm run dev` starts FastAPI on `http://localhost:8000`, waits for it to be reachable, then starts Vite. If `DATABASE_URL` is not set, this command uses a local SQLite database at `dev.db` so login and registration work without extra setup.

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
npm run build
```
