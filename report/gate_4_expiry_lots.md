# Gate 4 Summary — Expiry Lots

Date: 2026-07-04
Status: Complete

## Completed
- Implemented `Credit Grant` and `Credit Expiry Lot` DocTypes
- Implemented `Credit Reservation Lot Allocation` child table on `Credit Reservation`
- Implemented `ExpiryService` with lot creation, FIFO consume/reserve, scheduled expiry, and reservation lot integration
- Updated `grant_credits` to create grants and expiry lots when `expires_on` is set and expiry is enabled
- Updated direct consume, reserve, consume-reserved, and release flows to use FIFO expiry lots
- Added `EXPIRE` ledger entry type and business logic
- Implemented daily `expire_credits` scheduler task
- Added Gate 4 test suite (22 tests) including Gate 2/3 regression checks
- Preserved Gate 2 and Gate 3 public API contracts and test suites

## Files changed

### New
- `credit_management/credit_management/doctype/credit_grant/` — Credit Grant DocType
- `credit_management/credit_management/doctype/credit_expiry_lot/` — Credit Expiry Lot DocType
- `credit_management/credit_management/doctype/credit_reservation_lot_allocation/` — reservation allocation child DocType
- `credit_management/tests/test_gate4_expiry_lots.py` — Gate 4 test suite (22 tests)
- `report/gate_4_expiry_lots.md` — this report

### Updated
- `credit_management/services/expiry_service.py` — full expiry lot service implementation
- `credit_management/services/grant_service.py` — expiring grants with Credit Grant + lot creation
- `credit_management/services/consume_service.py` — FIFO lot consumption on direct consume
- `credit_management/services/reservation_service.py` — lot allocation on reserve/consume/release
- `credit_management/services/account_service.py` — `lifetime_expired_delta` on balance updates
- `credit_management/services/ledger_service.py` — `EXPIRE` entry type
- `credit_management/credit_management/doctype/credit_ledger_entry/credit_ledger_entry.json` — added `EXPIRE`
- `credit_management/credit_management/doctype/credit_reservation/credit_reservation.json` — expiry lot allocations table
- `credit_management/tasks.py` — `expire_credits` delegates to `ExpiryService`
- `credit_management/tests/test_gate1_scaffold.py` — `expire_credits` no longer stub
- `docs/decision_log.md` — Gate 4 decisions D-041 through D-046

### Removed / Deprecated
- None

## Public API behavior
- grant_credits expiry behavior: `expires_on` + `enable_credit_expiry` creates `Credit Grant`, `GRANT` ledger, and `Credit Expiry Lot`; otherwise unchanged Gate 2 grant path
- consume_credits expiry behavior: FIFO consume from active lots when lots exist, then non-expiring balance; single `CONSUME` ledger entry
- reserve_credits expiry behavior: FIFO reserve from active lots via child allocations; account `reserved_balance` unchanged from Gate 3 semantics
- consume_reserved_credits expiry behavior: consumes/releases lot allocations; auto-releases unused allocation rows; separate from direct `CONSUME`
- release_reservation expiry behavior: releases lot `reserved_amount`; credits released from past-expiry lots expire immediately

## Expiry behavior
- Lot creation: On expiring grant when settings enabled; `original_amount = remaining_amount = grant amount`
- FIFO consumption: Earliest `expires_on` active lots first, then non-expiring pool
- Reservation lot allocation: `Credit Reservation Lot Allocation` child rows track per-lot reserved/consumed/released amounts
- Reserved consume: Decreases lot `reserved_amount` and `remaining_amount`; increases `consumed_amount`
- Reserved release: Decreases lot `reserved_amount` only; does not consume `remaining_amount`
- Expiry scheduler: Daily `expire_credits` expires `remaining_amount - reserved_amount` for lots with `expires_on < today`
- Reserved expired-lot policy: Active reservation protects reserved portion from scheduler; released credits from expired lots expire immediately (not returned to usable balance)
- Idempotency approach: Grant via `Credit Grant` + ledger keys; expire via `expiry-lot:{name}:expire`; existing Gate 3 reservation keys preserved
- Row-locking approach: `for_update=True` on account and expiry lots during mutations

## Ledger behavior
- GRANT: Unchanged; linked to `Credit Grant` when expiring grant created
- CONSUME: Unchanged entry type; lot `remaining_amount` decreased in service layer before entry
- RESERVE: Unchanged; lot `reserved_amount` increased via allocations
- CONSUME_RESERVE: Unchanged; lot allocation consume path
- RELEASE_RESERVE: Unchanged; lot allocation release path; may trigger immediate `EXPIRE` on past-expiry lots
- EXPIRE: New; decreases `current_balance`, increases `lifetime_expired`, updates lot `expired_amount`

## Tests run

```bash
bench --site jomveo migrate
bench --site jomveo run-tests --app credit_management
bench --site jomveo run-tests --app credit_management --module credit_management.tests.test_gate4_expiry_lots
```

## Test result

* **Migrate:** Passed (Credit Grant, Credit Expiry Lot, allocation child table synced)
* **Full app tests:** **69 passed, 0 failed, 0 skipped**
* **Gate 4 module tests:** **22 passed, 0 failed, 0 skipped** (includes Gate 2 and Gate 3 regression subtests)

## Risks or unresolved decisions

* **Non-expiring balance is implicit:** No separate lot; computed as consumption overflow after FIFO lots — sufficient for Gate 4 but reconciliation (Gate 7) may add explicit tracking
* **Credit Grant only for expiring grants:** Grants without `expires_on` do not create `Credit Grant` records; acceptable for Gate 4 scope
* **Daily scheduler granularity:** Date-based `expires_on < today`; same-day expiry within the day depends on scheduler run time

## Next recommended gate

Gate 5: Transfers and Adjustments