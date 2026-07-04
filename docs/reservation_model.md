# Reservation Model

> Status: Gates 3–9 — production reservation lifecycle

## Purpose

Reservations hold credits for **async workloads** (video jobs, AI generation, long exports) so credits are not spent until work succeeds, and can be returned on failure.

## Statuses

| Status | Meaning |
|---|---|
| Active | Hold in place; nothing consumed yet |
| Partially Consumed | Some amount consumed; remainder may be released |
| Consumed | Fully consumed |
| Released | Manually released (failure/cancel) |
| Expired | Scheduler released after `expires_at` |
| Cancelled | Released with cancel reason |

## Balance effects

| Operation | current_balance | reserved_balance | available_balance |
|---|---|---|---|
| Reserve | unchanged | +amount | −amount |
| Consume reserved | −consumed | −consumed | net unchanged from reserve |
| Release | unchanged | −released | +released |
| Partial consume | −actual | −actual; remainder released | restored for released portion |

## Reserve behavior

1. Lock account (`FOR UPDATE`)
2. Validate available balance
3. Allocate from expiry lots if enabled (FIFO)
4. Create `RESERVE` ledger entry
5. Create `Credit Reservation` + lot allocations
6. Update account reserved/available caches

Default `expires_at` from `Credit Settings.default_reservation_timeout_minutes` (default 30).

## Consume-reserved behavior

- `actual_amount` defaults to full remaining reservation
- Creates `CONSUME_RESERVE` ledger entry
- If `actual_amount` < remaining → auto `RELEASE_RESERVE` for difference (partial consume policy)
- Updates reservation `consumed_amount`, `released_amount`, status

## Release behavior

- Creates `RELEASE_RESERVE` ledger entry
- Releases remaining unconsumed amount
- Status: `Released`, `Expired`, or `Cancelled` based on reason/expiry

## Expiry scheduler

`tasks.release_expired_reservations` (hourly) releases Active reservations past `expires_at`.

**Worker crash flow:** If job never completes, reservation expires and credits return to available balance automatically.

## Lot allocation

When expiry is enabled, `Credit Reservation Lot Allocation` links reservation amounts to `Credit Expiry Lot` rows (FIFO). Release/consume updates lot `reserved_amount` accordingly.

## Async job pattern

```
estimate → reserve → [external work] → consume_reserved OR release_reservation
```

Each step uses its **own idempotency key**.

## Failure and retry

- Duplicate callback with same idempotency key → `idempotent_replay: True`, no double charge
- Never consume before provider confirms success
- Never reuse reserve key for consume operation

## Idempotency examples

```
video-job:VID-001:reserve
video-job:VID-001:consume-reserved
video-job:VID-001:release
```

See [video_generation_integration.md](video_generation_integration.md) for a complete example.