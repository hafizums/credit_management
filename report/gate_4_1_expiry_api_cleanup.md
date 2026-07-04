# Gate 4.1 Summary — Expiry Public API Cleanup

Date: 2026-07-04
Status: Complete

## Problem fixed
- `credit_management.api.expire_credits()` still raised `NotImplementedError` after Gate 4.

## Completed
- Imported `ExpiryService` in `credit_management/api.py`
- Wired `expire_credits()` to delegate to `ExpiryService.expire_credits()`
- Updated Gate 1 scaffold test: `expire_credits` public API returns `completed`; Gate 5+ stubs unchanged
- Re-ran migrate, full app tests, Gate 4 module tests, and `bench execute` smoke check

## Files changed
- `credit_management/api.py` — `expire_credits()` public API wrapper
- `credit_management/tests/test_gate1_scaffold.py` — added `test_expire_credits_public_api`; renamed stub test to Gate 5+
- `report/gate_4_1_expiry_api_cleanup.md` — this report

## Public API verification
- expire_credits: Returns `ExpiryService.expire_credits()` result dict with `status: completed`; `bench execute credit_management.api.expire_credits` succeeded

## Tests run

```bash
bench --site jomveo migrate
bench --site jomveo run-tests --app credit_management
bench --site jomveo run-tests --app credit_management --module credit_management.tests.test_gate4_expiry_lots
bench --site jomveo execute credit_management.api.expire_credits
```

## Test result

* **Migrate:** Passed
* **Full app tests:** **70 passed, 0 failed, 0 skipped**
* **Gate 4 module tests:** **22 passed, 0 failed, 0 skipped**
* **API execute smoke:** Passed — `{"status": "completed", "expired": 0, "skipped": 4, "errors": []}`

## Risks or unresolved decisions

* **Scheduler vs public API:** `tasks.expire_credits` and `api.expire_credits` now share the same service path; consuming apps should prefer `credit_management.api.expire_credits` per platform contract
* **Manual invocation:** Public `expire_credits()` is intended for scheduler/admin use; no REST exposure until Gate 8

## Next recommended gate

Gate 5: Transfers and Adjustments