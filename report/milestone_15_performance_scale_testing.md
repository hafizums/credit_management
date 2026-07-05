# Milestone 15 Summary — Performance and Scale Testing

Date: 2026-07-05
Status: Complete
Test site: `credit-staging-load`
Data volume: ~6,800 credit accounts, ~12,800 ledger entries (post-load), ~7,400 integration logs

## Completed

- Created dedicated load-test site `credit-staging-load` (isolated from `jomveo` production pilot)
- Implemented M15 load helpers in `credit_management/load_tests/` and `dummy_website/load_tests/`
- Ran baseline test suites (186 + 20 tests) on load site
- Executed bulk grant, bulk consume, reservation concurrency, and video lifecycle concurrency scenarios
- Measured reconciliation at account, recent, and all-account scale
- Executed all 10 script reports after load data
- Ran scheduler smoke tasks and integration-log cleanup (dry-run + disposable delete)
- Reviewed MariaDB EXPLAIN/SHOW INDEX for hot tables
- Documented deadlock/retry signals (load vs test-fixture noise)

## Environment

- Frappe version: 14.101.1
- Python version: 3.10.12
- MariaDB version: 10.6.22-MariaDB
- Installed apps: `frappe`, `credit_management`, `dummy_website`
- Credit app version/commit: `0.0.1` / `f3e370a` (includes M15 load helpers)
- Dummy website version/commit: `0.0.1-m14` / `1111f78`

**Site choice:** `credit-staging-load` — disposable site per M15 recommendation; avoids destructive load on `jomveo` pilot data.

## Load profile

- Accounts created: ~6,100 load accounts + test-suite accounts ≈ **6,800 total**
- Ledger entries created: **~12,800** submitted entries (post-consume rerun)
- Reservations created: **~200** (concurrency + video flows)
- Video jobs simulated: **~95** (concurrency + lifecycle)
- Integration logs created: **~7,400+** (1 per logged API call)
- Webhook events created: **14** (from test suite; webhooks disabled)
- Expiry lots created: **~390** (from automated tests)

## Bulk grant performance

| Scenario | Runtime | Avg/op | Errors | Reconciliation |
|---|---:|---:|---|---|
| 100 users | 1.72s | 17.2 ms | 0 | Passed |
| 1,000 users | 16.87s | 16.9 ms | 0 | Passed |
| 5,000 users | 140.03s | 28.0 ms | 0 | Passed |

## Bulk consume performance

| Scenario | Runtime | Avg/op | Errors | Reconciliation |
|---|---:|---:|---|---|
| 100 consumes | 1.69s | 16.9 ms | 0 | Passed |
| 1,000 consumes | 15.45s* | 15.5 ms | 0 | Passed |
| 5,000 consumes | 113.90s* | 22.8 ms | 0 | Passed |

\*Re-run with per-scenario grant seed (`m15_consume_rerun`) after fixing shared idempotency key in initial harness. No negative balances; idempotent replay verified.

## Reservation concurrency

| Workers | Success | Failed | Deadlocks | Runtime | Reserved | Reconciliation |
|---:|---:|---:|---:|---:|---:|---|
| 10 | 10 | 0 | 0 | 0.44s | 30.0 | Passed |
| 25 | 25 | 0 | 0 | 1.03s | 105.0 | Passed |
| 50 | 50 | 0 | 0 | 2.14s | 255.0 | Passed |

No accidental negative available balance. No double reserve on same job.

## Video lifecycle concurrency

- Success jobs: mixed flows completed **10/10** worker runs OK
- Failed jobs: `[PILOT:FAIL]` flows released correctly
- Partial jobs: partial consume with auto-release remainder
- Duplicate callbacks: `dup_success` / `dup_fail` flows executed
- Stuck jobs: **2** `Reserved`/`Processing` after `dup_fail` harness (recoverable via `recover_stuck_video_jobs`)
- Deadlocks: **0** under load concurrency
- Double-charge check: video pilot account reconciliation **Passed**
- Runtime: 0.75s for 10 concurrent workers

## Reconciliation scale

| Operation | Runtime | Checked | Mismatches | Notes |
|---|---:|---:|---:|---|
| `reconcile_account` (sample) | 0.014s | 1 | 0 | Passed |
| `reconcile_recent_accounts` | 25.2s | 6,783 | 16 | Mismatch summary includes **Gate 7 test fixtures** |
| `reconcile_all_accounts` | 25.4s | 6,800 | 16 | Same fixture noise; compact `details_json` — no packet errors |

Pilot/load accounts reconciled clean. Site-wide mismatch count is test-fixture noise, not load regression.

## Report scale

| Report | Runtime | Rows |
|---|---:|---:|
| Credit Balance Report | 0.058s | 6,800 |
| Credit Ledger Report | 0.104s | 7,768 |
| Credit Usage by App | 0.011s | 6 |
| Credit Usage by Owner | 0.106s | 6,783 |
| Reservation Aging Report | 0.007s | 124 |
| Expired Credits Report | 0.002s | 96 |
| Reconciliation Report | 0.002s | 40 |
| Top Credit Consumers | 0.003s | 10 |
| Credit Grant History | 0.007s | 390 |
| Credit Transfer History | 0.003s | 65 |

