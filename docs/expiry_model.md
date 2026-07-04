# Expiry Model

> Status: Gates 4–9 — FIFO expiry lots

## Components

| DocType | Role |
|---|---|
| **Credit Grant** | Records a grant with optional expiry; links to ledger GRANT |
| **Credit Expiry Lot** | Bucket of expiring balance with `expires_on` |

Expiry is active only when `Credit Settings.enable_credit_expiry` is enabled.

## Expiring vs non-expiring balance

| Source | Expiry lot created? |
|---|---|
| Grant with `expires_on` | Yes |
| Grant without `expires_on` | No (non-expiring) |
| Refund | No (non-expiring policy) |
| Positive adjustment | No (non-expiring) |
| Transfer target (TRANSFER_IN) | No (non-expiring policy) |
| Negative adjustment | N/A (reduces balance) |

## FIFO consumption

Active lots ordered by `expires_on asc, creation asc`. Direct consume and reserve operations draw from earliest lots first.

## Reservation lot allocation

`reserve_credits` allocates `reserved_amount` on lots. `consume_reserved_credits` and `release_reservation` update lot reserved/remaining amounts.

## Direct consume with lots

`consume_credits` decrements `remaining_amount` on lots FIFO before creating CONSUME ledger entry.

## Reserved consume with lots

`consume_reserved_credits` finalizes lot consumption tied to reservation allocations.

## Release from expired lots

If a lot is past `expires_on`, scheduler `expire_credits` creates EXPIRE ledger entries for available lot remainder.

## Expiry scheduler

`tasks.expire_credits` (daily) processes active lots where `expires_on < today`.

## Reconciliation warnings

Reconciliation compares:

- Lot `remaining_total` vs ledger-derived current
- Lot `reserved_total` vs account `reserved_balance`
- Gate 5 reversal may cause lot/account drift (warnings/mismatches in `Credit Reconciliation Run`)

Reconciliation is **detect-only** — no automatic lot repair.