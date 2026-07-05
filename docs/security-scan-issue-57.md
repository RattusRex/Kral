# Codex Security Scan For Issue 57

Repository: `https://github.com/RattusRex/Kral`
Reviewed revision: `e9c2f722955b25a27713ea498ead16caf9879282`
Scan ID: `e9c2f722955b25a27713ea498ead16caf9879282_20260705T162342Z`

The requested deep/max-intellect profile was blocked by the available Codex runtime configuration (`agents.max_depth` was 1, deep scan requires at least 2). I proceeded with the supported repository-wide Codex Security scan and full-file review coverage.

## Coverage

- Reviewed files: 35/35 from `artifacts/02_discovery/deep_review_input.jsonl`.
- Validation: static trace plus bounded FastAPI TestClient PoC for player-reachable routes.
- Application code changes: none.

## Reportable Findings

| # | Severity | Priority | Finding | CWE |
| --- | --- | --- | --- | --- |
| 1 | medium | P2 | Players can self-modify karma through authenticated `/me` endpoints | CWE-862 |
| 2 | medium | P2 | Players can mint inventory currency and items outside shop/admin flows | CWE-862 |
| 3 | medium | P2 | Player character update can self-grant progression and clear death state | CWE-862, CWE-915 |
| 4 | medium | P2 | Stored attack damage formula can allocate unbounded dice rolls | CWE-400 |
| 5 | medium | P2 | Manual downtime entries accept unbounded day spans | CWE-400 |
| 6 | low | P3 | Backend falls back to a committed PostgreSQL credential | CWE-798 |

## Suppressed / Not Filed

- `startup-admin-username-owner-promotion`: Suppressed/deferred: exploitable only if an attacker already controls a persisted `admin` username row before startup. Fresh DB startup seeds admin before registration and no normal delete/demote path proving this precondition was found.
- `character-transfer-target-enumeration`: Suppressed as product-intent ambiguity: transfer UI/tests intentionally use global transfer targets and cross-player transfers. Metadata is limited to character transfer directory fields.
- `network-exposed-vite-dev-proxy`: Suppressed as dev-only: production Docker serves static frontend/nginx, backend APIs still require JWT, and no production deployment uses Vite dev server in the repository.
- `frontend-token-storage-without-xss-sink`: Suppressed: token is in localStorage, but no `dangerouslySetInnerHTML`, `innerHTML`, `eval`, `new Function`, `javascript:` URL, or equivalent attacker-controlled browser execution sink was found.

## Runtime Validation Evidence

The bounded PoC returned:

- `self_karma_add`: status 200, karma 77.
- `self_currency_add`: status 200, currency increased.
- `self_item_add`: status 200, item `Unreviewed Wand` added.
- `self_character_progression_patch`: status 200, level 20, `is_dead=false`.
- `roll_oversized_damage`: status 200, 5000 rolls returned.
- `oversized_downtime`: status 200 for 10,000 days.

Full validation output is in the scan bundle at `artifacts/05_findings/validation_artifacts/runtime_poc_output.json`.

## GitHub Issue Creation

Exact proposed issue payloads are in `docs/security-issue-previews-issue-57.md` and in the scan bundle under `artifacts/05_findings/issue_previews/`. They were not created yet because the Codex Security tracking workflow requires approval of the exact payloads before writing GitHub issues.

Tracking readiness:

- Destination `RattusRex/Kral` has issues enabled.
- Current GitHub token permission on `RattusRex/Kral`: `READ`, so upstream issue creation is not available from this environment without additional repository permission.
- Exact duplicate searches for all six finding IDs returned no matches on 2026-07-05.
