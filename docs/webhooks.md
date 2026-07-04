# Webhooks

> Status: Gate 8–9

## Enable webhooks

1. **Credit Settings** → check **Enable Webhooks**
2. Optionally set **Webhook Target URL** for HTTP delivery
3. Configure **Webhook Max Retries** and **Webhook Retry Interval (Minutes)**

## Policy

| Setting | Behavior |
|---|---|
| `enable_webhooks = 0` | No `Credit Webhook Event` rows created |
| `enable_webhooks = 1`, no URL | Events created as **Pending** (audit only) |
| `enable_webhooks = 1`, URL set | HTTP POST attempted; retries on failure |

## Event types

| Event | Trigger |
|---|---|
| `credit.granted` | `grant_credits` |
| `credit.consumed` | `consume_credits` |
| `credit.reserved` | `reserve_credits` |
| `credit.reservation_consumed` | `consume_reserved_credits` |
| `credit.reservation_released` | `release_reservation` |
| `credit.refunded` | `refund_credits` |
| `credit.adjusted` | `adjust_credits` |
| `credit.transferred` | `transfer_credits` |
| `credit.expired` | `expire_credits` |
| `credit.reconciliation_completed` | reconcile APIs |
| `credit.low_balance` | After balance decrease if threshold > 0 |

## Payload shape

HTTP POST body (when delivering):

```json
{
  "event_type": "credit.granted",
  "payload": {
    "credit_account": "CA-...",
    "amount": 100,
    "current_balance": 100
  },
  "idempotency_key": "optional",
  "source_app": "optional"
}
```

Stored `payload_json` is sanitized (secrets redacted).

## Statuses

| Status | Meaning |
|---|---|
| Pending | Created; not yet delivered (or awaiting retry) |
| Delivered | HTTP delivery succeeded |
| Failed | Delivery failed or max retries exceeded |
| Cancelled | Manually cancelled (operator) |

## Retry behavior

`tasks.retry_failed_webhooks` every 30 minutes:

- Processes Pending/Failed with `next_retry_at <= now`
- Skips Delivered and Cancelled
- Skips when `retry_count >= max_retries`
- Missing URL → Failed with `No webhook target URL configured`

## Idempotency

Webhook events may include `idempotency_key` from the originating API call. Receivers should deduplicate on `(event_type, idempotency_key)`.

## Example receiver expectations

```python
# Pseudocode — your external service
def handle_credit_webhook(body):
    event_type = body["event_type"]
    payload = body["payload"]
    # idempotent processing using body.get("idempotency_key")
```

## Security recommendations

- Use **HTTPS** endpoint only
- Verify source IP / network allowlist
- **No signature mechanism in Gate 8** — add shared-secret HMAC verification in your receiver or future enhancement
- Do not log raw webhook bodies containing secrets on receiver side

## Known limitation

Webhook **signature verification is not implemented** in this version. Document and plan HMAC header validation for production external endpoints.