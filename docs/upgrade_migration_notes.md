# Upgrade and Migration Notes

> Status: Gate 1.5–9

## Gate 1.5 — Legacy MVP removal

The original MVP used **different schema** from production. These were **removed** (not upgraded in place):

| Legacy MVP | Fate |
|---|---|
| MVP `Credit Account` table | **Dropped** (`drop_mvp_tables` patch) |
| `Credit Transaction` | **Removed** DocType + table dropped |
| `Credit Management Settings` | **Deleted** (replaced by `Credit Settings`) |
| `utils/credit.py` direct balance helpers | **Removed** |

Production `Credit Account` (Gate 2+) is a **new DocType** with ledger architecture — not a migration of MVP rows.

## Production DocTypes (post-cleanup)

Introduced across Gates 2–8:

- Credit Type, Credit Settings, Credit Account, Credit Ledger Entry
- Credit Reservation, Credit Reservation Lot Allocation
- Credit Grant, Credit Expiry Lot, Credit Transfer
- Credit Reconciliation Run
- Credit Integration Log, Credit Webhook Event (Gate 8)

## Patch strategy

`patches.txt`:

```
[pre_model_sync]
remove_mvp_doctypes, drop_mvp_tables

[post_model_sync]
seed_gate2_defaults, sync_gate2_workspace,
seed_gate6_workspace, seed_gate7_workspace, fix_workspace_content
```

Patches are idempotent. `bench migrate` applies on every upgrade.

## Existing sites

1. **Backup database** before first production migrate
2. Run `bench --site <site> migrate`
3. Verify workspace has no links to `Credit Transaction` or `Credit Management Settings`
4. Re-seed roles/types via `install.seed_defaults()` if needed

## Backup recommendation

```bash
bench --site <site> backup
```

Before upgrading across major gates or applying MVP cleanup patches.

## Known test-data residue

Development sites running gate tests accumulate:

- Many `CA-*` smoke accounts
- Deliberate mismatch fixtures (`current_balance = 777`)
- Pending/failed webhook events from Gate 8 tests

Safe to ignore for documentation/smoke; filter in production reconciliation.

## Verify migration

```bash
bench --site <site> migrate
bench --site <site> run-tests --app credit_management
```

Workspace check (Gate 6 test): no shortcuts/links to MVP DocTypes.

```python
# Quick check
import frappe
frappe.db.exists("DocType", "Credit Transaction")  # should be falsy
frappe.db.exists("DocType", "Credit Management Settings")  # should be falsy
frappe.db.exists("DocType", "Credit Settings")  # should be truthy
```