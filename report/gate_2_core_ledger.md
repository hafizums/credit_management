# Gate 2 Summary — Core Ledger

Date: 2026-07-04
Status: Complete

## Completed
- Implemented production DocTypes: `Credit Type`, `Credit Account`, `Credit Ledger Entry`, `Credit Settings`
- Seeded default `GENERAL` credit type and `Credit Settings` singleton via install hook and post-migrate patch
- Implemented service layer: `account_service`, `ledger_service`, `grant_service`, `consume_service`
- Implemented public API: `get_or_create_account`, `get_balance`, `grant_credits`, `consume_credits`
- Added idempotency for grant and consume via unique `idempotency_key` on submitted ledger entries
- Added row locking with `frappe.get_doc(..., for_update=True)` during grant/consume
- Enforced append-only ledger (submittable entries; no amend/cancel; update guard on submitted rows)
- Enforced controlled balance updates (service-layer `db.set_value`; UI direct mutation blocked in controller)
- Updated workspace with production DocType links and shortcuts
- Added Gate 2 test suite (`test_gate2_core_ledger.py`) with 17 tests covering all required scenarios
- Reorganized `patches.txt` into pre/post model sync sections for correct migration ordering

## Files changed

### New
- `credit_management/credit_management/doctype/credit_type/` — Credit Type DocType
- `credit_management/credit_management/doctype/credit_account/` — production Credit Account DocType
- `credit_management/credit_management/doctype/credit_ledger_entry/` — append-only ledger DocType
- `credit_management/credit_management/doctype/credit_settings/` — singleton settings DocType
- `credit_management/tests/test_gate2_core_ledger.py` — Gate 2 test suite
- `credit_management/patches/v1_0/seed_gate2_defaults.py` — seed GENERAL type and settings
- `credit_management/patches/v1_0/sync_gate2_workspace.py` — remove stale MVP workspace links
- `report/gate_2_core_ledger.md` — this report

### Updated
- `credit_management/api.py` — implemented Gate 2 public functions
- `credit_management/services/account_service.py` — account lifecycle, balance reads, locking helpers
- `credit_management/services/ledger_service.py` — append-only ledger writes, idempotency lookup
- `credit_management/services/grant_service.py` — grant orchestration with lock and idempotency
- `credit_management/services/consume_service.py` — consume orchestration with balance checks
- `credit_management/install.py` — `seed_defaults()`, `before_tests` hook
- `credit_management/hooks.py` — wired `before_tests`
- `credit_management/patches.txt` — INI format with pre/post model sync sections
- `credit_management/credit_management/workspace/credit_management/credit_management.json` — production links
- `credit_management/tests/test_gate1_scaffold.py` — Gate 3+ stub test only
- `docs/decision_log.md` — Gate 2 decisions D-019 through D-025

### Removed / Deprecated
- None (MVP artifacts were removed in Gate 1.5)

## Gate 1.5 condition check
- Workspace stale MVP links check: Verified `Credit Transaction` and `Credit Management Settings` were still present in DB workspace after JSON update
- Result: Stale links found in database workspace; JSON source was already clean
- Fix applied, if any: Added idempotent patch `sync_gate2_workspace` to reload workspace JSON and strip stale MVP DocType links

## Public API implemented
- get_or_create_account
- get_balance
- grant_credits
- consume_credits

## Ledger behavior
- Entry types implemented: GRANT, CONSUME (business logic); REFUND, ADJUST_IN, ADJUST_OUT, REVERSAL, RESERVE, RELEASE_RESERVE, CONSUME_RESERVE (select options only — reservation logic deferred to Gate 3)
- Append-only protection: Submittable `Credit Ledger Entry`; `on_cancel` blocked; `before_update_after_submit` blocked; `validate` rejects edits to submitted rows
- Idempotency approach: Optional `idempotency_key` on grant/consume; globally unique on ledger entry; replay returns prior structured result without duplicate balance change
- Row-locking approach: `AccountService.lock_account()` uses `frappe.get_doc("Credit Account", name, for_update=True)` (MariaDB `SELECT ... FOR UPDATE`) before balance mutation in grant/consume

## Tests run

```bash
bench --site jomveo migrate
bench --site jomveo run-tests --app credit_management
bench --site jomveo run-tests --app credit_management --module credit_management.tests.test_gate2_core_ledger
```

## Test result

* **Migrate:** Passed (DocTypes synced, seed and workspace patches applied)
* **Full app tests:** **22 passed, 0 failed, 0 skipped**
* **Gate 2 module tests:** **17 passed, 0 failed, 0 skipped**

Tests cover:
1. Credit Type creation/default (GENERAL)
2. Account creation
3. Account uniqueness (owner + type + company)
4. Get balance
5. Grant increases balance
6. Grant creates ledger entry
7. Idempotent grant does not duplicate
8. Consume decreases balance
9. Consume creates ledger entry
10. Insufficient balance blocks consume
11. Negative balance only when allowed
12. Idempotent consume does not duplicate
13. Suspended account cannot consume
14. Ledger entry cannot be edited after submit
15. Workspace has no stale MVP DocType links

## Risks or unresolved decisions

* **Dynamic Link owner validation:** Service-layer account creation uses `ignore_links` so generic owner identifiers (guest IDs, external keys) work without a backing Frappe document; desk form validation still applies on manual edits
* **`expires_on` on grant:** Accepted in API signature but ignored until Gate 4 expiry lots
* **Refund/adjust/reversal entry types:** Defined in select list; business logic deferred to Gate 5
* **Orphan test accounts from failed runs:** Pre-fix test data with random account names may remain on `jomveo`; harmless but could be cleaned in a future maintenance patch

## Next recommended gate

Gate 3: Reservations