# Integration Layer

> Status: Gate 8–9

## Credit Integration Log

Append-only audit records (`CIL-{#####}`) for public API operations.

| Field | Purpose |
|---|---|
| operation | API function name |
| status | Success, Failed, Replayed, Blocked |
| request_json / response_json | Sanitized payloads |
| credit_account, ledger_entry, reservation | Links to outcomes |
| idempotency_key, source_app | Traceability |

**Immutable:** Cannot edit or delete after insert.

## Credit Webhook Event

Outbound event records (`CWE-{#####}`) for external integrations.

Delivery fields (`status`, `retry_count`, `last_error`, `next_retry_at`, `delivered_at`) may update; audit fields are immutable.

## Integration logging decorator

`integration_logging.with_integration_logging` wraps public API functions in `api.py`:

- Logs success/failure via `IntegrationLogService`
- Emits webhooks via `WebhookService` when enabled
- Checks low balance threshold after balance-decreasing ops

## Logged operations

`grant_credits`, `consume_credits`, `reserve_credits`, `consume_reserved_credits`, `release_reservation`, `refund_credits`, `adjust_credits`, `transfer_credits`, `expire_credits`, `reconcile_account`, `reconcile_all_accounts`

Not logged: `get_or_create_account`, `get_balance` (read-only).

## Failure logs

Exceptions during API calls create `Failed` logs with sanitized request and error message.

## Replayed / idempotent logs

Idempotent replay returns `idempotent_replay: True`; integration log status `Replayed`.

## Sanitization / redaction

Sensitive keys replaced with `[REDACTED]`:

`api_key`, `secret`, `token`, `authorization`, `password`, `provider_key`, `access_token`, `refresh_token`, `client_secret`, `webhook_secret`

Large JSON truncated at 50KB.

## Credit Settings

| Field | Default | Purpose |
|---|---|---|
| `enable_integration_logs` | 1 | Toggle API logging |
| `enable_webhooks` | 0 | Toggle webhook events |
| `enable_rest_api` | 0 | Toggle REST wrappers |
| `webhook_target_url` | empty | HTTP POST target |
| `webhook_max_retries` | 5 | Max delivery attempts |
| `webhook_retry_interval_minutes` | 30 | Retry backoff |
| `audit_log_retention_days` | 365 | Retention guidance |
| `low_balance_threshold_default` | 0 | `credit.low_balance` threshold |

## Performance

One `Credit Integration Log` insert per logged API call when enabled. High-volume apps should plan retention cleanup (see [operations_runbook.md](operations_runbook.md)).

## Retention recommendation

Purge or archive integration logs and webhook events older than `audit_log_retention_days` via scheduled job (operator-defined; not auto-implemented in Gate 8).