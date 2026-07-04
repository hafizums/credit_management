# Gate 1 Summary — Architecture Scaffold

**Date:** 2026-07-04  
**Status:** Complete  
**Business logic:** None (stubs only)

---

## Completed

* Added architecture scaffold: `exceptions.py`, `api.py` (13 public stubs), `tasks.py` (5 scheduler stubs)
* Added 11 service module stubs under `credit_management/services/`
* Added test suite entry: `tests/test_gate1_scaffold.py` (5 tests)
* Added documentation skeletons (9 docs) + `docs/decision_log.md` with 12 recorded decisions
* Added `patches/v1_0/README.md` — MVP → production migration plan for installed `jomveo` site
* Added `fixtures/` placeholder for Gate 6 role fixtures
* Wired `scheduler_events` in `hooks.py` (hourly, daily, cron — all stub handlers)
* Updated `README.md` and app description in `hooks.py` / `pyproject.toml`
* **Preserved** existing MVP DocTypes on `jomveo` (no schema changes this gate)

---

## Files changed

### New

| Path | Purpose |
|---|---|
| `credit_management/exceptions.py` | 7 custom exception classes |
| `credit_management/api.py` | 13 public API stubs |
| `credit_management/tasks.py` | 5 scheduler entry stubs |
| `credit_management/services/*.py` | 11 service class stubs |
| `credit_management/tests/test_gate1_scaffold.py` | Gate 1 test suite |
| `credit_management/fixtures/.gitkeep` | Fixtures placeholder |
| `docs/*.md` | 9 documentation skeletons |
| `patches/v1_0/README.md` | MVP migration plan |

### Updated

| Path | Change |
|---|---|
| `credit_management/hooks.py` | Scheduler hooks + app description |
| `README.md` | Project overview + gate status |
| `pyproject.toml` | Updated description |

### Unchanged (intentionally)

* MVP DocTypes: `Credit Account`, `Credit Transaction`, `Credit Management Settings`
* MVP `utils/credit.py` and DocType controllers
* `install.py`, workspace, `patches.txt`

---

## Public API surface (stubs)

All functions in `credit_management.api` raise `NotImplementedError` until Gate 2+:

* `get_or_create_account`
* `get_balance`
* `grant_credits`
* `consume_credits`
* `reserve_credits`
* `consume_reserved_credits`
* `release_reservation`
* `refund_credits`
* `adjust_credits`
* `transfer_credits`
* `expire_credits`
* `reconcile_account`
* `reconcile_all_accounts`

---

## Scheduler tasks (stubs)

| Task | Schedule |
|---|---|
| `release_expired_reservations` | Hourly |
| `reconcile_recent_accounts` | Hourly |
| `expire_credits` | Daily |
| `generate_daily_credit_summary` | Daily |
| `retry_failed_webhooks` | Every 30 min (cron) |

All return `{"status": "stub", "task": "<name>"}` — no side effects.

---

## Tests run

```bash
./env/bin/python -c "import credit_management.api; import credit_management.tasks"

bench --site jomveo set-config allow_tests true
bench --site jomveo run-tests --app credit_management --module credit_management.tests.test_gate1_scaffold
```

### Test result

* **Import smoke test:** Passed (13 API functions)
* **Frappe unit tests:** **5 passed, 0 failed, 0 skipped**

```
.....
----------------------------------------------------------------------
Ran 5 tests in 0.001s

OK
```

**Tests cover:**

* Public API export list
* API stubs raise `NotImplementedError`
* Exception class hierarchy
* Service module imports
* Scheduler task stubs

---

## Decision log highlights

See `docs/decision_log.md` for full list. Key defaults:

| ID | Decision |
|---|---|
| D-003 | MVP DocTypes migrated via `patches/v1_0/` in Gate 2 |
| D-004 | `Company` field optional (no ERPNext on bench) |
| D-006 | Row locking via `SELECT ... FOR UPDATE` |
| D-007 | Ledger immutability; reversals as new entries |
| D-010 | Consuming apps use `credit_management.api` only |

---

## Risks or unresolved decisions

1. **MVP DocTypes still live on `jomveo`** — Gate 2 must run migration patch (name collision on `Credit Account`)
2. **`utils/credit.py` still present** — direct balance mutation; removal planned Gate 2
3. **No git repo** — recommend `git init` before Gate 2
4. **Scheduler stubs wired in hooks** — must not invoke real services until Gate 3+
5. **`allow_tests true`** set on `jomveo` for development

---

## Next recommended gate

**Gate 2: Core Ledger**

Deliverables:

* Migration patch: retire MVP DocTypes on `jomveo`
* New DocTypes: `Credit Type`, `Credit Account` (new schema), `Credit Ledger Entry`, `Credit Settings`
* Services: `account_service`, `ledger_service`, `grant_service`, `consume_service`
* Implement: `get_or_create_account`, `get_balance`, `grant_credits`, `consume_credits` + idempotency
* Tests: account, grant, consume suites