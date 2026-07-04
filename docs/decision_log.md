# Decision Log

## Gate 1 — Architecture Scaffold

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D-001 | Python import paths | `credit_management.api`, `credit_management.services.*` | Matches Frappe app package layout |
| D-002 | DocType module path | `credit_management/credit_management/credit_management/doctype/` | Required for Frappe module sync |
| D-003 | MVP DocTypes on jomveo | Migrate via `patches/v1_0/` in Gate 2 | App is installed; avoid silent data loss |
| D-004 | `Company` field | Optional Link; non-mandatory on Frappe-only bench | No ERPNext `Company` DocType detected |
| D-005 | Amount storage | Float + per-type `decimal_precision` | Frappe v14 Currency/Float compatibility |
| D-006 | Row locking | `SELECT ... FOR UPDATE` in services | MariaDB-safe concurrent balance updates |
| D-007 | Ledger immutability | Submitted entries; reversals via new rows | Append-only audit requirement |
| D-008 | Idempotency | Unique key on ledger/reservation when provided | Retry-safe async integrations |
| D-009 | Negative balance | Default deny; override per Credit Type | Safer default for reusable platform |
| D-010 | Consuming app integration | `credit_management.api` only | Prevents tight coupling and balance drift |
| D-011 | Scheduler wiring | Stub tasks in Gate 1; logic from Gate 3+ | Safe scaffold without side effects |
| D-012 | Git workflow | Recommend `git init` in app folder | Bench root is not a git repo today |

## Gate 1.5 — Legacy MVP Cleanup

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D-013 | MVP DocTypes | **Removed** — no backward compatibility | User decision; Gate 2 recreates production models |
| D-014 | MVP tables | **Dropped** `tabCredit Account`, `tabCredit Transaction` | Obsolete schema; idempotent patch; frees names for Gate 2 |
| D-015 | MVP singles | **Deleted** `Credit Management Settings` singles rows | Replaced by `Credit Settings` in Gate 2 |
| D-016 | MVP workspace | **Replaced** with placeholder (no DocType links) | Avoid broken sidebar links until Gate 2/6 |
| D-017 | `utils/credit.py` | **Removed** | Direct balance mutation violates ledger architecture |
| D-018 | `install.after_install` | **No-op** until Gate 2 seeding | No MVP settings to initialize |

## Gate 2 — Core Ledger

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D-019 | Account naming | Deterministic `CA-{sha256[:20]}` from owner + type + company | Enforces one-account uniqueness without a separate hash field |
| D-020 | Row locking | `frappe.get_doc("Credit Account", name, for_update=True)` | Issues `SELECT ... FOR UPDATE` on MariaDB before balance mutation |
| D-021 | Idempotency storage | Unique `idempotency_key` on submitted `Credit Ledger Entry` | Retry-safe grant/consume; replays return prior result |
| D-022 | Balance cache updates | `AccountService.update_balances()` with `frappe.flags.allow_credit_balance_update` | Blocks UI/direct mutation; allows controlled service writes |
| D-023 | Ledger immutability | Submittable `Credit Ledger Entry`; block amend/cancel in controller | Append-only audit trail; reversals deferred to Gate 5 |
| D-024 | Gate 2 seeding | `install.seed_defaults()` + `patches/v1_0/seed_gate2_defaults` | Seeds `GENERAL` type and `Credit Settings` on migrate |
| D-025 | `expires_on` on grant | Accepted but ignored until Gate 4 | Keeps public API stable without implementing expiry lots |
| D-026 | Generic owner identifiers | `ignore_links` on service-layer account insert | Dynamic Link field retained; API supports non-document owner IDs |
| D-027 | Balance cache writes | `frappe.db.set_value` in `update_balances()` | Avoids Dynamic Link re-validation on every grant/consume save |
| D-028 | Patch execution order | INI `patches.txt` with `[post_model_sync]` for seeding | Old-format patches ran before DocType sync and failed |

## Gate 3 — Prerequisites (approved constraints)

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D-029 | Gate 2 API stability | **No behavior changes** to Gate 2 public functions unless bugfix | Approved Gate 2 contract must not drift |
| D-030 | Idempotency key scope | **Operation-specific** keys per lifecycle step (`:reserve`, `:consume-reserved`, `:release`) | Prevents cross-operation replay collisions |
| D-031 | Reserved consume path | **Separate logic** from direct `CONSUME`; must reduce `reserved_balance` | Direct consume does not touch reserved balance |
| D-032 | Reservation tests | **Async-style lifecycle** tests (reserve → consume/release + idempotency) | Mirrors real integrating-app retry patterns |
| D-033 | Ledger immutability | **Append-only** preserved for reservation entry types | Consistent with D-007 / D-023 |

## Gate 3 — Reservations

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D-034 | Ledger entry type names | **Keep** `RESERVE`, `RELEASE_RESERVE`, `CONSUME_RESERVE` from Gate 2 select list | No rename needed; already committed in schema |
| D-035 | Partial consume policy | **Auto-release remainder** in same operation; final status `Consumed` | Matches recommended async workload pattern |
| D-036 | Partial consume idempotency | Primary key on `CONSUME_RESERVE`; auto-release uses `{key}:auto-release` | Operation-specific keys without collision |
| D-037 | Default reservation timeout | `Credit Settings.default_reservation_timeout_minutes`, fallback **60** minutes | Safe default when setting missing or zero |
| D-038 | Expire scheduler idempotency | `reservation:{name}:expire` on `RELEASE_RESERVE` | Safe to run hourly; replays skip existing ledger row |
| D-039 | Reserve owner links | `ignore_links` on reservation insert | Same generic-owner pattern as Gate 2 accounts |
| D-040 | Release status mapping | `Expired` (scheduler), `Cancelled` (reason contains cancel), else `Released` | Supports failure/cancel/timeout semantics |

