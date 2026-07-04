# Reconciliation

> Status: Gate 7–9 — detect-only production reconciliation

## Policy

**Detect-only.** Reconciliation compares ledger-derived expected balances against cached `Credit Account` fields and expiry-lot consistency. It does **not** auto-repair balances or lots.

## Public API

```python
import credit_management.api as credit_api

credit_api.reconcile_account("CA-...")
credit_api.reconcile_all_accounts()
```

Scheduler: `credit_management.tasks.reconcile_recent_accounts()` (hourly; last 24h activity window).

## Ledger-derived balance logic

Replay submitted `Credit Ledger Entry` rows:

| Entry type | Current | Reserved |
|---|---|---|
| GRANT, REFUND, ADJUST_IN, TRANSFER_IN | +amount | |
| CONSUME, CONSUME_RESERVE, ADJUST_OUT, EXPIRE, TRANSFER_OUT | −amount | |
| RESERVE | | +amount |
| RELEASE_RESERVE, CONSUME_RESERVE | | −amount |
| REVERSAL | Opposite of reversed entry | |

`expected_available = expected_current - expected_reserved`

## Lifetime warning policy

`lifetime_granted`, `lifetime_consumed`, `lifetime_expired` drift is recorded as **warnings** in `details_json`. Lifetime alone does not fail a run.

## Expiry-lot consistency checks

- No negative lot remaining/reserved
- Reserved on lot ≤ remaining on lot
- Terminal lots have no usable remainder
- Account reserved ≥ sum of lot reserved
- Lot remaining totals vs ledger current (Gate 5 reversal drift detection)

## Manual investigation workflow

1. Run `reconcile_account` or open **Reconciliation Report**
2. Review `Credit Reconciliation Run` — status `Mismatch`
3. Inspect `details_json` for field-level differences
4. Trace ledger entries for the account
5. If test fixture (777 balance) — expected on dev sites with Gate 7 tests
6. Correct via proper API (`adjust_credits`) after root cause — never direct SQL

## Known Gate 5 reversal / lot drift risk

Reversing a GRANT/CONSUME/etc. updates cached balances but **does not** restore expiry-lot allocations. Reconciliation may report lot/account inconsistency afterward.

## Records

Each run creates `Credit Reconciliation Run` (`CRR-{#####}`) with status `Passed`, `Mismatch`, `Failed`, or `Partial` (batch).

## Settings

`Credit Settings.balance_reconciliation_enabled` — feature toggle for service checks (scheduler still runs via task).