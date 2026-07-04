# Reservation Model

> Status: Gate 3 — implemented. Constraints below remain binding for future changes.

## Gate 3 constraints (approved)

1. **Do not change Gate 2 public behavior** unless fixing a bug. `get_or_create_account`, `get_balance`, `grant_credits`, and `consume_credits` semantics remain stable.

2. **Idempotency keys must be operation-specific.** A single business job may use distinct keys per lifecycle step, for example:
   - `video-job:VID-0001:reserve`
   - `video-job:VID-0001:consume-reserved`
   - `video-job:VID-0001:release`

   Reusing the same key across different operations must not replay the wrong ledger effect.

3. **Reserved consumption is not direct CONSUME.** `consume_reserved_credits` must not reuse direct-credit consume logic without correctly reducing `reserved_balance` (and updating `available_balance` consistently: `available = current - reserved`).

4. **Tests must cover an async-style reservation lifecycle.** Include reserve → consume-reserved and reserve → release paths, with idempotency and balance assertions at each step.

5. **Preserve the append-only ledger rule.** Reservation operations create new submitted ledger rows (`RESERVE`, `CONSUME_RESERVE`, `RELEASE_RESERVE`); no in-place edits or cancellations.

## Planned balance effects (Gate 3)

| Operation | `current_balance` | `reserved_balance` | `available_balance` |
|---|---|---|---|
| Reserve | unchanged | increases | decreases |
| Consume reserved | decreases | decreases (by consumed amount) | unchanged net effect from reserve |
| Release reservation | unchanged | decreases | increases |

Ledger remains source of truth; `Credit Account` fields stay cached projections updated only through service methods.