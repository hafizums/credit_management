# Reconciliation

> Status: Milestone 14 — detect-only production reconciliation SOP

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

## Operations SOP

### Daily — pilot users

For each named pilot account:

```bash
bench --site <site> execute credit_management.api.reconcile_account --kwargs "{'credit_account':'<PILOT_CA>'}"
```

Expect `summary_status: Passed`. Record result in pilot log. **Do not auto-repair.**

### Hourly — recent activity

Scheduler task `reconcile_recent_accounts` covers accounts with ledger changes in the last 24h.

### Ad hoc — all accounts

`reconcile_all_accounts` for audits. On dev/staging after test runs, mismatch counts may reflect **test fixtures**, not pilot drift.

## Distinguishing test fixture noise vs real drift

| Signal | Test fixture | Real pilot issue |
|---|---|---|
| Account owner | Test emails / Gate 7 patterns | Named pilot users |
| Balance pattern | Deliberate values (e.g. 777) | Matches grant + job consumption |
| Timing | After `run-tests` | After production pilot flows |
| Ledger | Synthetic test keys | `video-job:*` idempotency keys |

**Never use** post-test site-wide mismatch totals as pilot baseline.

## Manual investigation workflow

1. Run `reconcile_account` or open **Reconciliation Report**
2. Review `Credit Reconciliation Run` — status `Mismatch`
3. Inspect `details_json` for field-level differences (current, reserved, available)
4. Trace `Credit Ledger Entry` and `Credit Reservation` for the account
5. Check `Credit Integration Log` for failed/replayed operations
6. Correct via proper API (`adjust_credits`) after root cause — **never direct SQL**

## Forbidden actions

| Action | Why |
|---|---|
| SQL `UPDATE tabCredit Account` balances | Breaks ledger projection; no audit trail |
| Edit submitted `Credit Ledger Entry` | Violates append-only model |
| Delete reconciliation runs to hide mismatches | Hides operational signal |
| Silent auto-repair in reconciliation service | Explicitly out of scope (detect-only) |

## Known Gate 5 reversal / lot drift risk

Reversing a GRANT/CONSUME/etc. updates cached balances but **does not** restore expiry-lot allocations. Reconciliation may report lot/account inconsistency afterward.

## Records

Each run creates `Credit Reconciliation Run` (`CRR-{#####}`) with status `Passed`, `Mismatch`, `Failed`, or `Partial` (batch).

## Settings

`Credit Settings.balance_reconciliation_enabled` — feature toggle for service checks (scheduler still runs via task).