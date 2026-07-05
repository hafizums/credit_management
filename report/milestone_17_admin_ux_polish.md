# Milestone 17 Summary — Admin UX Polish

Date: 2026-07-05
Status: Complete
Production site: `jomveo`
Pilot app: `dummy_website` (video generation pilot integration)

## Completed

- Added Desk admin helpers (`credit_management.admin_ux`) wrapping trusted `credit_management.api` for top-up, refund, reservation release, balance inspection, and reconciliation review
- Created **Credit Admin Tools** Frappe page (`credit-admin-tools`) with sectioned wizards
- Added **Release Reservation** custom button on Credit Reservation form (Manager/System Manager)
- Expanded workspace metrics (Failed Webhook Events, Recent Reconciliation Mismatches, Low Balance Accounts)
- Added workspace shortcuts/links for reconciliation runs, integration logs, webhook events, admin tools, and key reports
- Updated operations, permissions, and developer documentation
- Added 14 M17 regression tests; full suites pass on `jomveo`
- REST and webhooks remain disabled on production (M16 restrictions unchanged)

## Files changed

### New

- `credit_management/admin_ux.py` — whitelisted Desk admin API wrappers
- `credit_management/credit_management/page/credit_admin_tools/credit_admin_tools.json`
- `credit_management/credit_management/page/credit_admin_tools/credit_admin_tools.js`
- `credit_management/public/js/credit_reservation_admin.js` — form release action
- `credit_management/patches/v1_0/seed_gate17_admin_ux.py` — number cards + workspace sync
- `credit_management/tests/test_m17_admin_ux.py`
- `report/milestone_17_admin_ux_polish.md`

### Updated

- `credit_management/workspace_content.py` — metrics, shortcuts, Admin Tools card
- `credit_management/hooks.py` — Credit Reservation client script
- `credit_management/patches.txt` — Gate 17 patch entry
- `docs/operations_runbook.md` — desk admin workflows
- `docs/permissions.md` — admin UX role matrix
- `docs/developer_guide.md` — admin_ux vs integration API boundary
- `README.md` — M16/M17 status, admin UX section, test command
- `report/README.md` — M17 index

### Removed / Deprecated

- None

## Index update

- **README:** Milestone 16 Security Review — Complete; Milestone 17 Admin UX Polish — Complete
- **report/README:** Milestone 16 — Complete; Milestone 17 — Complete

## Credit top-up UX

- **Implementation:** `admin_top_up_credits` + Credit Admin Tools → Top Up Credits section
- **Permission behavior:** Credit Manager / System Manager only; Credit User blocked (`PermissionError`)
- **Ledger behavior:** Calls `api.grant_credits`; creates submitted `GRANT` ledger entry; shows before/after balance; idempotency key auto-generated when omitted; grant reason stored in metadata
- **Tests:** `test_01`–`test_04`

## Refund UX

- **Implementation:** `admin_refund_credits` + Credit Admin Tools → Refund Credits section
- **Permission behavior:** Credit Manager / System Manager only; Credit User blocked
- **Ledger behavior:** Calls `api.refund_credits`; creates `REFUND` ledger entry (non-expiring policy unchanged)
- **Tests:** `test_05`, `test_06`

## Reservation release UX

- **Implementation:** `admin_release_reservation`, `admin_get_reservation_details`; Desk page + Credit Reservation form button
- **Permission behavior:** Credit Manager / System Manager only
- **Ledger behavior:** Calls `api.release_reservation`; creates `RELEASE_RESERVE` entry; does not delete reservation; blocks consumed/released reservations
- **Tests:** `test_07`, `test_08`

## Reconciliation mismatch review UX

- **Implementation:** `admin_get_reconciliation_review`, `admin_rerun_reconcile_account`; Credit Admin Tools → Reconciliation Review table
- **Detect-only behavior:** Re-run calls `reconcile_account`; `auto_repair_performed` always false; mismatches remain until investigated
- **Safe actions:** Open Credit Reconciliation Run, re-run detect-only reconcile, open Ledger Report filtered by account (no repair button)
- **Tests:** `test_09`, `test_10`

## Balance quick view

- **Implementation:** `admin_get_account_balance_overview`; Credit Admin Tools → Balance Quick View
- **Permission behavior:** Credit User — own User account only; privileged roles — any account
- **Fields shown:** current/reserved/available balances, lifetime granted/consumed/expired, active reservations, recent ledger entries
- **Tests:** `test_11`

## Workspace/dashboard polish

- **Shortcuts:** Credit Account, Credit Ledger Entry, Credit Reservation, Credit Grant, Credit Expiry Lot, Credit Transfer, Credit Reconciliation Run, Credit Integration Log, Credit Webhook Event, Credit Settings, Credit Admin Tools
- **Number cards:** Total Credit Accounts, Active Reservations, Credits Consumed Today, Credits Reserved, Credits Expired Today, Failed Webhook Events, Recent Reconciliation Mismatches, Low Balance Accounts (custom method using `low_balance_threshold_default`)
- **Old MVP link check:** No `Credit Transaction` or `Credit Management Settings` links (`test_13`)

## Documentation updates

- **Operations runbook:** Desk admin tools table, reconciliation review steps, top-up/refund/release guidance
- **Developer guide:** `admin_ux` is Desk-only; consuming apps use `credit_management.api`
- **Permissions:** Admin UX role matrix added
- **README:** Admin UX section, M16/M17 status, test module command

## Commands run

```bash
bench --site jomveo migrate
bench --site jomveo run-tests --app credit_management
bench --site jomveo run-tests --app dummy_website
bench --site jomveo run-tests --app credit_management --module credit_management.tests.test_m17_admin_ux
```

## Results

```text
migrate: OK (seed_gate17_admin_ux patch applied)

credit_management.tests.test_m17_admin_ux: Ran 14 tests in 78.859s — OK
  (includes nested Gate 6/8/M16 regression via test_14)

credit_management (full): Ran 214 tests in 256.269s — OK
dummy_website (full): Ran 22 tests in 3.973s — OK

Production settings unchanged:
  enable_rest_api = 0
  enable_webhooks = 0
```

## Issues found

- Low Balance Accounts number card uses `Credit Settings.low_balance_threshold_default`; returns 0 when threshold is 0 (documented limitation)
- Reconciliation review table parses `details_json` summary only; full details remain on Credit Reconciliation Run form

## Required fixes before wider rollout

- Keep REST and webhooks disabled per M16 security decision until explicitly approved
- Use Desk admin tools or trusted API for grants/refunds — never SQL balance edits
- Take site backup before each pilot expansion tranche
- Set `low_balance_threshold_default` if Low Balance Accounts card should be meaningful on production

## Readiness decision

**Ready for wider pilot expansion with improved admin UX**

Admin operators on `jomveo` can grant, refund, release reservations, inspect balances, and review reconciliation mismatches through Desk without weakening ledger, permission, or security controls. Not approved for wide production rollout.

## Next recommended milestone

Milestone 18: Advanced Billing / Payment Integration