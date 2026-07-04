# Gate 3 Summary — Reservations

Date: 2026-07-04
Status: Complete

## Completed
- Implemented production `Credit Reservation` DocType with full lifecycle statuses
- Implemented `ReservationService` with reserve, consume-reserved, release, and expire flows
- Implemented public API: `reserve_credits`, `consume_reserved_credits`, `release_reservation`
- Wired `release_expired_reservations` scheduler task (hourly via existing `hooks.py`)
- All reservation balance changes create append-only ledger entries (`RESERVE`, `CONSUME_RESERVE`, `RELEASE_RESERVE`)
- Operation-specific idempotency keys with auto-release suffix for partial consume
- Partial consume auto-releases remainder in same operation (final status `Consumed`)
- Added Gate 3 test suite with 25 tests including async video-generation simulations
- Preserved Gate 2 public API behavior and all Gate 2 tests

## Files changed

### New
- `credit_management/credit_management/doctype/credit_reservation/` — Credit Reservation DocType
- `credit_management/tests/test_gate3_reservations.py` — Gate 3 test suite (25 tests)
- `report/gate_3_reservations.md` — this report

### Updated
- `credit_management/services/reservation_service.py` — full reservation lifecycle implementation
- `credit_management/services/account_service.py` — added `validate_account_can_reserve`
- `credit_management/api.py` — implemented Gate 3 public functions
- `credit_management/tasks.py` — `release_expired_reservations` delegates to service
- `credit_management/tests/test_gate1_scaffold.py` — Gate 4+ stub test; scheduler test for implemented task
- `docs/decision_log.md` — Gate 3 decisions D-034 through D-040
- `docs/reservation_model.md` — status updated to implemented constraints reference

### Removed / Deprecated
- None

## Public API implemented
- reserve_credits
- consume_reserved_credits
- release_reservation

## Reservation behavior
- Statuses implemented: Active, Partially Consumed (schema), Consumed, Released, Expired, Cancelled
- Reserve behavior: Lock account → validate status/balance → increase `reserved_balance` → create reservation + `RESERVE` ledger entry; default `expires_at` from settings (60 min fallback)
- Consume reserved behavior: Lock account + reservation → `CONSUME_RESERVE` decreases `current_balance` and `reserved_balance` by consumed amount; increases `lifetime_consumed`
- Partial consume policy: If `actual_amount` < remaining reserved, consume actual and auto-release remainder via `RELEASE_RESERVE` with `{idempotency_key}:auto-release`; final status `Consumed`
- Release behavior: Lock account + reservation → decrease `reserved_balance` by remaining amount; status `Released`, `Expired`, or `Cancelled` based on context/reason
- Expiry behavior: Hourly scheduler finds Active/Partially Consumed with `expires_at < now`, releases remainder, sets `Expired`, ledger key `reservation:{name}:expire`
- Idempotency approach: Unique key on `Credit Reservation` for reserve; ledger keys per operation (`:reserve`, `:consume-reserved`, `:release`, `:auto-release`, `:expire`)
- Row-locking approach: `for_update=True` on Credit Account and Credit Reservation before all mutations

## Ledger behavior
- RESERVE: Records hold placement; `current_balance` unchanged; `reserved_balance_after` increased
- CONSUME_RESERVE: Records actual consumption from hold; decreases `current_balance`
- RELEASE_RESERVE: Records hold release (manual, auto-remainder, or expire); decreases `reserved_balance`; `current_balance` unchanged
- Append-only protection: Unchanged from Gate 2 — submitted entries immutable; no cancel/amend

## Async workload simulation
- Video-generation success test: grant → reserve (`:reserve`) → consume (`:consume-reserved`) → balances 930/0/930
- Video-generation failure test: grant → reserve → release (`:release`) → balances restored to 1000/0/1000
- Retry/duplicate callback test: duplicate reserve and consume idempotency replays do not double-charge; release on consumed reservation correctly rejected

## Tests run

```bash
bench --site jomveo migrate
bench --site jomveo run-tests --app credit_management
bench --site jomveo run-tests --app credit_management --module credit_management.tests.test_gate3_reservations
```

## Test result

* **Migrate:** Passed (Credit Reservation DocType synced)
* **Full app tests:** **47 passed, 0 failed, 0 skipped** (includes all Gate 1, Gate 2, and Gate 3 tests)
* **Gate 3 module tests:** **25 passed, 0 failed, 0 skipped**

## Risks or unresolved decisions

* **`Partially Consumed` status:** Defined in schema but not used as a terminal state under the approved auto-release policy; reserved for future partial-settlement flows if policy changes
* **Scheduler concurrency:** Hourly expire task processes reservations sequentially; high-volume sites may need batching in a later gate
* **No REST/webhook integration yet:** Scheduler and API are service-ready; Gate 8 will expose integration layer

## Next recommended gate

Gate 4: Expiry Lots