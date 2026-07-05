# Developer Guide

> Status: Gate 9 — integrating another Frappe app

## Quick start

```python
# your_app/job.py
import credit_management.api as credit_api

def charge_user(user_email, amount, job_id):
    return credit_api.consume_credits(
        "User", user_email, "GENERAL", amount,
        reference_doctype="Your Job DocType",
        reference_name=job_id,
        idempotency_key=f"your-app:{job_id}:consume",
        source_app="your_app",
    )
```

## Choosing owner model

`Credit Account` uses Dynamic Link (`account_owner_doctype`, `account_owner_name`):

| Owner | When to use |
|---|---|
| `User` | Per-user credits (most common) |
| `Customer` | CRM/billing per customer |
| `Project` | Project budget pools |
| `Department` | Internal cost centers |
| Custom DocType | Any stable business entity |

Account name is deterministic hash of owner + credit_type + company.

## Choosing credit type

- Start with seeded `GENERAL`
- Add types for separate pools (e.g. `VIDEO`, `API_TOKENS`)
- Configure `decimal_precision`, `allow_negative_balance` per type

## Idempotency keys

- **Required** for async/resumable workflows
- **Unique per operation step** (reserve ≠ consume)
- Suggested format: `{app}:{business_id}:{operation}`
- On replay, API returns `idempotent_replay: True`

## Reference fields

```python
credit_api.reserve_credits(
    ...,
    reference_doctype="Video Generation Job",
    reference_name=job.name,
)
```

Both `reference_doctype` and `reference_name` recommended for Dynamic Link traceability in integration logs.

## Async jobs

Use **reservation-first** — see [video_generation_integration.md](video_generation_integration.md).

## Service-layer imports

Prefer public API:

```python
import credit_management.api as credit_api  # recommended
```

Avoid importing services directly from consuming apps unless extending `credit_management` itself.

## Error handling

```python
from credit_management.exceptions import InsufficientCreditError, CreditManagementError

try:
    credit_api.consume_credits(...)
except InsufficientCreditError:
    frappe.throw("Not enough credits")
except CreditManagementError as exc:
    frappe.log_error(title="Credit API", message=str(exc))
    raise
```

## Testing integration

```python
# your_app/tests/test_credits.py
import credit_management.api as credit_api
from credit_management.install import seed_defaults

def setUp(self):
    seed_defaults()
    credit_api.grant_credits("User", "test@example.com", "GENERAL", 100,
                             idempotency_key="test:grant:1")
```

Run full platform tests: `bench --site <site> run-tests --app credit_management`

## Desk admin UX vs integration API

Milestone 17 adds Desk-only helpers (`credit_management.admin_ux`) for operators: top-up, refund, reservation release, balance inspection, reconciliation review.

**Consuming apps must not call `admin_ux` from client code.** Use `credit_management.api` from trusted server-side code in your app, with your own authorization checks.

## Avoid coupling

- Do not read/write `Credit Account` balance fields
- Do not depend on internal service class signatures
- Use `source_app` for attribution
- Use webhooks/logs for observability, not business logic
- Do not expose `admin_ux` whitelisted methods to untrusted browsers

## Examples index

| Scenario | Doc |
|---|---|
| Grant / balance / consume | [public_api.md](public_api.md) |
| Async video job | [video_generation_integration.md](video_generation_integration.md) |
| Permissions | [permissions.md](permissions.md) |
| REST (optional) | [rest_api.md](rest_api.md) |