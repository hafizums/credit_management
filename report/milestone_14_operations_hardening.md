# Milestone 14 Summary — Operations Hardening

Date: 2026-07-05
Status: Complete
Production site: `jomveo`
Pilot app: `dummy_website` (video generation pilot integration)

## Completed

- Added bounded deadlock/lock-wait retry with backoff around video credit settlement (`reserve`, `consume`, `release`)
- Added 5 deadlock retry integration tests in `dummy_website`
- Implemented `cleanup_old_integration_logs` task with dry-run default and retention from `audit_log_retention_days`
- Allowed operator-flagged integration log deletion via cleanup task only
- Added webhook monitoring helpers (`list_failed_webhook_events`, `cancel_exhausted_webhook_events`)
- Expanded reconciliation SOP, operations runbook, and webhook enablement checklist
- Created `docs/pilot_expansion_checklist.md` and grant/offboarding workflow guidance
- Initialized git tracking for `dummy_website` with `DEPLOYMENT.json` manifest
- Updated `README.md` and `report/README.md` milestone index
- Ran full test suites and production scheduler commands on `jomveo`

## Files changed

### New

- `dummy_website/dummy_website/services/db_retry.py` — transient DB retry/backoff helper
- `dummy_website/dummy_website/tests/test_deadlock_retry.py` — deadlock retry tests
- `dummy_website/DEPLOYMENT.json` — deployment/version manifest
- `credit_management/credit_management/services/integration_log_cleanup_service.py`
- `credit_management/credit_management/tests/test_m14_operations.py`
- `credit_management/docs/pilot_expansion_checklist.md`
- `credit_management/report/milestone_14_operations_hardening.md`

### Updated

- `dummy_website/dummy_website/services/credit_integration.py` — wraps settlement APIs with retry
- `credit_management/credit_management/tasks.py` — cleanup + webhook operator tasks
- `credit_management/credit_management/services/webhook_service.py` — list/cancel helpers
- `credit_management/credit_management/doctype/credit_integration_log/credit_integration_log.py` — cleanup flag
- `credit_management/docs/operations_runbook.md` — reconciliation SOP, grants, log cleanup
- `credit_management/docs/reconciliation.md` — pilot vs fixture guidance, forbidden actions
- `credit_management/docs/webhooks.md` — enablement checklist, monitoring, HMAC limitation
- `credit_management/README.md` — milestone index through M14
- `credit_management/report/README.md` — M13 Complete, M14 Complete

### Removed / Deprecated

- None

## Documentation index update

- README: milestones 11–14 marked Complete; added `pilot_expansion_checklist.md` link
- report/README: M13 Controlled Production Pilot — **Complete**; M14 Operations Hardening — **Complete**

## Deadlock retry/backoff

- Implemented: **Yes** — `dummy_website.services.db_retry.retry_transient_db_error`
- Retry scope: `reserve_credits`, `consume_reserved_credits`, `release_reservation` via `credit_integration.py`
- Idempotency behavior: same idempotency keys on retry; `reserve_before_provider` skips if already `Reserved`
- Tests: 5 tests in `test_deadlock_retry.py` — all passed on `jomveo`
- Remaining risk: concurrent high-volume naming may still fail after 3 attempts; job left in recoverable `Reserved` state for `recover_stuck_video_jobs`

## Integration log retention

- Implemented: **Yes** — `credit_management.tasks.cleanup_old_integration_logs`
- Retention days: from `Credit Settings.audit_log_retention_days` (default 365; dry-run sample used 90)
- Dry-run behavior: default `dry_run=True`; returns `eligible` count, `deleted=0`
- Cleanup behavior: deletes only `Credit Integration Log` older than cutoff via `allow_integration_log_cleanup` flag
- Safety rules: never deletes ledger entries, reconciliation runs, or recent logs

## Webhook operations

- Enablement checklist: added to `docs/webhooks.md`
- Failed/Pending monitoring: `tasks.list_failed_webhook_events`; desk filter on `Credit Webhook Event`
- Retry behavior: documented; `retry_failed_webhooks` every 30 minutes
- Signature/HMAC limitation: **not implemented** — documented explicitly; network + idempotent receiver required

## Reconciliation SOP

- Pilot account reconciliation: `reconcile_account` per pilot `CA-*` — documented in runbook + reconciliation.md
- Recent reconciliation: hourly `reconcile_recent_accounts` (24h window)
- All-account reconciliation: `reconcile_all_accounts` for audits; not pilot go/no-go alone
- Mismatch investigation: trace ledger → reservations → integration logs; no auto-repair
- Forbidden actions: SQL balance updates, ledger edits, silent auto-repair, deleting reconciliation runs

## Pilot expansion checklist

- File: `docs/pilot_expansion_checklist.md`
- Covered items: backup, approvals, REST/webhooks, baseline, scheduler health, stuck/failed/deadlock checks, final reconciliation

## Grant/offboarding workflow

- Grant approval: documented ticket fields + metadata on `grant_credits`
- Limited grant: trusted API only with idempotency key
- Refund handling: `refund_credits` with documented reason after approval
- User offboarding: disable user, recover stuck jobs, release reservations, reconcile
- Unused credit handling: document balance; refund via API if approved

## Version tracking

- Credit app version/commit: `0.0.1` / `e5ced5c` (M14 operations hardening commit)
- Dummy website version/commit: `0.0.1-m14` / `1f44aa4` (git initialized in bench)
- Deployment manifest: `dummy_website/DEPLOYMENT.json`

## Commands run

```bash
bench --site jomveo migrate
bench --site jomveo run-tests --app credit_management
bench --site jomveo run-tests --app dummy_website
bench --site jomveo execute credit_management.tasks.reconcile_recent_accounts
bench --site jomveo execute credit_management.tasks.generate_daily_credit_summary
bench --site jomveo execute credit_management.tasks.release_expired_reservations
bench --site jomveo execute credit_management.tasks.retry_failed_webhooks
bench --site jomveo execute credit_management.tasks.cleanup_old_integration_logs --kwargs "{'dry_run': True}"
```

## Results

```text
migrate: success
credit_management tests: 186 passed (~86s)
dummy_website tests: 20 passed (~2s) — includes 5 deadlock retry tests
reconcile_recent_accounts: Passed — 81 checked, 0 mismatches
generate_daily_credit_summary: completed — total_accounts=81
release_expired_reservations: released=0
retry_failed_webhooks: attempted=0
cleanup_old_integration_logs (dry_run): eligible=1, deleted=0
```

## Issues found

* Integration logs were append-only with no operator delete path — resolved via flagged cleanup task
* `dummy_website` had no git metadata — resolved with local git repo + `DEPLOYMENT.json`
* Deadlock retry `rollback()` in tests rolled back uncommitted job rows — tests fixed with `frappe.db.commit()` before settlement

## Required fixes before wider rollout

* Monitor deadlock Error Log after adding pilot users; stop expansion if retries exhaust frequently
* Push `dummy_website` to a remote git repository (currently bench-local only)
* Schedule `cleanup_old_integration_logs` only after operator approves retention policy on each site
* Keep REST/webhooks disabled until explicit security review

## Readiness decision

Choose one:

* **Ready for limited expansion**
* Needs operations fixes
* Blocked

**Recommendation: Ready for limited expansion** — operations tooling, docs, retry safety, and monitoring paths are in place for controlled pilot growth.

## Next recommended milestone

Milestone 15: Performance and Scale Testing