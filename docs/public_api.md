# Public API

> Status: Gates 2–8 — production Python API with optional REST wrappers (Gate 8).

Entry point: `credit_management.api`

Consuming apps must not mutate balances or ledger rows directly.

## Integration layer (Gate 8)

- **Integration logs:** `Credit Integration Log` records public API operations when `Credit Settings.enable_integration_logs` is enabled. Payloads are sanitized before persistence.
- **Webhooks:** `Credit Webhook Event` records are created when `Credit Settings.enable_webhooks` is enabled. Without `webhook_target_url`, events remain `Pending` for audit only. Retries run via `credit_management.tasks.retry_failed_webhooks`.
- **REST:** Optional whitelisted endpoints in `credit_management.rest_api` when `Credit Settings.enable_rest_api` is enabled. Authorization rules are enforced per role before delegating to the Python API.