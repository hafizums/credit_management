# Architecture

> Status: Gates 2–9 — production architecture

## App boundaries

`credit_management` is the **credit source of truth**. Consuming Frappe apps (video generation, AI tools, internal services) integrate through:

- **`credit_management.api`** — trusted server-side Python API (primary)
- **`credit_management.rest_api`** — optional whitelisted REST wrappers (disabled by default)

Consuming apps must **not**:

- Update `Credit Account` balance fields directly
- Insert or edit `Credit Ledger Entry` rows manually
- Bypass services for balance mutations

## Layered architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Consuming app (server-side)                                │
│  import credit_management.api as credit_api                 │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  api.py + integration_logging.py                            │
│  Stable public surface; logging/webhooks on mutations       │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  services/                                                  │
│  account, ledger, grant, consume, reservation, expiry,      │
│  refund, adjustment, transfer, reconciliation,              │
│  integration_log, webhook, daily_summary                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│  DocTypes (MariaDB)                                         │
│  Credit Account, Credit Ledger Entry, Credit Reservation,   │
│  Credit Grant, Credit Expiry Lot, Credit Transfer, ...      │
└─────────────────────────────────────────────────────────────┘
```

### Optional layers (Gate 8)

| Layer | Module | Purpose |
|---|---|---|
| REST | `rest_api.py` + `rest_permissions.py` | Whitelisted HTTP access when enabled |
| Integration logs | `integration_log_service.py` | Audit API operations |
| Webhooks | `webhook_service.py` | Outbound event records and retries |
| Scheduler | `tasks.py` | Hourly/daily/cron delegated tasks |

## DocType model

| DocType | Role |
|---|---|
| Credit Type | Master data for credit categories |
| Credit Settings | Singleton configuration |
| Credit Account | Cached balances per owner + type |
| Credit Ledger Entry | Append-only balance audit trail |
| Credit Reservation | Async job credit holds |
| Credit Reservation Lot Allocation | Links reservations to expiry lots |
| Credit Grant | Grant record when expiry enabled |
| Credit Expiry Lot | FIFO expiring balance buckets |
| Credit Transfer | Transfer document |
| Credit Reconciliation Run | Reconciliation audit record |
| Credit Integration Log | API integration audit (Gate 8) |
| Credit Webhook Event | Outbound webhook audit (Gate 8) |

## Permission layers

1. **DocType JSON permissions** — role-based Desk access
2. **`permission_query_conditions`** — list-view ownership filters
3. **`has_permission`** — document-level checks
4. **Controllers** — append-only ledger, balance field guards on accounts
5. **REST authorization** — `rest_permissions.authorize()` when REST enabled
6. **Service layer** — `ignore_permissions=True` for trusted API writes

Desk permissions govern UI. The Python API is trusted server-side code and is not blocked by Credit User desk rules.

## Scheduler tasks

| Task | Schedule | Delegates to |
|---|---|---|
| `release_expired_reservations` | Hourly | `ReservationService` |
| `reconcile_recent_accounts` | Hourly | `ReconciliationService` |
| `expire_credits` | Daily | `ExpiryService` |
| `generate_daily_credit_summary` | Daily | `DailySummaryService` |
| `retry_failed_webhooks` | Every 30 min | `WebhookService` |

## Data flows

### Grant

```
api.grant_credits → GrantService → lock account → ledger GRANT → update balances
                  → (optional) Credit Grant + Credit Expiry Lot if expiry enabled
                  → integration log + webhook (if enabled)
```

### Direct consume

```
api.consume_credits → ConsumeService → lock account → FIFO lot consume (if expiry)
                    → ledger CONSUME → update balances
```

### Reserve → consume reserved (async success)

```
api.reserve_credits → RESERVE ledger → reserved_balance ↑, available ↓
api.consume_reserved_credits → CONSUME_RESERVE (+ optional RELEASE_RESERVE for remainder)
                             → current ↓, reserved ↓
```

### Reserve → release (async failure)

```
api.reserve_credits → RESERVE ledger
api.release_reservation → RELEASE_RESERVE → reserved ↓, available ↑
```

### Expiry (scheduled)

```
tasks.expire_credits → ExpiryService → EXPIRE ledger per expired lot
```

### Transfer

```
api.transfer_credits → TransferService → TRANSFER_OUT + TRANSFER_IN (atomic)
                     → target receives non-expiring balance (policy)
```

### Refund / adjust

```
api.refund_credits → REFUND ledger (non-expiring)
api.adjust_credits → ADJUST_IN or ADJUST_OUT
```

### Reconcile (detect-only)

```
api.reconcile_account → ReconciliationService → derive from ledger → compare cache
                      → Credit Reconciliation Run record (no repair)
```

## Why the ledger is append-only

- Complete audit trail for compliance and dispute resolution
- Concurrent operations use row locks + new entries, not in-place edits
- Corrections use `REVERSAL` entries (Gate 5), not amendments
- Submitted `Credit Ledger Entry` cannot be cancelled or amended (controller enforced)

## Why cached balances exist

- Fast `get_balance` without replaying entire ledger history
- Updated atomically inside services after each ledger write
- `available_balance = current_balance - reserved_balance`
- Reconciliation detects drift between cache and ledger-derived values

## Why reconciliation is detect-only

Automatic repair could mask bugs or unauthorized changes. Gate 7 records mismatches in `Credit Reconciliation Run` for manual investigation. Operators follow [operations_runbook.md](operations_runbook.md).

## Text diagrams

### Async job (reservation-first)

```
[Job Created] → estimate cost
      ↓
[Reserve credits] ──fail──→ insufficient balance → abort
      ↓ success
[Call external provider]
      ↓                    ↓
  [Success]            [Failure]
      ↓                    ↓
[Consume reserved]   [Release reservation]
```

### Balance projection

```
Ledger (source of truth) ──replay──→ expected balances
                                           ↓ compare
Credit Account (cache) ─────────────────→ mismatch? → Reconciliation Run
```

See [decision_log.md](decision_log.md) for policy decisions.