# Operations Runbook

> Status: Gate 9 — day-2 operations

## Daily checks

1. Review **Credit Management** workspace metrics (accounts, reservations, consumed/expired today)
2. Run or verify daily scheduler: `generate_daily_credit_summary`, `expire_credits`
3. Spot-check failed `Credit Webhook Event` rows
4. Review reconciliation mismatches if reconciliation enabled

```bash
bench --site <site> execute credit_management.tasks.generate_daily_credit_summary
```

## Running daily summary

Returns same-day ledger aggregates without creating a DocType. Safe to run repeatedly.

## Running expiry

```bash
bench --site <site> execute credit_management.tasks.expire_credits
```

Also runs on daily scheduler. Requires `enable_credit_expiry` for lot-based expiry.

## Running reconciliation

```bash
bench --site <site> execute credit_management.tasks.reconcile_recent_accounts
bench --site <site> execute credit_management.api.reconcile_all_accounts
```

Hourly scheduler runs recent-window reconciliation automatically.

## Reviewing mismatches

1. Open **Reconciliation Report** or latest `Credit Reconciliation Run`
2. Compare expected vs actual in `details_json`
3. Distinguish test fixtures (deliberate 777 balances) from production drift
4. Trace `Credit Ledger Entry` history for account

**Do not use automatic repair** — reconciliation is detect-only.

## Investigating double-charge claims

1. Find idempotency keys on job document
2. Search `Credit Ledger Entry` by `idempotency_key`
3. Check `Credit Integration Log` for `Replayed` vs duplicate keys
4. Verify reservation lifecycle: one RESERVE, one CONSUME_RESERVE or RELEASE

## Investigating stuck reservations

1. List `Credit Reservation` with status Active / Partially Consumed
2. Check `expires_at` — hourly scheduler should release expired holds
3. Manual release: `credit_api.release_reservation(...)` via server script (Manager role)
4. Check `Reservation Aging Report`

## Investigating failed webhooks

1. Filter `Credit Webhook Event` status Failed
2. Read `last_error` — common: `No webhook target URL configured`
3. Fix URL in Credit Settings or cancel stale events
4. Retry: `bench --site <site> execute credit_management.tasks.retry_failed_webhooks`

## Cleaning integration logs

Recommendation: archive/delete records older than `audit_log_retention_days` (default 365). Implement site-specific cleanup script; not auto-scheduled in Gate 8.

**Do not delete** without retention policy approval.

## Low-balance events

Set `low_balance_threshold_default > 0` in Credit Settings. `credit.low_balance` webhook fires when available balance falls below threshold after consume/reserve/transfer/adjust.

## Safe manual correction

1. Identify root cause
2. Use `adjust_credits` with documented `reason` and idempotency key
3. Re-run `reconcile_account` to confirm Passed
4. Document in support ticket

## What not to do

| Forbidden | Reason |
|---|---|
| Edit submitted `Credit Ledger Entry` | Breaks append-only audit |
| SQL `UPDATE tabCredit Account` balance fields | Cache drift; no ledger trail |
| Delete `Credit Integration Log` / webhook events without policy | Audit loss |
| Fake webhook delivery success | Misleading operations state |
| Enable REST mutations on public internet without auth | Security risk |