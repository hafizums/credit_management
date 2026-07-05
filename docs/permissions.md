# Permissions

> Status: Gate 6 — production permission model

## Roles

| Role | Purpose |
|---|---|
| **Credit User** | End-user visibility of own credit balance and history |
| **Credit Manager** | Operational credit administration (grant, refund, adjust, transfer, release) |
| **Credit Auditor** | Read-only audit visibility across all credit data |
| **Credit Developer** | Integration/debug visibility on configuration and technical records |
| **System Manager** | Full Frappe administrative access |

`System Manager` is a standard Frappe role and retains full DocType access. Append-only ledger controller rules still apply to every role.

## Role matrix

| Capability | Credit User | Credit Manager | Credit Auditor | Credit Developer | System Manager |
|---|---:|---:|---:|---:|---:|
| Read own Credit Account / ledger / reservations / grants / lots / transfers | Yes | Yes | Yes | Yes | Yes |
| Read all credit accounts and history | No | Yes | Yes | Yes | Yes |
| Grant / refund / adjust / transfer credits (Desk) | No | Yes | No | No | Yes |
| Release reservations (Desk) | No | Yes | No | No | Yes |
| Manage Credit Type | No | Yes | No | Read | Yes |
| Read Credit Settings | No | Yes | Yes | Yes | Yes |
| Write Credit Settings | No | No | No | No | Yes |
| Edit cached account balances | No | No* | No | No | No* |
| Edit submitted ledger entries | No | No | No | No | No |
| Delete ledger audit history | No | No | No | No | No |

\*Balance fields are blocked by `CreditAccount` controller even when write permission exists. Mutations must go through `credit_management.api` services.

## Ownership rules

Credit User list and document access is scoped by account ownership:

- `Credit Account`: `account_owner_doctype == "User"` and `account_owner_name == session user`
- Account-linked DocTypes (`Credit Ledger Entry`, `Credit Reservation`, `Credit Grant`, `Credit Expiry Lot`): filtered by `credit_account` ownership
- `Credit Transfer`: readable when the user owns the source or target account

Privileged read roles (`Credit Manager`, `Credit Auditor`, `Credit Developer`, `System Manager`) bypass ownership filters.

## Implementation

Gate 6 uses a combined Frappe permission model:

1. **DocType role permissions** in JSON (`permissions` blocks per role)
2. **`permission_query_conditions` hooks** in `credit_management/permissions.py` for list-view filtering
3. **`has_permission` hooks** in `credit_management/permissions.py` for document-level enforcement
4. **Controller guards** on `Credit Account` (balance mutation) and `Credit Ledger Entry` (append-only submitted rows)

Hooks are registered in `credit_management/hooks.py`.

## Service-layer API permission policy

The public integration API (`credit_management.api`) intentionally uses `ignore_permissions=True` inside service methods so consuming apps can perform balance-changing operations through controlled service code rather than Desk form permissions.

This means:

- **Desk / DocType permissions** govern what users can see and change in the Frappe UI.
- **Service-layer APIs** are not blocked by Credit User desk permissions and must be called only from trusted server-side integration code.
- Gate 6 permission tests validate the **Desk permission layer** separately from service API behavior.

## Ledger immutability

- Submitted `Credit Ledger Entry` rows cannot be amended, cancelled, or edited (controller enforced).
- `has_credit_ledger_permission` returns `False` for write/cancel/amend/delete on submitted entries for all non-Administrator users.
- Corrections must use `REVERSAL` entries via service layer (Gate 5).

## Credit Account cached-balance edit restrictions

`CreditAccount.validate()` rejects direct changes to:

- `current_balance`
- `reserved_balance`
- `available_balance`
- `lifetime_granted`
- `lifetime_consumed`
- `lifetime_expired`

unless `frappe.flags.allow_credit_balance_update` is set by `AccountService.update_balances()`.

## Workspace behavior

The **Credit Management** workspace links and shortcuts include all production DocTypes:

- Credit Account, Credit Ledger Entry, Credit Reservation, Credit Grant, Credit Expiry Lot, Credit Transfer, Credit Type, Credit Settings

Stale MVP links (`Credit Transaction`, `Credit Management Settings`) are excluded.

Number cards provide lightweight operational counters; ten Script Reports available (Gate 7).

## REST authorization (Gate 8)

When `Credit Settings.enable_rest_api` is enabled, `credit_management.rest_permissions` enforces:

| Operation class | Credit User | Credit Manager | Credit Auditor | Credit Developer | System Manager |
|---|---|---|---|---|---|
| `get_balance` | Own User account only | Yes | Yes | Yes | Yes |
| Mutations (grant, consume, reserve, …) | No | Yes | No | No | Yes |
| Reconciliation REST | No | Yes | Yes | Yes | Yes |

REST disabled → all endpoints raise `PermissionError`.

See [rest_api.md](rest_api.md).

## Report permissions

- **Credit User:** Credit Balance Report, Credit Ledger Report (own accounts only via `report_utils.py`)
- **Privileged roles:** All ten reports

## Integration DocType access

`Credit Integration Log` and `Credit Webhook Event`: privileged read (Manager, Auditor, Developer, System Manager). Credit User has no access.

## Desk admin UX (Milestone 17)

Whitelisted helpers in `credit_management.admin_ux` wrap the trusted Python API for Desk operators. They are **not** a substitute for consuming-app integration.

| Action | Roles allowed | API used | Ledger entry |
|---|---|---|---|
| Top up credits | Credit Manager, System Manager | `grant_credits` | `GRANT` |
| Refund credits | Credit Manager, System Manager | `refund_credits` | `REFUND` |
| Release reservation | Credit Manager, System Manager | `release_reservation` | `RELEASE_RESERVE` |
| Balance quick view | Credit User (own User account), privileged roles (all) | read-only | — |
| Reconciliation review / re-run | Privileged read roles | `reconcile_account` (detect-only) | — |

Credit User cannot top up, refund, or release reservations. Reconciliation re-run never mutates cached balances.