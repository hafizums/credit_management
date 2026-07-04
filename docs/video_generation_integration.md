# Video Generation Integration

> Status: Gate 9 — generic async job example (not video-specific DocTypes)

This guide shows how a **generic video generation app** (or any long-running job app) integrates with `credit_management` using the **reservation-first** pattern.

## Recommended job fields

Add to your `Video Generation Job` DocType (or equivalent):

| Field | Type | Purpose |
|---|---|---|
| `estimated_credit_cost` | Float | Pre-job estimate |
| `actual_credit_cost` | Float | Final charged amount |
| `credit_reservation` | Link → Credit Reservation | Active hold |
| `credit_status` | Select | Integration state |

## Recommended credit_status values

| Status | Meaning |
|---|---|
| Not Reserved | Job created; no hold yet |
| Reserved | Credits held |
| Consumed | Success; credits charged |
| Released | Failure; hold returned |
| Refunded | Separate refund applied |
| Failed | Terminal failure state |

## Prerequisites

- User (or project) has sufficient balance (grant/top-up first if needed)
- Server-side code only — `import credit_management.api as credit_api`

## Success flow

```python
import credit_management.api as credit_api

OWNER_DOCTYPE = "User"
CREDIT_TYPE = "GENERAL"
JOB_ID = job.name

# 1. Ensure balance (grant if billing separately)
credit_api.grant_credits(
    OWNER_DOCTYPE, job.owner, CREDIT_TYPE, 1000,
    idempotency_key=f"billing:{JOB_ID}:grant",
    source_app="video_app",
)

# 2. Estimate and reserve BEFORE provider call
estimate = 70
job.estimated_credit_cost = estimate
job.credit_status = "Not Reserved"
job.save()

reserve = credit_api.reserve_credits(
    owner_doctype=OWNER_DOCTYPE,
    owner_name=job.owner,
    credit_type=CREDIT_TYPE,
    amount=estimate,
    reference_doctype="Video Generation Job",
    reference_name=JOB_ID,
    idempotency_key=f"video-job:{JOB_ID}:reserve",
    source_app="video_app",
)
job.credit_reservation = reserve["reservation"]
job.credit_status = "Reserved"
job.save()

# 3. Call external provider
provider_result = call_video_provider(job)  # your code

# 4. On success — consume reserved
actual = provider_result.actual_cost  # e.g. 70
consume = credit_api.consume_reserved_credits(
    job.credit_reservation,
    actual_amount=actual,
    idempotency_key=f"video-job:{JOB_ID}:consume-reserved",
    source_app="video_app",
)
job.actual_credit_cost = actual
job.credit_status = "Consumed"
job.save()
```

## Failure flow

```python
# After reserve, provider fails:
credit_api.release_reservation(
    job.credit_reservation,
    reason="Provider render failed",
    idempotency_key=f"video-job:{JOB_ID}:release",
)
job.credit_status = "Released"
job.save()
```

## Partial cost flow

Reserve 100, actual cost 70:

```python
credit_api.consume_reserved_credits(
    job.credit_reservation,
    actual_amount=70,
    idempotency_key=f"video-job:{JOB_ID}:consume-reserved",
)
# Automatically releases remaining 30 via RELEASE_RESERVE
```

## Retry / idempotency flow

Duplicate worker callback with **same key** → safe replay:

```python
# Second call with same idempotency_key returns idempotent_replay: True
result = credit_api.consume_reserved_credits(
    job.credit_reservation,
    actual_amount=70,
    idempotency_key=f"video-job:{JOB_ID}:consume-reserved",  # same key
)
assert result.get("idempotent_replay") is True  # no double charge
```

## Worker crash flow

If worker dies after reserve:

- Hourly `release_expired_reservations` releases hold after `expires_at`
- Credits return to available balance
- Job should handle stale `Reserved` status on restart (check reservation status before re-reserving)

## Idempotency key naming

```
{business}:{job_id}:{operation}

Examples:
video-job:VID-2026-001:reserve
video-job:VID-2026-001:consume-reserved
video-job:VID-2026-001:release
billing:INV-1001:grant
```

**Never** reuse the same key across different operation types.

## Storing reservation on job

Always persist `reserve["reservation"]` on the job document before calling the provider. All subsequent steps use `job.credit_reservation`.

## Anti-patterns

| Anti-pattern | Why unsafe |
|---|---|
| `frappe.db.set_value("Credit Account", ..., "current_balance", ...)` | Bypasses ledger; breaks reconciliation |
| Manual `Credit Ledger Entry` insert | No balance cache update; audit gap |
| `consume_credits` before provider success | Charges user even if job fails |
| Missing idempotency keys | Retries double-charge |
| Reusing reserve key for consume | Wrong replay semantics |
| Calling REST mutations without authorization | Security violation |

## Grant and balance examples

```python
# Grant
credit_api.grant_credits("User", user, "GENERAL", 500, idempotency_key="topup:1")

# Balance check
balance = credit_api.get_balance("User", user, "GENERAL")
if balance["available_balance"] < estimate:
    frappe.throw("Insufficient credits")
```

See [public_api.md](public_api.md) and [developer_guide.md](developer_guide.md).