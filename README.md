# Credit Management

Reusable Frappe credit management platform for any consuming app. Provides an append-only ledger, cached account balances, async reservations, expiry lots, transfers, reconciliation, and an optional integration layer (logs, webhooks, REST).

**Supported Frappe version:** v14 (tested on Frappe 14.101.1)

## Safety principles

**Do not mutate Credit Account balances directly.**

**Do not insert Credit Ledger Entry manually from consuming apps.**

**Use `credit_management.api` for trusted server-side integration.**

**Use `credit_management.rest_api` only when REST is enabled and properly authorized.**

All balance changes must go through the public Python API or authorized REST wrappers. Cached balances are projections updated only by services. The ledger is append-only.

## Core concepts

| Concept | Description |
|---|---|
| **Credit Account** | One account per owner + credit type (+ optional company). Holds cached balances. |
| **Credit Ledger Entry** | Append-only audit row for every balance effect. |
| **Credit Reservation** | Holds credits for async jobs before consume or release. |
| **Credit Expiry Lot** | FIFO expiring balance tracking when expiry is enabled. |
| **Credit Type** | Configurable credit category (e.g. `GENERAL`). |
| **Idempotency key** | Retry-safe unique key per operation step. |

## Public Python API

```python
import credit_management.api as credit_api

account = credit_api.get_or_create_account("User", user_email, "GENERAL")
balance = credit_api.get_balance("User", user_email, "GENERAL")
credit_api.grant_credits("User", user_email, "GENERAL", 100, idempotency_key="topup-001")
```

See [docs/public_api.md](docs/public_api.md) for every function, parameters, return shapes, and examples.

## Reservation-first async workflow

For long-running jobs (video generation, AI tasks, exports):

1. **Grant** or ensure sufficient balance
2. **Reserve** credits before starting external work
3. On success → **consume reserved** credits
4. On failure → **release** reservation
5. Use **operation-specific idempotency keys** for every step

See [docs/video_generation_integration.md](docs/video_generation_integration.md).

## REST API (optional)

REST is **disabled by default**. Enable `Credit Settings.enable_rest_api` only when needed. Whitelisted wrappers live in `credit_management.rest_api` with role-based authorization. Do not expose mutation endpoints publicly without network and authentication controls.

See [docs/rest_api.md](docs/rest_api.md).

## Webhooks (optional)

Enable `Credit Settings.enable_webhooks` to record outbound `Credit Webhook Event` rows. Without `webhook_target_url`, events remain `Pending` for audit. Retries run every 30 minutes via scheduler.

See [docs/webhooks.md](docs/webhooks.md).

## Reports

Ten Script Reports are available from the Credit Management workspace (privileged roles; Credit User limited to Balance and Ledger reports scoped to own accounts):

- Credit Balance Report, Credit Ledger Report
- Credit Usage by App, Credit Usage by Owner
- Reservation Aging, Expired Credits, Reconciliation, Top Credit Consumers
- Credit Grant History, Credit Transfer History

## Installation

```bash
# From bench root
bench get-app <repo-url> credit_management   # or use existing apps/credit_management
bench --site <site> install-app credit_management
bench --site <site> migrate
```

Defaults seeded on install: `GENERAL` credit type, `Credit Settings`, credit roles, workspace.

## Test commands

```bash
bench --site <site> migrate
bench --site <site> run-tests --app credit_management
bench --site <site> run-tests --app credit_management --module credit_management.tests.test_gate8_integration_layer
```

See [docs/testing_guide.md](docs/testing_guide.md).

## Development status

| Gate / Milestone | Status |
|---|---|
| 0 Discovery | Complete |
| 1 Architecture Scaffold | Complete |
| 1.5 Legacy MVP Cleanup | Complete |
| 2 Core Ledger | Complete |
| 3 Reservations | Complete |
| 3.1 Reservation Public API Fix | Complete |
| 4 Expiry Lots | Complete |
| 4.1 Expiry Public API Cleanup | Complete |
| 5 Transfers and Adjustments | Complete |
| 6 Permissions and Workspace | Complete |
| 7 Reports and Reconciliation | Complete |
| 7.1 Reconcile Scheduler Fix | Complete |
| 8 Integration Layer | Complete |
| 9 Documentation and Example Integration | Complete |
| 10 Full Verification | Complete |
| 11 Controlled Staging Deployment | Complete |
| 12 Video App Pilot Integration | Complete |
| 13 Controlled Production Pilot | Complete |
| 14 Operations Hardening | Complete |

## Documentation index

| Document | Purpose |
|---|---|
| [architecture.md](docs/architecture.md) | System design and data flows |
| [public_api.md](docs/public_api.md) | Trusted Python API reference |
| [video_generation_integration.md](docs/video_generation_integration.md) | Async job integration example |
| [ledger_model.md](docs/ledger_model.md) | Ledger entry types and rules |
| [reservation_model.md](docs/reservation_model.md) | Reservation lifecycle |
| [expiry_model.md](docs/expiry_model.md) | Expiry lots and FIFO |
| [transfer_adjustment_model.md](docs/transfer_adjustment_model.md) | Transfers, refunds, adjustments |
| [permissions.md](docs/permissions.md) | Roles and authorization |
| [reconciliation.md](docs/reconciliation.md) | Balance checks (detect-only) |
| [integration_layer.md](docs/integration_layer.md) | Integration logs and settings |
| [rest_api.md](docs/rest_api.md) | Optional REST wrappers |
| [webhooks.md](docs/webhooks.md) | Webhook events and retries |
| [operations_runbook.md](docs/operations_runbook.md) | Day-2 operations |
| [pilot_expansion_checklist.md](docs/pilot_expansion_checklist.md) | Controlled pilot expansion |
| [developer_guide.md](docs/developer_guide.md) | Integrating another Frappe app |
| [testing_guide.md](docs/testing_guide.md) | Running tests and smoke checks |
| [upgrade_migration_notes.md](docs/upgrade_migration_notes.md) | MVP cleanup and migration |
| [decision_log.md](docs/decision_log.md) | Architecture decisions |

## License

MIT