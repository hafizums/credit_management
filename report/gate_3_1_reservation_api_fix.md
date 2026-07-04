# Gate 3.1 Summary — Reservation Public API Fix

Date: 2026-07-04
Status: Complete

## Problem fixed
- `credit_management/api.py` still raised `NotImplementedError` for reservation APIs.

## Completed
- Confirmed and finalized `ReservationService` import in `credit_management/api.py`
- Updated `reserve_credits`, `consume_reserved_credits`, and `release_reservation` to delegate to `ReservationService` with explicit keyword arguments
- Added `gate_3_1_api_smoke()` in `install.py` for grant → reserve → release verification
- Fixed `seed_credit_settings()` race (`reload()` before save) uncovered during smoke/test overlap
- Re-ran full app tests, Gate 3 module tests, and live API smoke check

## Files changed
- `credit_management/api.py` — reservation public API delegates to `ReservationService`
- `credit_management/install.py` — `gate_3_1_api_smoke()` helper; `seed_credit_settings()` reload fix
- `report/gate_3_1_reservation_api_fix.md` — this report

## Public API verification
- reserve_credits: Delegates to `ReservationService.reserve_credits(...)`; smoke returned `CR-*` reservation and `RESERVE` ledger entry
- consume_reserved_credits: Delegates to `ReservationService.consume_reserved_credits(...)`; covered by 25 Gate 3 tests
- release_reservation: Delegates to `ReservationService.release_reservation(...)`; smoke released hold and restored `available_balance` to 10

## Tests run

```bash
bench --site jomveo migrate
bench --site jomveo run-tests --app credit_management
bench --site jomveo run-tests --app credit_management --module credit_management.tests.test_gate3_reservations
bench --site jomveo execute credit_management.install.gate_3_1_api_smoke
```

## Test result

* **Migrate:** Passed
* **Full app tests:** **47 passed, 0 failed, 0 skipped**
* **Gate 3 module tests:** **25 passed, 0 failed, 0 skipped**
* **API smoke (grant → reserve → release):** Passed — balances restored to `current=10`, `reserved=0`, `available=10`
* **Import smoke:** `reserve_credits` / `consume_reserved_credits` / `release_reservation` contain no `NotImplementedError`

## Risks or unresolved decisions

* **Smoke owner data:** `gate3-api-smoke` account retains grant balance on `jomveo`; harmless test residue
* **Gate 3 report accuracy:** `report/gate_3_reservations.md` described API as implemented before this fix was verified in the public module path; Gate 3.1 closes that gap

## Next recommended gate

Gate 4: Expiry Lots