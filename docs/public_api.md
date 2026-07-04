# Public API

> Status: Gates 2–9 — production Python API with optional REST wrappers (Gate 8)

## API boundaries

```
credit_management.api       = trusted server-side Python API (primary integration surface)
credit_management.rest_api  = optional whitelisted REST wrapper with authorization checks
```

Call the Python API from **trusted server-side code** in consuming Frappe apps (controllers, background jobs, server scripts). REST is opt-in and disabled by default.

**Do not mutate Credit Account balances directly. Do not insert Credit Ledger Entry manually.**

```python
import credit_management.api as credit_api
```

---

## get_or_create_account

**Purpose:** Get or create a `Credit Account` for an owner + credit type (+ optional company).

**Parameters:**

| Name | Type | Required | Notes |
|---|---|---|---|
| `owner_doctype` | str | Yes | e.g. `User`, `Customer`, `Project` |
| `owner_name` | str | Yes | Owner document name or identifier |
| `credit_type` | str | Yes | e.g. `GENERAL` |
| `company` | str | No | Optional company scope |

**Returns:** `str` — Credit Account name (e.g. `CA-...`)

**Idempotency:** Deterministic account naming; safe to call repeatedly.

**Security:** Trusted server-side only. Not exposed on REST.

**Example:**

```python
account = credit_api.get_or_create_account("User", "user@example.com", "GENERAL")
```

**Failures:** Invalid credit type; account creation errors.

---

## get_balance

**Purpose:** Read cached balances for an account.

**Parameters:** Same owner/credit_type/company as `get_or_create_account`.

**Returns:**

```python
{
    "credit_account": "CA-...",
    "credit_type": "GENERAL",
    "current_balance": 100.0,
    "reserved_balance": 10.0,
    "available_balance": 90.0,
}
```

**Idempotency:** Read-only.

**Security:** Trusted server-side. REST: Credit User may read own `User` account only.

**Example:**

```python
balance = credit_api.get_balance("User", "user@example.com", "GENERAL")
assert balance["available_balance"] == balance["current_balance"] - balance["reserved_balance"]
```

**Failures:** Account does not exist (created implicitly by grant/reserve paths, not always by get_balance alone).

---

## grant_credits

**Purpose:** Add credits to an account (top-up, purchase, promotional grant).

**Parameters:**

| Name | Type | Required |
|---|---|---|
| `owner_doctype`, `owner_name`, `credit_type` | str | Yes |
| `amount` | float | Yes (> 0) |
| `reference_doctype`, `reference_name` | str | No |
| `expires_on` | date/str | No (creates expiry lot if expiry enabled) |
| `idempotency_key` | str | Recommended |
| `source_app` | str | No |
| `metadata` | dict | No (sanitized in integration logs) |

**Returns:** Ledger result dict + optional `credit_grant` when expiry lot created.

```python
{
    "credit_account", "credit_type", "ledger_entry", "entry_type": "GRANT",
    "amount", "current_balance", "reserved_balance", "available_balance",
    "balance_after", "idempotent_replay", "credit_grant"  # if expiry
}
```

**Idempotency:** Same key + same account replays prior GRANT result.

**Example:**

```python
credit_api.grant_credits(
    "User", "user@example.com", "GENERAL", 100,
    idempotency_key="billing:inv-1001:grant",
    source_app="billing_app",
)
```

**Failures:** `InvalidCreditAmountError`; suspended account.

---

## consume_credits

**Purpose:** Direct consumption (no prior reservation). Use for synchronous, immediate charges.

**Parameters:** Owner fields, `amount`, optional `reference_*`, `idempotency_key`, `source_app`, `metadata`.

**Returns:** Ledger result with `entry_type`: `CONSUME`.

**Idempotency:** Per-key replay safe.

**Example:**

```python
credit_api.consume_credits(
    "User", "user@example.com", "GENERAL", 5,
    idempotency_key="usage:session-42:consume",
)
```

**Failures:** `InsufficientCreditError`; `InvalidCreditAmountError`; suspended account.

---

## reserve_credits

**Purpose:** Hold credits for an async job before external work completes.

**Parameters:** Owner fields, `amount`, `expires_at` (optional), `reference_*`, `idempotency_key`, `source_app`, `metadata`.

**Returns:**

```python
{
    "credit_account", "credit_type", "reservation", "ledger_entry",
    "reserved_amount", "consumed_amount", "released_amount", "status",
    "current_balance", "reserved_balance", "available_balance", "idempotent_replay",
}
```

**Idempotency:** Per reservation key; replays same reservation.

**Example:**

```python
reserve = credit_api.reserve_credits(
    owner_doctype="User",
    owner_name="user@example.com",
    credit_type="GENERAL",
    amount=70,
    idempotency_key="video-job:VID-001:reserve",
    source_app="video_app",
)
job.credit_reservation = reserve["reservation"]
```

