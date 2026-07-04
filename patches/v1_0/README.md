# v1.0 Migration Plan (MVP → Production Platform)

## Context

`credit_management` is installed on site `jomveo` with MVP DocTypes:

- `Credit Account` (party/limit model)
- `Credit Transaction` (direct balance mutation)
- `Credit Management Settings` (singleton)

## Gate 2 execution plan

### Phase A — Backup & inventory

1. Export any MVP `Credit Account` / `Credit Transaction` rows (if present).
2. Document row counts in patch log.

### Phase B — Retire MVP DocTypes

| MVP DocType | Action | Replacement |
|---|---|---|
| `Credit Transaction` | Delete DocType + table `tabCredit Transaction` | `Credit Ledger Entry` |
| `Credit Management Settings` | Delete DocType + singles | `Credit Settings` |
| `Credit Account` | Delete DocType + table | New `Credit Account` (owner + credit_type model) |

### Phase C — Install production DocTypes

Gate 2 adds:

- `Credit Type`
- `Credit Account` (new schema)
- `Credit Ledger Entry`
- `Credit Settings`

### Phase D — Workspace

Replace workspace shortcuts to point at new DocTypes.

### Phase E — Code removal

Remove after patch succeeds:

- `credit_management/credit_management/utils/credit.py`
- MVP doctype folders under `doctype/credit_transaction/`, `doctype/credit_management_settings/`
- MVP `credit_account/` controllers tied to limit/outstanding model

### Safety rules

- Patches must be idempotent (`if frappe.db.exists(...)` guards).
- No direct SQL balance updates outside services.
- Run `bench --site jomveo migrate` and full test suite after patch.

## Patch files (to be added in Gate 2)

- `patches/v1_0/remove_mvp_doctypes.py`
- `patches/v1_0/seed_credit_types.py`