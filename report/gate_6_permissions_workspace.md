# Gate 6 Summary — Permissions and Workspace

Date: 2026-07-04
Status: Complete

## Completed
- Created production credit roles: Credit User, Credit Manager, Credit Auditor, Credit Developer (plus existing System Manager)
- Implemented `credit_management/permissions.py` with `has_permission` and `permission_query_conditions` hooks
- Updated DocType role permissions for all production credit DocTypes
- Registered permission hooks in `credit_management/hooks.py`
- Preserved ledger append-only controller rules and Credit Account balance mutation guards
- Finalized Credit Management workspace with production links, shortcuts, number cards, and Recent Transfers quick list
- Added Gate 6 permission/workspace test suite (19 tests) including Gate 2–5 regression checks
- Updated `docs/permissions.md`, `docs/decision_log.md`, and `README.md`

## Files changed

### New
- `credit_management/permissions.py` — ownership and role permission hooks
- `credit_management/patches/v1_0/seed_gate6_workspace.py` — roles, number cards, workspace sync
- `credit_management/tests/test_gate6_permissions_workspace.py` — Gate 6 test suite (19 tests)
- `report/gate_6_permissions_workspace.md` — this report

### Updated
- `credit_management/hooks.py` — permission hook registration
- `credit_management/install.py` — `seed_credit_roles()`
- `credit_management/patches.txt` — Gate 6 workspace patch
- `credit_management/credit_management/workspace/credit_management/credit_management.json` — production navigation
- `credit_management/credit_management/doctype/credit_account/credit_account.json` — role permissions
- `credit_management/credit_management/doctype/credit_ledger_entry/credit_ledger_entry.json` — role permissions
- `credit_management/credit_management/doctype/credit_reservation/credit_reservation.json` — role permissions
- `credit_management/credit_management/doctype/credit_grant/credit_grant.json` — role permissions
- `credit_management/credit_management/doctype/credit_expiry_lot/credit_expiry_lot.json` — role permissions
- `credit_management/credit_management/doctype/credit_transfer/credit_transfer.json` — role permissions
- `credit_management/credit_management/doctype/credit_type/credit_type.json` — role permissions
- `credit_management/credit_management/doctype/credit_settings/credit_settings.json` — role permissions
- `docs/permissions.md` — role matrix and policy documentation
- `docs/decision_log.md` — Gate 6 decisions D-056 through D-064
- `README.md` — permissions doc link and gate status
- `report/README.md` — Gate 6 status

### Removed / Deprecated
- None

## Roles implemented
- Credit User: Read own accounts, ledger, reservations, grants, expiry lots, and transfers; no mutations; no Credit Settings
- Credit Manager: Read all; grant/refund/adjust/transfer/release via Desk permissions; manage Credit Type and account status; no destructive ledger edits
- Credit Auditor: Read all credit data; export/report; no mutations
- Credit Developer: Read configuration and credit data for integration/debug; no balance mutations
- System Manager: Full administrative DocType access; ledger append-only controller rules still apply

## Permission behavior
- Credit Account: Credit User ownership filter; privileged roles read all; balance writes blocked by controller; Manager may update status
- Credit Ledger Entry: Credit User reads own account entries; Auditor/Manager/Developer read all; submitted entry edits denied by hook + controller
- Credit Reservation: Ownership filter for Credit User; Manager may manage; Auditor read-only
- Credit Grant: Ownership filter for Credit User; Manager may create/manage; Auditor read-only
- Credit Expiry Lot: Ownership filter for Credit User; Manager may manage; Auditor read-only
- Credit Transfer: Credit User reads transfers where source or target account is owned; Manager may create/manage; Auditor read-only
- Credit Settings: Manager/Auditor/Developer read; System Manager write; Credit User denied

## Service-layer API permission policy
- Internal API behavior: `credit_management.api` service methods continue to perform balance-changing operations for trusted server-side integrations
- Desk/DocType permission behavior: Frappe UI and direct DocType access governed by roles + hooks + controllers
- Any intentional use of ignore_permissions: Service-layer inserts/saves use `ignore_permissions=True` by design; documented in `docs/permissions.md` (D-060)

## Workspace behavior
- Production links: Credit Account, Credit Ledger Entry, Credit Reservation, Credit Grant, Credit Expiry Lot, Credit Transfer, Credit Type, Credit Settings
- Dashboard/shortcut changes: Added number cards (Total Credit Accounts, Active Reservations, Credits Reserved, Credits Consumed Today, Credits Expired Today) and Recent Transfers quick list; expanded shortcuts
- Old MVP link check: `Credit Transaction` and `Credit Management Settings` excluded; patch strips stale DB links

## Tests run

```bash
bench --site jomveo migrate
bench --site jomveo run-tests --app credit_management
bench --site jomveo run-tests --app credit_management --module credit_management.tests.test_gate6_permissions_workspace
```

## Test result

* **Migrate:** Passed (role permissions synced; Gate 6 workspace/number cards patch applied)
* **Full app tests:** **118 passed, 0 failed, 0 skipped**
* **Gate 6 module tests:** **19 passed, 0 failed, 0 skipped** (includes Gate 2–5 regression subtests)

## Risks or unresolved decisions

* Public `credit_management.api` remains server-trusted and bypasses Desk permissions by design; consuming apps must enforce their own authorization
* Ownership model assumes `account_owner_doctype == User`; other owner DocTypes are visible only to privileged roles
* Number cards provide lightweight counters; richer dashboard/reporting deferred to Gate 7
* Credit Developer read scope matches auditor for credit data today; tighter scoping can be added when integration logs land in Gate 8

## Next recommended gate

Gate 7: Reports and Reconciliation