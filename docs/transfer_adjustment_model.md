# Transfer and Adjustment Model

> Status: Gate 5–9

## Credit Transfer

Atomic movement between two `Credit Account` records:

1. Lock source and target accounts
2. Validate source available balance
3. Create `Credit Transfer` document
4. Ledger: `TRANSFER_OUT` (source) + `TRANSFER_IN` (target)
5. Update both account caches

**Policy:** Target receives **non-expiring** balance (no expiry lot on TRANSFER_IN).

## Refund

- Ledger: `REFUND`
- Increases `current_balance` and `lifetime_granted` tracking
- **Non-expiring** — no expiry lot created

## Adjustments

| Sign | Ledger type | Effect |
|---|---|---|
| Positive | `ADJUST_IN` | Increase balance (non-expiring) |
| Negative | `ADJUST_OUT` | Decrease balance |

Requires `reason` string. Use for audited manual corrections.

## Reversal pattern

Gate 5 supports reversing eligible ledger entries via service layer:

- Creates `REVERSAL` row linked to `reversed_entry`
- Idempotency: `reversal:{original_entry.name}`

**Limitations:**

- Does **not** restore expiry-lot state
- Does **not** reverse RESERVE / CONSUME_RESERVE / EXPIRE entries
- `Credit Transfer` status is **not** auto-marked `Reversed`

## Atomicity and locking

- `SELECT ... FOR UPDATE` on accounts before mutation
- Transfer commits both legs or fails
- Idempotency keys prevent duplicate transfer on retry

## Idempotency

Provide unique keys per business operation:

```python
credit_api.transfer_credits(..., idempotency_key="pool:move-2026-001")
credit_api.adjust_credits(..., idempotency_key="audit:adj-42")
```

## Known limitations

1. Transfer target balance is always non-expiring
2. Reversal does not restore expiry-lot allocations
3. Credit Transfer document status not automatically updated on reversal
4. Investigate lot drift via reconciliation after reversals