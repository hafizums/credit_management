# Pilot Expansion Checklist

> Status: Milestone 14 — controlled expansion only (not wide rollout)

Use this checklist before adding each new pilot user or expanding pilot duration.

## Pre-expansion

- [ ] **Backup completed** — `bench --site <site> backup --with-files`
- [ ] **Pilot users approved** — named list recorded (email + business owner)
- [ ] **Credit grants approved** — amount, credit type, idempotency key, reason documented
- [ ] **REST disabled** unless security review explicitly approved
- [ ] **Webhooks disabled** unless target URL + security plan reviewed ([webhooks.md](webhooks.md))
- [ ] **Consuming app version traced** — git commit or `DEPLOYMENT.json` recorded
- [ ] **Credit app version/commit recorded** — `git rev-parse HEAD` in `credit_management`

## Baseline (pilot accounts only)

- [ ] **Starting balance recorded** — `credit_api.get_balance` for each pilot user
- [ ] **Reconciliation baseline recorded** — `credit_api.reconcile_account(<pilot CA>)` → `Passed`
- [ ] **No test-fixture baseline** — do not use post-test-run site aggregates or deliberate mismatch fixtures

## Health checks

- [ ] **Scheduler jobs healthy** — `release_expired_reservations`, `reconcile_recent_accounts`, `generate_daily_credit_summary`
- [ ] **Integration logs monitored** — recent `Credit Integration Log` rows for `source_app=video_generation`
- [ ] **Stuck reservations checked** — `Credit Reservation` status Active on pilot jobs past SLA
- [ ] **Failed jobs checked** — `Video Generation` status Failed with `credit_status` Released/Failed
- [ ] **Deadlocks checked** — Error Log / integration failures for `QueryDeadlockError`; video jobs left in `Reserved` + `Processing`

## Post-expansion validation

- [ ] **Final reconciliation passed** — per pilot account after first real usage window
- [ ] **Ledger references video jobs** — reservations point to `Video Generation`
- [ ] **No double charge** — duplicate callback retries show `Replayed` / unchanged balance
- [ ] **Pilot limits respected** — total exposure within approved cap

## Commands

```bash
bench --site <site> migrate
bench --site <site> execute credit_management.tasks.reconcile_recent_accounts
bench --site <site> execute credit_management.api.reconcile_account --kwargs "{'credit_account':'<PILOT_CA>'}"
bench --site <site> execute credit_management.tasks.cleanup_old_integration_logs --kwargs "{'dry_run': true}"
bench --site <site> execute dummy_website.tasks.recover_stuck_video_jobs
```

## Grant pilot credits (example)

```python
import credit_management.api as credit_api

credit_api.grant_credits(
    "User",
    "<pilot-user-email>",
    "AI_VIDEO",
    <approved_amount>,
    idempotency_key="pilot-grant:<user>:<sequence>",
    source_app="pilot_setup",
    metadata={"reason": "<approved reason>", "approved_by": "<operator>"},
)
```

## Offboarding reference

See [operations_runbook.md](operations_runbook.md) — Pilot grant and offboarding workflow.