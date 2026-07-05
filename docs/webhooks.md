# Webhooks

> Status: Milestone 14 — operations hardening (disabled in pilot)

## Enablement checklist (complete before enabling)

- [ ] Business approval for outbound event delivery
- [ ] **HTTPS** target URL reviewed and reachable from Frappe server
- [ ] Network allowlist / firewall rules documented
- [ ] Receiver idempotency on `(event_type, idempotency_key)` implemented
- [ ] **HMAC/signature verification planned** — not implemented in credit_management (see below)
- [ ] Retry and max-retry behavior understood ([Retry behavior](#retry-behavior))
- [ ] Monitoring for Failed/Pending events configured
- [ ] Pilot expansion checklist updated ([pilot_expansion_checklist.md](pilot_expansion_checklist.md))

## Enable webhooks

1. **Credit Settings** → check **Enable Webhooks**
2. Set **Webhook Target URL** for HTTP delivery (required for delivery; without URL events stay Pending)
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

## Monitoring Failed/Pending events

```bash
bench --site <site> execute credit_management.tasks.list_failed_webhook_events
bench --site <site> execute credit_management.tasks.retry_failed_webhooks
```

Filter in desk: **Credit Webhook Event** where `status` in (`Failed`, `Pending`).

Cancel exhausted events (dry-run first):

```bash
bench --site <site> execute credit_management.tasks.cancel_exhausted_webhook_events --kwargs "{'dry_run': true}"
```

## Missing target URL behavior

When `enable_webhooks = 1` and `webhook_target_url` is empty:

- Events are **created** as `Pending` (audit trail)
- HTTP delivery is **not attempted**
- `retry_failed_webhooks` marks failures with `No webhook target URL configured`

## Known limitation — no HMAC/signature

Webhook **signature verification is not implemented** in this version. Payloads are JSON POST without `X-Signature` or HMAC headers. Receivers must use network controls and idempotent processing. Do not enable on public endpoints without an explicit security plan.