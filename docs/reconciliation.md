# Reconciliation

> Status: Gate 7 — production reconciliation and reporting

## Public API

```python
import credit_management.api as credit_api

credit_api.reconcile_account("CA-...")
credit_api.reconcile_all_accounts()
```

Scheduler: `credit_management.tasks.reconcile_recent_accounts()` (hourly).

## Balance derivation

Expected balances are derived by replaying submitted `Credit Ledger Entry` rows:

| Entry type | Current | Reserved |
|---|---|---|
| GRANT, REFUND, ADJUST_IN, TRANSFER_IN | +amount | |
| CONSUME, CONSUME_RESERVE, ADJUST_OUT, EXPIRE, TRANSFER_OUT | −amount | |
| RESERVE | | +amount |
| RELEASE_RESERVE, CONSUME_RESERVE | | −amount |
| REVERSAL | Opposite of reversed entry's current effect | |

Then:

`expected_available_balance = expected_current_balance - expected_reserved_balance`

Compared against cached `Credit Account` fields.

## Lifetime fields

`lifetime_granted`, `lifetime_consumed`, and `lifetime_expired` are also derived and recorded as **warnings** in `details_json` when they drift. They do not alone determine pass/fail.

## Expiry-lot checks

Per account:

- No negative `remaining_amount` or `reserved_amount`
- `reserved_amount` must not exceed `remaining_amount`
- Terminal lots (`Exhausted`, `Expired`) must not have usable `remaining - reserved`
- Account `reserved_balance` must not be less than sum of lot `reserved_amount`
- Lot remaining totals must not exceed account/ledger-derived current (detects Gate 5 reversal desync)

## Repair behavior

Gate 7 does **not** auto-repair cached balances or expiry lots. `Credit Reconciliation Run` records mismatches only.

## Records

Each reconciliation creates a `Credit Reconciliation Run` with status `Passed`, `Mismatch`, `Failed`, or `Partial` (batch runs).