## Gate 4 — Expiry Lots

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D-041 | `expires_on` with expiry disabled | Grant normally; **no** Credit Grant or expiry lot | Settings gate keeps non-expiring path simple |
| D-042 | FIFO consumption | Earliest `expires_on` first, then non-expiring pool | Standard expiry-lot semantics |
| D-043 | Reservation lot tracking | Child table `Credit Reservation Lot Allocation` | Links reserves/consumes/releases to specific lots |
| D-044 | Reserved expired-lot policy | Scheduler expires only `remaining - reserved`; release from past-expiry lot **expires immediately** | Reserved hold protected; released credits cannot return to usable pool |
| D-045 | Expire scheduler idempotency | `expiry-lot:{lot.name}:expire` on `EXPIRE` ledger entry | Safe for daily reruns |
| D-046 | Partial reserved consume release | Auto-release all unused allocation rows after consume | Consistent with Gate 3 auto-release policy |

## Gate 5 — Transfers and Adjustments

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D-047 | Refund expiry policy | **Non-expiring by default**; no lot restoration without explicit metadata | Safe default; avoids guessing consumed lot mapping |
| D-048 | Positive adjustment expiry | **Non-expiring** balance increase | Administrative credits should not inherit arbitrary expiry |
| D-049 | Negative adjustment expiry | **FIFO** consume from active expiry lots, then non-expiring pool | Matches Gate 4 consume semantics for deductions |
| D-050 | Transfer expiry policy | Source deducts **FIFO** from expiry lots; target receives **non-expiring** balance | Moves usable credits without copying lot expiry to recipient |
| D-051 | Transfer idempotency | Unique key on `Credit Transfer`; ledger keys `{key}:transfer-out` / `{key}:transfer-in` | Atomic replay without duplicate transfers or ledger rows |
| D-052 | Transfer row locking | `lock_accounts_in_order()` sorted by account name | Deterministic lock order prevents deadlocks |
| D-053 | Reversal scope | Support `GRANT`, `CONSUME`, `REFUND`, `ADJUST_IN`, `ADJUST_OUT`, `TRANSFER_IN`, `TRANSFER_OUT` | Gate 5 business entry types; append-only via new `REVERSAL` row |
| D-054 | Reversal limitations | **No** reservation or `EXPIRE` reversal; **no** expiry-lot restoration on reversal | Unsafe edge cases deferred; balance-only reversal effect |
| D-055 | Reversal idempotency | Default key `reversal:{entry.name}` on `REVERSAL` ledger entry | Safe retries without duplicate reversals |

## Gate 6 — Permissions and Workspace

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D-056 | Permission mechanism | DocType JSON role perms + `has_permission` + `permission_query_conditions` hooks | Maintainable Frappe v14 pattern; server-side enforcement beyond UI |
| D-057 | Credit User ownership | `account_owner_doctype == User` and `account_owner_name == session.user` | Generic owner model aligned with Gate 2 accounts |
| D-058 | Privileged read roles | `Credit Manager`, `Credit Auditor`, `Credit Developer`, `System Manager` bypass ownership filters | Manager/Auditor/Developer operational and audit needs |
| D-059 | Mutation roles | Only `Credit Manager` and `System Manager` may Desk-mutate operational credit DocTypes | Auditor/Developer remain read-only; Credit User read-only |
| D-060 | Service API permissions | Keep `ignore_permissions=True` in service-layer writes | Integration API remains server-trusted; Desk permissions are separate layer |
| D-061 | Ledger Desk hardening | `has_credit_ledger_permission` denies write/cancel/amend/delete on submitted entries | Complements controller append-only rules |
| D-062 | Balance edit hardening | Existing `CreditAccount` controller + no Credit User write perms | Prevents cached balance drift outside services |
| D-063 | Workspace | Production DocType links/shortcuts + number cards + Recent Transfers quick list | Gate 6 navigation finalized; no MVP links |
| D-064 | Dashboard cards | Lightweight `Number Card` counters now; richer reports deferred to Gate 7 | Operational visibility without full reconciliation reports |

## Gate 7 — Reports and Reconciliation

| ID | Decision | Choice | Rationale |
|---|---|---|---|
| D-065 | Reconciliation repair | **Detect only**; no automatic balance repair in Gate 7 | Mismatches must be visible; repairs require explicit future operation |
| D-066 | Ledger derivation | Replay submitted `Credit Ledger Entry` rows with Gate 5 `REVERSAL` policy | Deterministic expected balances from append-only ledger |
| D-067 | Lifetime checks | **Warnings only** in `details_json`; do not fail run solely on lifetime drift | Lifetime fields are secondary to current/reserved/available correctness |
| D-068 | Lot/account inconsistency | Promote Gate 5 reversal desync to mismatch issues | Do not hide lot-vs-account drift after non-lot-restoring reversals |
| D-069 | Credit User reports | `Credit Balance Report` and `Credit Ledger Report` only, with ownership filters | Safe user-level visibility; other reports privileged-only |
| D-070 | Reconciliation runs | Append-only `Credit Reconciliation Run` records; read-only after insert | Audit trail for checks without mutating source data |
| D-071 | Recent reconciliation | Hourly task reconciles accounts with ledger/account activity in last 24h | Bounded scheduler workload |