# D&D Compendium Integration Research

## Goal

Enable automatic lookup of D&D 5e reference data (classes, subclasses, races, spells, items,
monsters, abilities) inside the Epoch of Catastrophe Assistant.

## Candidate Data Source: 5etools

Project page: https://github.com/5etools-mirror-2/5etools-mirror-2  
License: Custom non-commercial; data files carry their own SRD / third-party licenses.

The repository ships a structured JSON dataset under `data/` covering:

| Directory       | Contents                                |
|----------------|-----------------------------------------|
| `data/class/`  | Class features, hit dice, proficiencies |
| `data/race/`   | Racial traits, speed, ability bonuses   |
| `data/spell/`  | Spell levels, components, damage        |
| `data/item/`   | Weapons, armor, magic items             |
| `data/bestiary/` | Monster stats and actions             |

Data is well-structured JSON and is machine-readable without a server dependency.

## Proposed Architecture

### Option A – Bundled static JSON (recommended for MVP)

1. Copy only the SRD-licensed subset of 5etools data files into `app/static/compendium/`.
2. Serve them at `/static/compendium/<file>.json` via FastAPI's `StaticFiles` mount.
3. The React frontend fetches and caches the relevant file on demand (e.g. spells when the
   spell-lookup UI is opened).
4. A lightweight search utility in `api.ts` filters the cached data client-side.

Pros: zero additional dependencies, works offline, simple deployment.  
Cons: data does not auto-update; JSON payload can be large (filter to SRD only first).

### Option B – On-demand backend proxy

1. Add a `/api/compendium/{category}` endpoint in FastAPI.
2. On first request the backend fetches the relevant JSON from 5etools' GitHub raw URL,
   caches it in a local file or Redis entry with a TTL (e.g. 7 days).
3. The endpoint exposes a search parameter so only matching entries are returned.

Pros: data can be refreshed without a redeploy.  
Cons: requires network access at runtime, adds backend complexity.

### Option C – Open5e REST API

The Open5e project (https://open5e.com) exposes a public REST API covering the official SRD.
No license concerns; data is Open Game License content.

Example: `GET https://api.open5e.com/spells/?name=fireball&format=json`

Pros: no data hosting, always up to date, clean REST interface.  
Cons: external dependency; latency on each lookup; requires internet from the server or client.

## Recommendation

Start with **Option A** for SRD-licensed data and **Option C** for anything beyond the SRD.

### Implementation steps

1. Identify which SRD JSON files from 5etools are needed (classes, races, spells, items).
2. Add a `app/static/compendium/` folder with those filtered files.
3. Mount it with `app.mount("/static", StaticFiles(directory="app/static"))`.
4. Add a `CompendiumPage` React component with a search box that queries the cached JSON.
5. Wire up auto-complete on the character form for `class_name`, `race`, and future spell
   fields.
6. For non-SRD lookups add an optional backend proxy to Open5e.

## Open Questions

- Should GMs be able to add custom homebrew entries to the compendium?
- Are spell slots / prepared spells in scope for the character sheet?
- Does the campaign use any 5etools-only content that is not in the SRD?
