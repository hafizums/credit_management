# Operations Runbook

> Status: Milestone 17 — admin UX polish

## Desk admin tools (Milestone 17)

Open **Credit Management → Credit Admin Tools** (`credit-admin-tools` page) or use form actions on **Credit Reservation**.

| Task | Who | How |
|---|---|---|
| Top up / grant credits | Credit Manager, System Manager | Admin Tools → Top Up; requires grant reason; uses `grant_credits` → `GRANT` ledger |
| Refund credits | Credit Manager, System Manager | Admin Tools → Refund; requires refund reason; uses `refund_credits` → `REFUND` ledger |
| Release stuck reservation | Credit Manager, System Manager | Admin Tools → Release, or **Release Reservation** button on reservation form |
| Inspect account balance | All roles (scoped) | Admin Tools → Balance Quick View; Credit User sees own User account only |
| Review reconciliation mismatches | Privileged roles | Admin Tools → Reconciliation Review; re-run is detect-only (no auto-repair) |

**Before/after balances** are shown for grant/refund actions. All balance changes go through `credit_management.api` — never edit `Credit Account` balances directly.

### Reviewing reconciliation mismatches (desk)

1. Open **Credit Admin Tools → Reconciliation Review**
2. Sort by status `Mismatch`; open the `Credit Reconciliation Run` form for details
3. Use **Re-run** to execute detect-only `reconcile_account` (does not repair balances)
4. Use **Ledger Report** shortcut filtered by account
5. Open **Credit Account** form from run record

There is **no auto-repair button**. Follow [reconciliation.md](reconciliation.md) for investigation.

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

### Pilot account (preferred for production pilot)

```bash
bench --site <site> execute credit_management.api.reconcile_account --kwargs "{'credit_account':'<PILOT_CA>'}"
```

Record `summary_status`, balances, and timestamp before/after pilot windows. **Do not** treat site-wide mismatch counts from test fixtures as pilot health.

### Recent accounts (hourly scheduler)

```bash
bench --site <site> execute credit_management.tasks.reconcile_recent_accounts
```

Reconciles accounts with ledger activity in the last 24 hours. Empty result on quiet production sites is normal.

### All accounts (use with care)

```bash
bench --site <site> execute credit_management.api.reconcile_all_accounts
```

May include deliberate test-fixture mismatches on dev/staging sites. Use for audits, not pilot go/no-go alone.

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

1. List events: `bench --site <site> execute credit_management.tasks.list_failed_webhook_events`
2. Filter `Credit Webhook Event` status Failed or Pending
3. Read `last_error` — common: `No webhook target URL configured`
4. Fix URL in Credit Settings or cancel exhausted events (dry-run first):

```bash
bench --site <site> execute credit_management.tasks.cancel_exhausted_webhook_events --kwargs "{'dry_run': true}"
```

5. Retry: `bench --site <site> execute credit_management.tasks.retry_failed_webhooks`

See [webhooks.md](webhooks.md) enablement checklist before turning webhooks on.

## Cleaning integration logs

Dry-run first (default):

```bash
bench --site <site> execute credit_management.tasks.cleanup_old_integration_logs --kwargs "{'dry_run': true}"
```

Delete when approved:

```bash
bench --site <site> execute credit_management.tasks.cleanup_old_integration_logs --kwargs "{'dry_run': false}"
```

Uses `Credit Settings.audit_log_retention_days` (default 365). **Never deletes** ledger entries, reconciliation runs, or recent logs.

## Pilot grant and offboarding workflow

### Approving and granting pilot credits

1. Record approver, business reason, user email, amount, and credit type in change ticket
2. Verify REST/webhooks remain disabled unless explicitly approved
3. Grant via trusted API or Desk **Credit Admin Tools → Top Up** (Manager only):

```python
import credit_management.api as credit_api

credit_api.grant_credits(
    "User", "<email>", "AI_VIDEO", <amount>,
    idempotency_key="pilot-grant:<email>:<seq>",
    source_app="pilot_setup",
    metadata={"reason": "...", "approved_by": "..."},
)
```

4. Record starting balance and `reconcile_account` baseline → must be `Passed`

### Suspending / ending pilot access

1. Disable user in Frappe (`User.enabled = 0`) — blocks new video jobs
2. Review stuck `Reserved` jobs — run `dummy_website.tasks.recover_stuck_video_jobs`
3. Release active reservations via `release_reservation` if jobs cannot complete
4. Reconcile pilot account; investigate mismatches before offboarding sign-off

### Unused credits

- Document remaining balance at pilot end
- Refund via `refund_credits` with documented reason and idempotency key if business approves return
- Do not SQL-adjust balances

### Failed jobs

1. Confirm `Video Generation.credit_status` is `Released` or `Failed` (not `Reserved`)
2. Check `credit_error` and integration logs
3. If credits consumed incorrectly, investigate ledger + idempotency keys; correct via `adjust_credits` only after root-cause analysis

See [pilot_expansion_checklist.md](pilot_expansion_checklist.md).

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