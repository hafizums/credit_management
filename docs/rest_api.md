# REST API

> Status: Gate 8–9 — optional, disabled by default

## Warning

```
credit_management.api       = trusted server-side Python API (use this in Frappe app code)
credit_management.rest_api  = optional HTTP wrappers — disabled unless explicitly enabled
```

**REST is disabled by default.** Enable only when required and protect with Frappe authentication, API keys, and network controls.

## Enable REST

1. Open **Credit Settings**
2. Check **Enable REST API**
3. Save

When disabled, all REST calls raise: `Credit Management REST API is disabled`

## Module path

Whitelisted methods: `credit_management.rest_api`

## Available endpoints

| Method | Maps to |
|---|---|
| `get_balance` | `api.get_balance` |
| `grant_credits` | `api.grant_credits` |
| `consume_credits` | `api.consume_credits` |
| `reserve_credits` | `api.reserve_credits` |
| `consume_reserved_credits` | `api.consume_reserved_credits` |
| `release_reservation` | `api.release_reservation` |
| `refund_credits` | `api.refund_credits` |
| `adjust_credits` | `api.adjust_credits` |
| `transfer_credits` | `api.transfer_credits` |
| `expire_credits` | `api.expire_credits` |
| `reconcile_account` | `api.reconcile_account` |
| `reconcile_all_accounts` | `api.reconcile_all_accounts` |

## Role authorization matrix

| Role | get_balance | Mutations | Reconcile |
|---|---|---|---|
| Credit User | Own User account only | Denied | Denied |
| Credit Manager | Yes | Yes | Yes |
| Credit Auditor | Yes | Denied | Yes |
| Credit Developer | Yes | Denied | Yes |
| System Manager | Yes | Yes | Yes |

## Example Frappe REST call

```bash
# POST /api/method/credit_management.rest_api.get_balance
curl -X POST https://<site>/api/method/credit_management.rest_api.get_balance \
  -H "Authorization: token <api_key>:<api_secret>" \
  -d 'owner_doctype=User&owner_name=user@example.com&credit_type=GENERAL'
```

```python
# From Frappe client (authenticated session)
frappe.call(
    "credit_management.rest_api.grant_credits",
    owner_doctype="User",
    owner_name="user@example.com",
    credit_type="GENERAL",
    amount=10,
    idempotency_key="rest:grant-001",
)
```

## Failure when REST disabled

```python
frappe.call("credit_management.rest_api.get_balance", ...)
# frappe.exceptions.PermissionError: Credit Management REST API is disabled
```

## Authentication hardening (recommendation)

- Use Frappe **API Key** + secret or site-approved session auth
- Do **not** expose mutation endpoints on public internet without VPN/firewall
- Gate 8 does **not** implement custom API-key middleware — relies on Frappe's standard auth
- Prefer Python API for server-to-server integration inside bench

## Security warnings

- Do not document or deploy REST mutations without TLS
- Do not embed secrets in client-side JavaScript
- Credit User cannot mutate via REST even when enabled