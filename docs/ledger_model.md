# Ledger Model

> Status: Gates 2–9 — production append-only ledger

## Principles

- **Append-only:** Submitted `Credit Ledger Entry` rows are never amended or cancelled.
- **Source of truth:** Expected balances are derived by replaying ledger rows.
- **Cached projection:** `Credit Account` balance fields are updated by services only.
- **Corrections:** `REVERSAL` entries (Gate 5) — not in-place edits.

## Entry types

| Entry Type | Current Balance Effect | Reserved Balance Effect | Used By | Notes |
|---|---|---|---|---|
| GRANT | +amount | — | `grant_credits` | May create expiry lot |
| CONSUME | −amount | — | `consume_credits` | Direct consume; FIFO lots if expiry on |
| REFUND | +amount | — | `refund_credits` | Non-expiring |
| ADJUST_IN | +amount | — | `adjust_credits` (positive) | Non-expiring |
| ADJUST_OUT | −amount | — | `adjust_credits` (negative) | |
| RESERVE | — | +amount | `reserve_credits` | Available decreases |
| RELEASE_RESERVE | — | −amount | `release_reservation`, partial consume | Available increases |
| CONSUME_RESERVE | −amount | −amount | `consume_reserved_credits` | Async finalize |
| EXPIRE | −amount | — | `expire_credits` scheduler | Lot-driven |
| TRANSFER_OUT | −amount | — | `transfer_credits` | Source account |
| TRANSFER_IN | +amount | — | `transfer_credits` | Target non-expiring |
| REVERSAL | Opposite of reversed entry's current effect | Opposite of reversed reserved effect | Service reversal API | Does not restore expiry lots |

**Available balance:** `current_balance - reserved_balance` (not a separate ledger type).

## Reversal behavior

Reversible types: `GRANT`, `CONSUME`, `REFUND`, `ADJUST_IN`, `ADJUST_OUT`, `TRANSFER_IN`, `TRANSFER_OUT`.

**Not reversible via standard reversal:** `RESERVE`, `RELEASE_RESERVE`, `CONSUME_RESERVE`, `EXPIRE`.

Reversal creates a new `REVERSAL` row linked to `reversed_entry`. Default idempotency key: `reversal:{entry.name}`.

**Known limitation:** Reversal adjusts cached balances but does **not** restore `Credit Expiry Lot` state. Reconciliation may detect lot/account drift after reversals (see [reconciliation.md](reconciliation.md)).

## Idempotency

- Optional `idempotency_key` on ledger rows
- Scoped per `entry_type` when checked
- Replay returns prior result with `idempotent_replay: True`
- Integration logs record `Replayed` status on replay

**Policy:** Use operation-specific keys per lifecycle step (reserve ≠ consume ≠ release).

## Reference fields

| Field | Purpose |
|---|---|
| `reference_doctype` / `reference_name` | Link to business document (job, invoice) |
| `source_app` | Consuming app identifier |
| `metadata_json` | Sanitized auxiliary data (not secrets) |
| `reversed_entry` | Link for REVERSAL rows |

If `reference_name` is provided without `reference_doctype`, integration logs store the name in request JSON only (Dynamic Link requires doctype).

## Immutability enforcement

1. `Credit Ledger Entry` controller blocks amend/cancel on submitted rows
2. `has_credit_ledger_permission` denies write/delete on submitted entries
3. Services create and submit entries; no external inserts

## Integration log relationship

When `enable_integration_logs` is on, public API operations create `Credit Integration Log` rows referencing `ledger_entry`, `credit_account`, or `reservation` where applicable. Logs are append-only and redact secrets.

## Anti-patterns

- **Do not** `frappe.get_doc("Credit Ledger Entry").insert()` from consuming apps
- **Do not** `frappe.db.set_value("Credit Account", ..., "current_balance", ...)`
- **Do not** use SQL `UPDATE tabCredit Account` for balance fixes

Use `credit_management.api` or authorized service paths only.