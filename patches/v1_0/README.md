# v1.0 Patches

## Gate 1.5 — `remove_mvp_doctypes` (executed)

Removes legacy MVP artifacts:

- DocTypes: `Credit Transaction`, `Credit Account`, `Credit Management Settings`
- Tables dropped: `tabCredit Transaction`, `tabCredit Account`
- Singles cleaned: `Credit Management Settings`
- Workspace `Credit Management` removed from DB by patch, then re-synced as placeholder

**Idempotent:** safe if DocTypes/tables already absent.

## Gate 2 (planned)

- `seed_credit_types.py` — seed default Credit Types
- Production DocType JSON sync via migrate