# Gate 0 Summary — Discovery

**Date:** 2026-07-04  
**Status:** Complete  
**Code written:** No (discovery only)

---

## Completed

* Inspected the Frappe bench and existing `credit_management` app
* Confirmed target stack: **Frappe v14.101.1**, **bench 5.25.9**, **MariaDB**, site **`jomveo`**
* Mapped current app layout, DocTypes, integration points, and gaps vs. the production spec
* Identified conflicts with the earlier MVP and with `dummy_website`'s separate credit wallet
* Produced a gated implementation plan and risk register
* **Prerequisite completed:** `credit_management` installed on `jomveo` before refactor

---

## Environment findings

| Item | Value |
|---|---|
| Frappe version | `14.101.1` (version-14) |
| Bench version | `5.25.9` |
| Site | `jomveo` |
| DB | MariaDB |
| Apps in `sites/apps.txt` | `frappe`, `credit_management`, `testing`, `doppio`, `dummy_website` |
| Installed on `jomveo` (post Gate 0) | `frappe`, `dummy_website`, `credit_management` |
| Git | No git repo in bench or app |

---

## Existing MVP inventory (pre-refactor)

**DocTypes on `jomveo`:**

| DocType | Notes |
|---|---|
| `Credit Account` | Party + limit model — conflicts with spec |
| `Credit Transaction` | Direct balance mutation — must be replaced |
| `Credit Management Settings` | MVP singleton — replaced by `Credit Settings` in Gate 2 |

**Workspace:** `Credit Management` (public)

**Anti-patterns identified:**

* Balances mutated in `utils/credit.py` and DocType `on_submit` handlers
* No ledger, reservations, idempotency, service layer, or public API

---

## Architecture gap analysis

| Spec principle | MVP state | Required action |
|---|---|---|
| Ledger is source of truth | Balances on `Credit Account` | Append-only `Credit Ledger Entry` |
| Reservations for async jobs | None | `Credit Reservation` + services |
| Idempotency | None | Unique keys on ledger/reservations |
| Public API only | None | `credit_management.api` |
| Service-layer logic | DocType controllers | `services/*` modules |
| Generic / reusable | Party/lending model | Owner-agnostic accounts + `Credit Type` |

---

## Proposed gate plan (Gates 1–10)

1. Architecture Scaffold  
2. Core Ledger  
3. Reservations  
4. Expiry Lots  
5. Transfers and Adjustments  
6. Permissions and Workspace  
7. Reports and Reconciliation  
8. Integration Layer  
9. Documentation and Example Integration  
10. Full Verification  

---

## Files changed

* **None** (Gate 0 is discovery only)

---

## Tests run

```bash
# No tests run — Gate 0 prohibits code changes
```

### Test result

* **Skipped** — discovery gate only

---

## Install commands (prerequisite)

```bash
bench pip install -e apps/credit_management
bench --site jomveo install-app credit_management
bench --site jomveo migrate
bench --site jomveo clear-cache
```

**Install verified:**

* DocTypes: `Credit Account`, `Credit Transaction`, `Credit Management Settings`
* Workspace: `Credit Management`
* Settings singleton initialized

---

## Risks or unresolved decisions

1. **MVP schema replacement** — Name collisions with new `Credit Account`; migration patch required in Gate 2
2. **No git** — Milestones are patch-based until repo initialized
3. **`Company` DocType absent** — Optional field; ERPNext not installed on bench
4. **`dummy_website` parallel credit** — Separate wallet system; integrate via API in Gate 9
5. **Concurrency** — Row locks + idempotency required in Gates 2–3
6. **Scope size** — Strict gate stops required

---

## Next recommended gate

**Gate 1: Architecture Scaffold**