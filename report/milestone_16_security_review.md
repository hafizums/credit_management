# Milestone 16 Summary — Security Review

Date: 2026-07-05
Status: Complete
Production site: `jomveo`
Pilot app: `dummy_website` (video generation pilot integration)

## Completed

- Reviewed role/permission hooks, trusted Python API, REST layer, webhooks, secret redaction, reports, integration logs, consuming-app integration, and operational controls
- Ran required security grep checks across `credit_management` and `dummy_website`
- Added M16 security-focused test modules for credit app (14 tests) and pilot app (2 tests)
- Verified production `jomveo` settings: REST disabled, webhooks disabled, integration logs enabled
- Confirmed no code changes required for verified security defects; documented restrictions for wider pilot expansion
- Updated milestone index in `report/README.md` and `README.md`

## Files changed

### New

- `credit_management/tests/test_m16_security_review.py` — REST, redaction, desk access, report scope, ledger/account immutability tests
- `dummy_website/tests/test_m16_security_review.py` — owner isolation and duplicate callback tests
- `report/milestone_16_security_review.md` — this report

### Updated

- `report/README.md` — M16 index entry
- `README.md` — development status through M16

### Removed / Deprecated

- None

## Role and permission review

- **Credit User:** Own User-owned accounts only (read). Cannot mutate balances or credit documents. Cannot read other users’ ledger entries, integration logs, or webhook events via Desk (`get_list` / `has_permission`). Limited to Credit Balance Report and Credit Ledger Report (own-scoped).
- **Credit Manager:** Approved mutations via trusted API and REST (when enabled). Can read/manage operational audit data. Desk write on Credit Account status allowed; ledger append-only guards still apply.
- **Credit Auditor:** Read-only on credit documents and audit data. Cannot mutate via Desk or REST. Can call reconciliation REST endpoints when REST enabled.
- **Credit Developer:** Privileged read (same audit visibility as Auditor). No mutation unless also Credit Manager or System Manager. Cannot call REST mutations.
- **System Manager:** Broad Desk access but cannot edit submitted ledger entries or directly mutate cached balances (controller + permission hooks). Reconciliation remains detect-only.

Verified DocTypes: Credit Account, Credit Ledger Entry, Credit Reservation, Credit Grant, Credit Expiry Lot, Credit Transfer, Credit Integration Log, Credit Webhook Event, Credit Reconciliation Run, Credit Settings, reports, workspace links — consistent with Gate 6/7/8 behavior.

## Trusted Python API review

- **Server-side trust boundary:** `credit_management.api` is **not** whitelisted. Only `credit_management.rest_api` exposes optional HTTP wrappers.
- **ignore_permissions usage:** Intentional in service-layer writes (ledger, reservation, integration log, webhook, account creation). Documented in `docs/permissions.md` (D-060). Test/install/patch usage is expected.
- **Consuming app authorization:** `dummy_website` uses `frappe.session.user` as credit owner in `generate_video`; `resolve_owner()` blocks Guest when credit_management is enabled.
- **Direct ledger insert prevention:** No public API exposes arbitrary ledger insert; `CreditLedgerEntry` controller blocks post-submit mutation.
- **Cached-balance mutation prevention:** `CreditAccount._prevent_direct_balance_mutation()` unless `frappe.flags.allow_credit_balance_update`; Desk write blocked for Credit User (test_13).

## REST security review

- **Enabled by default:** No (`enable_rest_api = 0` on `jomveo`).
- **Disabled behavior:** All 12 whitelisted endpoints throw `PermissionError` via `ensure_rest_enabled()`.
- **Credit User:** Own `get_balance` only when REST enabled; mutations blocked.
- **Credit Manager:** Mutations allowed only when REST enabled.
- **Credit Auditor:** Read/reconcile only; mutations blocked.
- **Credit Developer:** Read/reconcile only; mutations blocked.
- **System Manager:** Mutations allowed when REST enabled (with Frappe session auth).
- **Decision:** **Keep disabled** on production pilot. Enable only after explicit security approval, internal network restriction, and role-scoped operational need.

## Webhook security review

- **Enabled by default:** No (`enable_webhooks = 0` on `jomveo`).
- **Payload sanitization:** Uses `IntegrationLogService.sanitize_payload` (nested + mixed-case keys redacted).
- **Missing target behavior:** Retry marks `Failed` with `No webhook target URL configured`; does not fake delivery.
- **Retry bounds:** `webhook_max_retries` honored; exhausted events remain `Failed`.
- **HMAC/signature status:** **Not implemented** (documented in `docs/webhooks.md`). No signature claim in code or tests.
- **Decision:** **Keep disabled** until HMAC/signature implementation and receiver security review.

## Secret redaction review

- **Integration logs:** `SENSITIVE_KEYS` redacted in `IntegrationLogService` before persistence.
- **Webhook payloads:** Same sanitizer via `WebhookService._serialize_payload`.
- **Nested keys:** Verified (M16 test_07, test_08).
- **Mixed-case keys:** Verified (`API_KEY`, `Access_Token`, `Webhook_Secret`, `Client_Secret`).
- **Error messages:** Integration log `error_message` stores exception text, not raw request secrets; REST throws generic permission messages.

## Report/data leakage review

- **Credit User reports:** Credit Balance Report and Credit Ledger Report only, scoped to own accounts; privileged reports blocked.
- **Privileged reports:** Credit Usage by App/Owner, Reservation Aging, Expired Credits, Reconciliation, Top Consumers, Grant/Transfer History — Manager/Auditor/Developer/System Manager only.
- **Integration logs:** Credit User blocked at Desk (`has_permission` false, `get_list` raises). DocType has no Credit User role permission row.
- **Webhook events:** Same restriction as integration logs.
- **Reconciliation reports:** Privileged only; reconciliation API is detect-only (no auto-repair).