All reports executed without errors. No memory failures observed at tested volume.

## Scheduler scale

| Task | Runtime | Status |
|---|---:|---|
| `release_expired_reservations` | 0.001s | completed, released=0 |
| `expire_credits` | 0.017s | completed |
| `reconcile_recent_accounts` | 25.0s | completed |
| `generate_daily_credit_summary` | 0.011s | completed |
| `retry_failed_webhooks` | 0.082s | attempted=0 |
| `cleanup_old_integration_logs` (dry-run) | 0.004s | eligible=1 |

## Database/index review

- Slow queries observed: `reconcile_recent/all` ~25s at ~6.8k accounts (acceptable); ledger report 0.1s at ~7.7k rows
- Indexes reviewed: `SHOW INDEX` captured for ledger, account, reservation, integration log, webhook, expiry lot, reconciliation run
- EXPLAIN `ledger_by_account`: type `ALL` at ~7.6k rows — optimizer table scan with `Using where; Using filesort`; per-account reconcile still sub-20ms
- Indexes added: **None** — performance acceptable at tested volume; composite `(credit_account, docstatus)` recommended before 50k+ ledger rows
- Migration result: N/A (no schema changes)

## Integration log growth

- Logs created: ~1 integration log per API operation with logging enabled
- Storage concern: moderate at load volume; plan retention cleanup per M14 SOP
- Cleanup dry-run: eligible=1 (90-day window during suite)
- Cleanup actual run: deleted **1** disposable backdated log on load site only (approved disposable data)

## Deadlock/retry review

- Deadlocks observed in load concurrency: **0**
- Lock waits observed: **0**
- Error Log matches: **5** — all from **M14 simulated deadlock unit tests**, not M15 load
- Retry exhausted: none in load scenarios
- Jobs recoverable: 2 stuck reserved video jobs from `dup_fail` harness
- Double charge detected: **none** (reconciliation Passed on load accounts)

## Commands run

```bash
bench new-site credit-staging-load --admin-password admin --install-app credit_management --install-app dummy_website --mariadb-root-password hafiz123 --force
bench --site credit-staging-load set-config allow_tests true
bench --site credit-staging-load migrate
bench --site credit-staging-load execute dummy_website.install.after_install
bench --site credit-staging-load run-tests --app credit_management
bench --site credit-staging-load run-tests --app dummy_website
bench --site credit-staging-load execute credit_management.load_tests.m15_runner.run
bench --site credit-staging-load execute credit_management.load_tests.m15_consume_rerun.run
bench --site credit-staging-load execute credit_management.tasks.reconcile_recent_accounts
bench --site credit-staging-load execute credit_management.tasks.generate_daily_credit_summary
bench --site credit-staging-load execute credit_management.tasks.release_expired_reservations
bench --site credit-staging-load execute credit_management.tasks.retry_failed_webhooks
bench --site credit-staging-load execute credit_management.tasks.cleanup_old_integration_logs --kwargs "{'dry_run': True}"
```

## Results

```text
credit_management tests: 186 passed (~86s)
dummy_website tests: 20 passed (~2s)
bulk grant 5000: 140s, 0 errors, reconciliation Passed
bulk consume 5000: 114s (rerun), 0 errors, reconciliation Passed
concurrent reserve 50: 2.1s, 0 deadlocks, reconciliation Passed
video concurrency 10: 0.75s, 0 deadlocks, reconciliation Passed
reconcile_all: 25.4s, 6800 accounts, 16 mismatches (test fixtures)
all 10 reports: <0.11s each at ~7.7k ledger rows
schedulers: all completed without errors
```

## Issues found

* Initial bulk-consume harness reused grant idempotency key across scenarios → insufficient balance on 1,000 scenario (fixed; rerun passed)
* `reconcile_all` / `reconcile_recent` report 16 mismatches from embedded Gate 7 test fixtures (not load regression)
* Ledger EXPLAIN shows full table scan at ~7.7k rows — acceptable now; monitor beyond 50k rows
* Video `dup_fail` harness leaves 2 jobs in `Reserved`/`Processing` — recoverable, not a credit leak
* Error Log deadlock entries are from **simulated** M14 tests, not production load deadlocks

## Required fixes before wider rollout

* Add composite DB index on `Credit Ledger Entry (credit_account, docstatus)` if ledger exceeds ~50k rows per site
* Schedule integration-log retention review as log volume grows
* Keep pilot expansion on checklist; do not enable REST/webhooks without security review
* Monitor real (non-simulated) deadlock Error Log entries after adding concurrent pilot users

## Readiness decision

Choose one:

* **Ready for wider pilot expansion**
* Needs performance fixes
* Blocked

**Recommendation: Ready for wider pilot expansion** — controlled load site handled 5k grants/consumes, 50 concurrent reservations, and concurrent video flows with zero load deadlocks and clean pilot-account reconciliation.

## Next recommended milestone

Milestone 16: Security Review