**Failures:** `InsufficientCreditError`; invalid amount.

---

## consume_reserved_credits

**Purpose:** Finalize charge after async success. Supports partial consume (auto-releases remainder).

**Parameters:**

| Name | Type | Required |
|---|---|---|
| `reservation_name` | str | Yes |
| `actual_amount` | float | No (defaults to full remaining) |
| `idempotency_key` | str | Recommended |
| `source_app`, `metadata` | | No |

**Returns:** Reservation result with `consume_ledger_entry`, optional `release_ledger_entry`.

**Idempotency:** Per consume key.

**Example:**

```python
credit_api.consume_reserved_credits(
    job.credit_reservation,
    actual_amount=70,
    idempotency_key="video-job:VID-001:consume-reserved",
)
```

**Failures:** `CreditReservationError` (wrong status, over-consume).

---

## release_reservation

**Purpose:** Return held credits after async failure or cancellation.

**Parameters:** `reservation_name`, optional `reason`, `idempotency_key`.

**Returns:** Reservation result with `release_ledger_entry`.

**Example:**

```python
credit_api.release_reservation(
    job.credit_reservation,
    reason="Provider timeout",
    idempotency_key="video-job:VID-001:release",
)
```

**Failures:** Terminal reservation states; invalid release amount.

---

## refund_credits

**Purpose:** Return credits to account (non-expiring policy).

**Parameters:** Owner fields, `amount`, `reference_*`, `idempotency_key`, `source_app`, `metadata`.

**Returns:** Ledger result with `entry_type`: `REFUND`.

**Example:**

```python
credit_api.refund_credits(
    "User", "user@example.com", "GENERAL", 10,
    idempotency_key="support:ticket-99:refund",
)
```

---

## adjust_credits

**Purpose:** Manual positive or negative adjustment with required `reason`.

**Parameters:** Owner fields, `amount` (positive or negative), `reason`, `idempotency_key`.

**Returns:** Ledger result with `ADJUST_IN` or `ADJUST_OUT`.

**Example:**

```python
credit_api.adjust_credits(
    "User", "user@example.com", "GENERAL", -2,
    reason="Manual correction per audit",
    idempotency_key="audit:adj-2026-001",
)
```

---

## transfer_credits

**Purpose:** Move credits between two accounts atomically.

**Parameters:** `from_account`, `to_account`, `credit_type`, `amount`, `reference_*`, `idempotency_key`.

**Returns:** Transfer result with source/target ledger entries. Target receives **non-expiring** balance.

**Example:**

```python
credit_api.transfer_credits(
    from_account, to_account, "GENERAL", 25,
    idempotency_key="pool:transfer-001",
)
```

**Failures:** Insufficient balance; same account; suspended accounts.

---

## expire_credits

**Purpose:** Run scheduled expiry for lots past `expires_on` (also called by daily scheduler).

**Parameters:** None.

**Returns:**

```python
{"status": "completed", "expired_count": N, "skipped": M, "errors": [...]}
```

**Example:**

```python
result = credit_api.expire_credits()
```

---

## reconcile_account

**Purpose:** Detect-only balance/lot consistency check for one account.

**Parameters:** `credit_account` (name).

**Returns:**

```python
{
    "status": "completed",
    "reconciliation_run": "CRR-...",
    "summary_status": "Passed" | "Mismatch",
    "checked_accounts": 1,
    "mismatch_count": 0,
    "accounts": [...],
}
```

**Note:** Does **not** repair balances.

**Example:**

```python
credit_api.reconcile_account("CA-0035a9ebaab50a959949")
```

---

## reconcile_all_accounts

**Purpose:** Detect-only check for all accounts.

**Returns:** Same batch shape as `reconcile_account`.

**Example:**

```python
credit_api.reconcile_all_accounts()
```

---

## Integration layer (Gate 8)

When enabled via Credit Settings:

- **Integration logs** — `Credit Integration Log` per logged operation
- **Webhooks** — `Credit Webhook Event` per event type
- **REST** — see [rest_api.md](rest_api.md)

Logged operations: grant, consume, reserve, consume_reserved, release, refund, adjust, transfer, expire, reconcile_account, reconcile_all_accounts.

## Common exceptions

| Exception | Typical cause |
|---|---|
| `InsufficientCreditError` | Not enough available balance |
| `InvalidCreditAmountError` | Zero or negative amount |
| `CreditAccountSuspendedError` | Account status suspended |
| `CreditReservationError` | Invalid reservation state |
| `DuplicateCreditOperationError` | Idempotency conflict |
| `CreditReconciliationError` | Invalid reconcile target |

See [developer_guide.md](developer_guide.md) and [video_generation_integration.md](video_generation_integration.md) for full integration patterns.