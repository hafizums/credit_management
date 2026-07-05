# Milestone 13 Summary — Controlled Production Pilot

Date: 2026-07-05
Status: Complete
Production site: `jomveo`
Pilot duration: 2026-07-05 to 2026-07-19
Pilot users: `Administrator`, `pilot-video-prod@jomveo.local`
Credit type: `AI_VIDEO`

## Completed

- Confirmed pre-pilot production backup (`20260705_201547-jomveo-*`)
- Migrated `jomveo` with `credit_management` and `dummy_website` up to date
- Verified `AI_VIDEO` Credit Type and `Credit Settings` security defaults
- Granted limited pilot credits (500 per user, 1000 total exposure cap)
- Recorded pilot-account baselines and ran account-level reconciliation
- Executed controlled production pilot flows for two selected users (success, failure, partial, duplicate callbacks)
- Ran scheduler monitoring commands (reconcile, daily summary, expired release, webhook retry)
- Verified ledger, reservation, and integration-log linkage for video jobs
- Confirmed no production deadlocks, stuck reservations, or double charges during pilot window
- Added production pilot tooling (`pilot_production_m13.py`, `pilot_status_m13.py`, `pilot_report_m13.py`)

## Environment

- Frappe version: 14.101.1
- Python version: 3.10.12
- MariaDB version: 10.6.22-MariaDB
- Installed apps: `frappe`, `dummy_website`, `credit_management`
- Credit app version/commit: `0.0.1` / `da2d39f` (gate 12)
- Video app version/commit: `0.0.1` / bench-local (no git remote)

## Pilot configuration

- REST enabled: **0** (disabled)
- Webhooks enabled: **0** (disabled)
- Integration logs enabled: **1** (enabled)
- Initial grant per user: **500** `AI_VIDEO` credits
- Total pilot credit exposure: **1000** credits (2 users × 500)
- Pilot limits: 2 named users only; no wide rollout; mock provider pilot markers only; max spend capped by grant amount

## Starting baseline

- Pilot accounts:
  - `Administrator` → `CA-fa08687ecc9a301ef19d`
  - `pilot-video-prod@jomveo.local` → `CA-2f11c8883ed9f565877a`
- Starting balances: 0.0 current / 0.0 reserved / 0.0 available (new `AI_VIDEO` accounts before grant)
- Reconciliation status: **Passed** for both accounts after grant and after all pilot flows
- Existing mismatches: **0** on pilot accounts (site-wide `reconcile_recent_accounts` checked 0 recent-window accounts — clean production scope)
- Notes: Test-fixture accounts from staging (`credit-staging`) were not used as baseline. Production pilot accounts are isolated named users only.

## Pilot flows tested

Per pilot user (`Administrator`, `pilot-video-prod@jomveo.local`):

- Successful video: **Passed** — `Completed` / `credit_status=Consumed`; 10.0 credits consumed
- Failed video: **Passed** — `[PILOT:FAIL]` → `Failed` / `credit_status=Released`; no net charge
- Partial-cost video: **Passed** — estimated 10.0, actual 8.0; auto-released 2.0 remainder
- Duplicate success callback: **Passed** — idempotent replay; balance unchanged after retry
- Duplicate failure callback: **Passed** — `idempotent_replay=true`; balance unchanged
- Insufficient-credit handling: **Covered in staging (M12)** — not re-run on production to avoid polluting live accounts
- Stuck job recovery: **Passed** — `recover_stuck_video_jobs` returned 0 stuck jobs
- Reservation expiry: **Passed** — `release_expired_reservations` released 0; no active stale reservations

## Balance and ledger verification

| User | Starting (post-grant) | Final current | Reserved | Available | Lifetime consumed |
|---|---:|---:|---:|---:|---:|
| Administrator | 500.0 | 482.0 | 0.0 | 482.0 | 18.0 |
| pilot-video-prod@jomveo.local | 500.0 | 482.0 | 0.0 | 482.0 | 18.0 |

- Ledger entries: 8 per pilot account — `GRANT`, `RESERVE`, `CONSUME_RESERVE`, `RELEASE_RESERVE` chain correct
- Reservation records: 3 per user; each references `Video Generation` job; statuses `Consumed` or `Released`
- Integration logs: `reserve_credits` logged with video job `reference_name`; consume/release logged via API wrapper
- Reconciliation result: **Passed** for both pilot accounts (direct `reconcile_account` and post-flow snapshot)

Example reservation linkage (Administrator):

- `VG-2026-43722` → `CR-43723` (Consumed, 10.0)
- `VG-2026-43728` → `CR-43729` (Released, 10.0)
- `VG-2026-43734` → `CR-43735` (Consumed, 8.0 + 2.0 auto-released)

## Monitoring results

- Failed jobs: 2 total (1 per user; simulated `[PILOT:FAIL]`; credits released)
- Expired reservations: 0
- Stuck reservations: 0
- Deadlocks: **0** observed in production pilot execution
- Webhook failures: 0 (`retry_failed_webhooks`: attempted 0)
- REST access attempts: 0 integration-log REST operations; REST disabled
- Permission issues: none observed for pilot flows
- Reconciliation mismatches: **0** on pilot accounts

## Commands run

```bash
bench --site jomveo backup --with-files
bench --site jomveo migrate
bench --site jomveo execute dummy_website.pilot_production_m13.run
bench --site jomveo execute dummy_website.pilot_status_m13.run
bench --site jomveo execute dummy_website.pilot_report_m13.run
bench --site jomveo execute credit_management.tasks.reconcile_recent_accounts
bench --site jomveo execute credit_management.tasks.generate_daily_credit_summary
bench --site jomveo execute credit_management.tasks.release_expired_reservations
bench --site jomveo execute credit_management.tasks.retry_failed_webhooks
bench --site jomveo execute credit_management.api.reconcile_account --kwargs "{'credit_account':'CA-fa08687ecc9a301ef19d'}"
bench --site jomveo execute credit_management.api.reconcile_account --kwargs "{'credit_account':'CA-2f11c8883ed9f565877a'}"
```

## Results

```text
Backup: 20260705_201547-jomveo-database.sql.gz (with files) — success
Migrate: success (frappe, dummy_website, credit_management)
Pilot flows: 2 users × 3 jobs — all settled correctly
Daily summary: total_accounts=2, consumed_today=36.0, granted_today=1000.0
release_expired_reservations: released=0
retry_failed_webhooks: attempted=0
Pilot reconciliation: Passed (both accounts, 0 mismatches)
```

## Issues found

* `pilot_production_m13.py` monitoring initially queried nonexistent `delivery_status` on `Credit Webhook Event` (correct field is `status`) — fixed before report snapshot; pilot flows had already completed successfully
* `dummy_website` has no git commit metadata in bench (bench-local app) — track version externally before wider rollout
* MariaDB deadlock risk remains a known staging flake under concurrent ledger naming; **not observed** in this controlled production pilot (sequential flows)

## Required fixes before wider rollout

* Add explicit deadlock retry/backoff in `video_job_service` if concurrent production load increases
* Version-pin and git-track `dummy_website` for production deployments
* Define formal pilot offboarding and credit grant approval workflow before adding users
* Keep REST/webhooks disabled until security review is explicitly approved
* Continue baselining reconciliation per pilot account — do not use test-fixture or post-test DB aggregates

## Readiness decision

Choose one:

* **Ready for limited expansion**
* Needs pilot fixes
* Blocked

**Recommendation: Ready for limited expansion** — controlled pilot on `jomveo` passed all required flows, balances reconcile, security defaults hold, and no production deadlocks or double charges observed.

## Next recommended milestone

Milestone 14: Operations Hardening