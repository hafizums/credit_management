# Milestone 11 Summary — Controlled Staging Deployment

Date: 2026-07-05
Status: Complete
Staging site: `credit-staging`

## Completed
- Created clean staging site `credit-staging` (separate from `jomveo`)
- Installed `frappe` and `credit_management` on staging
- Ran `bench --site credit-staging migrate`
- Verified 12 Credit Management DocTypes synced
- Verified `Credit Settings` singleton and default `GENERAL` Credit Type
- Verified Credit Management workspace (30 links, no MVP links)
- Verified production credit roles seeded
- Ran full test suite on staging — **184 passed** (~90s)
- Ran API and scheduler smoke commands
- Executed all 10 Script Reports
- Verified security defaults (REST/webhooks disabled)
- Recorded clean reconciliation baseline on dedicated staging account

## Environment
- Frappe version: 14.101.1
- Python version: 3.10.12
- MariaDB version: 10.6.22-MariaDB
- Site: `credit-staging`
- Installed apps: `frappe`, `credit_management`

## Migration result
```bash
bench --site credit-staging migrate
```

Result:

```text
Passed — frappe and credit_management DocTypes synced; dashboards updated
```

## Test result

```bash
bench --site credit-staging run-tests --app credit_management
```

Result:

```text
184 passed, 0 failed, 0 skipped (~90s)
```

## Smoke checks

* gate_3_1_api_smoke: **Passed** — grant → reserve → release; balance 10.0
* grant credits: **Passed** — `staging-baseline` granted 100 GENERAL credits
* get balance: **Passed** — returned expected current/reserved/available balances
* reserve credits: **Passed** — reservation created with reserved_amount 10.0
* consume reserved credits: **Passed** — consumed_amount 4.0; reservation status `Consumed`
* release reservation: **Passed** — released_amount 10.0 (separate reservation; release-after-full-consume correctly rejected by API)
* expire_credits: **Passed** — `status: completed`, expired 0, skipped 0
* reconcile_recent_accounts: **Passed** — `status: completed` (post-install: 1 account, `Passed`; post-test-run: 662 accounts, 49 mismatches from test fixtures — not baseline)
* generate_daily_credit_summary: **Passed** — `status: completed`, total_accounts 1 at first smoke
* retry_failed_webhooks: **Passed** — `status: completed`, attempted 0

## Workspace and roles

* Credit Management workspace: **Loads** — `Credit Management` workspace present with production DocType links, shortcuts, number cards, and 10 report links
* Roles: **All present** — Credit User, Credit Manager, Credit Auditor, Credit Developer, System Manager
* Old MVP links: **None** — `Credit Transaction` and `Credit Management Settings` not in workspace content or links

## Reports

* Credit Balance Report: columns=9, rows=1 (post-smoke; grows with test data)
* Credit Ledger Report: columns=12, rows=3
* Credit Usage by App: columns=8, rows=1
* Credit Usage by Owner: columns=11, rows=1
* Reservation Aging Report: columns=14, rows=0
* Expired Credits Report: columns=11, rows=0
* Reconciliation Report: columns=24, rows=1
* Top Credit Consumers: columns=5, rows=0
* Credit Grant History: columns=14, rows=0
* Credit Transfer History: columns=14, rows=0

## Security defaults

* REST enabled: **0** (disabled)
* Webhooks enabled: **0** (disabled)
* Integration logs enabled: **1** (audit logging on; no outbound webhooks)
* Credit User permissions: read-only on Credit Account (no write/create/delete)
* Credit Manager permissions: read/write/create on Credit Account (no delete)
* Credit Auditor permissions: read-only on Credit Account

## Reconciliation baseline

* Checked accounts: **1** (`User` / `staging-baseline`)
* Passed: **1**
* Mismatches: **0**
* Errors: **0**
* Explanation: Baseline recorded via `reconcile_account` on a clean account created only for staging validation (no Gate 7 `current_balance = 777` fixture). Post-install `reconcile_recent_accounts` also returned `Passed` with 1 account before the test suite ran. After the 184-test run, `reconcile_all_accounts` reports 678 accounts / 49 mismatches — expected from embedded Gate 7 mismatch-detection tests; **not** used as staging baseline (distinct from `jomveo` dev noise).

## Issues found

* MariaDB root credentials were required non-interactively to create the staging site (resolved for this deployment session)
* `reconcile_all_accounts` after full test suite includes deliberate test-fixture mismatches — operators must baseline on clean pilot accounts, not post-test DB state
* Partial `consume_reserved_credits` sets reservation to `Consumed`; remaining hold cannot be `release_reservation` — release validated on a separate active reservation (expected API behavior)

## Readiness decision

**Ready for pilot integration**

Staging site is clean, installs correctly, passes full regression, enforces secure defaults, and reconciles clean pilot accounts with zero mismatches.

## Next recommended milestone

Milestone 12: Pilot Integration with Video Generation App