**Note:** `frappe.get_all()` bypasses permission hooks (Frappe internal API). Desk and `frappe.get_list()` enforce restrictions. Consuming apps must not expose `get_all` results to end users.

## Consuming app security review

- **Owner enforcement:** `generate_video` passes `owner_user=frappe.session.user`; job `credit_account_owner` matches session user (M16 test_14).
- **Guest fallback:** Guest cannot charge credit_management accounts (`PermissionError`); legacy wallet path isolated when credit_management disabled.
- **Idempotency:** Keys include job name and operation (`video-job:{name}:reserve`, etc.).
- **Provider success/failure:** Failed provider releases reservation; success consumes reserved amount only.
- **Duplicate callbacks:** `complete_success` replay is idempotent (M16 test_15; Gate 12 pilot tests).
- **Stuck job recovery:** M14 recovery path does not consume without provider success (pilot + operations docs).

## Operational security review

- **Backup:** M13/M14 pilot checklist requires backup before expansion; not re-run destructively on `jomveo` during M16.
- **Cleanup task:** `cleanup_old_integration_logs` dry-run default; deletes integration logs only (not ledger).
- **Webhook helpers:** `cancel_exhausted_webhook_events` updates event status only.
- **Reconciliation:** Detect-only; mismatch reporting without silent balance repair.
- **Forbidden actions:** No production `UPDATE tabCredit Account` in code; documented anti-patterns only. **`pilot_manual_m12.py`** contains staging-only `DELETE` on ledger/reservation — must not run on production.

## Security search checks

```bash
grep -R "ignore_permissions=True" -n credit_management dummy_website || true
grep -R "frappe.whitelist" -n credit_management dummy_website || true
grep -R "api_key\|secret\|token\|authorization\|password\|access_token\|refresh_token\|client_secret\|webhook_secret" -n credit_management dummy_website || true
grep -R "UPDATE tabCredit Account" -n credit_management dummy_website README.md docs report || true
grep -R "frappe.db.sql" -n credit_management dummy_website || true
grep -R "delete" -n credit_management/credit_management/services credit_management/credit_management/tasks.py || true
```

Result:

```text
ignore_permissions=True: Service-layer writes (ledger, reservation, webhook, integration log, account), install/patches, tests, dummy_website job orchestration — intentional trusted-server usage per D-060.
frappe.whitelist: credit_management/rest_api.py (12 endpoints, no allow_guest); dummy_website/api/video.py (4 allow_guest endpoints); www/demo.py (POST guest). credit_management.api is NOT whitelisted.
Sensitive key grep: Matches in integration_log_service SENSITIVE_KEYS, docs, tests, demo bundle — no raw secrets stored in production code paths.
UPDATE tabCredit Account: Documentation/report anti-pattern warnings only (ledger_model.md, operations_runbook.md, reconciliation.md).
frappe.db.sql: Read-only report queries, reconciliation_service account listing, daily_summary, M15 load helpers; dummy_website/pilot_manual_m12.py staging DELETE (non-production).
delete in services/tasks: integration_log_cleanup_service deletes old Credit Integration Log rows only (operator task); no ledger deletion.
```

Assessment:

* No unauthorized balance mutation paths found in production code. REST and webhooks correctly gated off on `jomveo`. Permission hooks and report scoping behave as designed for Desk access. Staging manual script and guest whitelisted endpoints are documented operational/integration risks, not silent production defects.

## Tests run

```bash
bench --site jomveo migrate
bench --site jomveo run-tests --app credit_management
bench --site jomveo run-tests --app dummy_website
bench --site jomveo run-tests --app credit_management --module credit_management.tests.test_m16_security_review
bench --site jomveo run-tests --app dummy_website --module dummy_website.tests.test_m16_security_review
```

Result:

```text
migrate: OK (frappe, dummy_website, credit_management DocTypes)

credit_management (full): Ran 200 tests in 124.359s — OK
  (first run: 1 intermittent nested gate5 failure inside gate6 re-run harness; passed on immediate re-run)

dummy_website (full): Ran 22 tests in 49.988s — OK

credit_management.tests.test_m16_security_review: Ran 14 tests in 1.691s — OK
dummy_website.tests.test_m16_security_review: Ran 2 tests in 2.315s — OK
```

## Issues found

* Webhook HMAC/signature not implemented (known limitation; documented).
* `dummy_website/api/video.py` exposes `allow_guest=True` whitelisted methods — acceptable for legacy wallet demo; credit_management path requires login and blocks Guest charging.
* `pilot_manual_m12.py` contains destructive staging SQL — must remain staging-only.
* `frappe.get_all()` bypasses permission query hooks — Desk UI safe; avoid exposing in user-facing server endpoints.

## Required fixes before wider rollout

* Keep `enable_rest_api = 0` on production until explicit security approval and network controls are in place.
* Keep `enable_webhooks = 0` until HMAC/signature is implemented, tested, and receiver security is reviewed.
* Do not run `pilot_manual_m12.py` on production sites.
* Take site backup before each pilot expansion tranche (per `docs/pilot_expansion_checklist.md`).
* Ensure new consuming apps enforce session/owner checks before calling `credit_management.api` mutations.

## Security decision

**Approved with restrictions**

Wider pilot expansion may proceed on `jomveo` with REST and webhooks remaining disabled, no permission weakening, and operational restrictions above. **Not approved for wide production rollout.**

## Next recommended milestone

Milestone 17: Admin UX Polish