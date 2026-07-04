# Architecture

> Status: Gate 1 scaffold — content expanded in Gates 2–9.

## Principles

- `credit_management` owns the credit source of truth.
- Consuming apps integrate only through `credit_management.api`.
- The ledger is append-only.
- Cached account balances are derived from ledger operations.
- Reservations protect async jobs.
- Idempotency protects retries.

## Layers

1. **DocTypes** — data model and permissions
2. **services/** — all balance-changing business logic
3. **api.py** — stable public integration surface
4. **tasks.py** — scheduler entry points delegating to services

See `decision_log.md` for Gate 1 defaults.