# Decision Log

## Gate 1 — Architecture Scaffold

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D-001 | Python import paths | `credit_management.api`, `credit_management.services.*` | Matches Frappe app package layout |
| D-002 | DocType module path | `credit_management/credit_management/credit_management/doctype/` | Required for Frappe module sync |
| D-003 | MVP DocTypes on jomveo | Migrate via `patches/v1_0/` in Gate 2 | App is installed; avoid silent data loss |
| D-004 | `Company` field | Optional Link; non-mandatory on Frappe-only bench | No ERPNext `Company` DocType detected |
| D-005 | Amount storage | Float + per-type `decimal_precision` | Frappe v14 Currency/Float compatibility |
| D-006 | Row locking | `SELECT ... FOR UPDATE` in services | MariaDB-safe concurrent balance updates |
| D-007 | Ledger immutability | Submitted entries; reversals via new rows | Append-only audit requirement |
| D-008 | Idempotency | Unique key on ledger/reservation when provided | Retry-safe async integrations |
| D-009 | Negative balance | Default deny; override per Credit Type | Safer default for reusable platform |
| D-010 | Consuming app integration | `credit_management.api` only | Prevents tight coupling and balance drift |
| D-011 | Scheduler wiring | Stub tasks in Gate 1; logic from Gate 3+ | Safe scaffold without side effects |
| D-012 | Git workflow | Recommend `git init` in app folder | Bench root is not a git repo today |

## Gate 1.5 — Legacy MVP Cleanup

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D-013 | MVP DocTypes | **Removed** — no backward compatibility | User decision; Gate 2 recreates production models |
| D-014 | MVP tables | **Dropped** `tabCredit Account`, `tabCredit Transaction` | Obsolete schema; idempotent patch; frees names for Gate 2 |
| D-015 | MVP singles | **Deleted** `Credit Management Settings` singles rows | Replaced by `Credit Settings` in Gate 2 |
| D-016 | MVP workspace | **Replaced** with placeholder (no DocType links) | Avoid broken sidebar links until Gate 2/6 |
| D-017 | `utils/credit.py` | **Removed** | Direct balance mutation violates ledger architecture |
| D-018 | `install.after_install` | **No-op** until Gate 2 seeding | No MVP settings to initialize |