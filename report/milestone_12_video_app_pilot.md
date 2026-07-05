# Milestone 12 Summary — Video App Pilot Integration

Date: 2026-07-05
Status: Complete
Credit app site: `credit-staging`
Video app repo/path: `/home/hafiz/frappe-bench/apps/dummy_website` (bench-local; no separate git remote)
Pilot user: `pilot-admin@credit-staging.local`

## Completed

- Integrated `dummy_website` (video generation demo app) with `credit_management` via trusted Python API (`import credit_management.api as credit_api`)
- Installed `dummy_website` on `credit-staging` alongside `frappe` and `credit_management`
- Added reservation-first video job orchestration (reserve → provider → consume/release)
- Added required credit fields on `Video Generation` DocType
- Seeded `AI_VIDEO` credit type and pilot grant helper
- Added 15 pilot integration tests covering reserve/consume/release/idempotency/reconciliation
- Added hourly `recover_stuck_video_jobs` scheduler for worker crash recovery
- Ran full staging verification: migrate, credit_management tests, dummy_website tests, scheduler smokes, manual pilot flows
- Fixed verified integration bug in `credit_management` reconciliation (`CONSUME_RESERVE` reserved-balance derivation)

## Video app changes

### New

- `dummy_website/services/credit_integration.py` — wraps `credit_management.api`; `AI_VIDEO` type; `source_app=video_generation`
- `dummy_website/services/video_provider.py` — mock provider with `[PILOT:FAIL]` and `[PILOT:PARTIAL:N]` prompt markers
- `dummy_website/services/video_job_service.py` — reservation-first orchestration (create → reserve → provider → consume/release)
- `dummy_website/tasks.py` — `recover_stuck_video_jobs` hourly scheduler
- `dummy_website/tests/test_video_credit_pilot.py` — 15 pilot integration tests
- `dummy_website/pilot_manual_m12.py` — manual pilot runner for staging validation

### Updated

- `dummy_website/doctype/video_generation/video_generation.json` — added `estimated_credit_cost`, `actual_credit_cost`, `credit_reservation`, `credit_status`, `credit_type`, `credit_account_owner`, `credit_error`, plus `model`, `resolution`, `provider_job_id`
- `dummy_website/doctype/video_generation_settings/video_generation_settings.json` — `use_credit_management`, `default_credit_type` (AI_VIDEO)
- `dummy_website/api/video.py` — uses `credit_management` when enabled; legacy wallet fallback for guests
- `dummy_website/install.py` — seeds `AI_VIDEO`, `grant_pilot_user_credits()`, `before_tests` hook
- `dummy_website/hooks.py` — `before_tests`, hourly `recover_stuck_video_jobs`

### Removed / Deprecated

- None removed. Legacy `Video Credit Wallet` retained as guest fallback only; logged-in users route through `credit_management`.

## Credit configuration

- Credit Type: `AI_VIDEO` (seeded on install if missing)
- Pilot grant: `grant_pilot_user_credits(owner_name="pilot-admin@credit-staging.local", amount=1000, idempotency_key="pilot-ai-video-grant-m12-manual")`
- REST enabled: **0** (disabled)
- Webhooks enabled: **0** (disabled)
- Integration logs enabled: **1** (audit logging on)

## Integration flow

- Reserve before provider call: `VideoJobService.reserve_before_provider` → `credit_api.reserve_credits`; stores `credit_reservation`, sets `credit_status=Reserved`, then starts provider
- Consume on success: `credit_api.consume_reserved_credits` with `actual_amount`; sets `credit_status=Consumed`, `status=Completed`
- Release on failure: `credit_api.release_reservation` when `credit_status=Reserved`; sets `credit_status=Released`, `status=Failed`, stores `credit_error`
- Partial consume: `consume_reserved_credits` with lower `actual_amount`; credit_management auto-releases remainder via `RELEASE_RESERVE` (no manual release after consume)
- Retry/idempotency: per-operation keys `video-job:{job.name}:reserve|consume-reserved|release`; duplicate calls return `idempotent_replay` without double mutation
- Worker crash / expiry handling: hourly `recover_stuck_video_jobs` re-inspects provider and settles credits; expired reservations handled by credit_management `release_expired_reservations`

## Tests run

```bash
bench --site credit-staging migrate
bench --site credit-staging run-tests --app credit_management
bench --site credit-staging run-tests --app dummy_website
bench --site credit-staging execute credit_management.tasks.reconcile_recent_accounts
bench --site credit-staging execute credit_management.tasks.generate_daily_credit_summary
bench --site credit-staging execute dummy_website.pilot_manual_m12.run
```

## Test result

* `credit_management`: **184 passed**, 0 failed (~109s)
* `dummy_website`: **15 passed**, 0 failed (~2s on clean re-run; one earlier run hit MariaDB deadlock on ledger naming — flaky under concurrent load, resolved on retry)
* `reconcile_recent_accounts`: **completed** — 727 accounts checked, 16 mismatches from prior test fixtures (not pilot account)
* `generate_daily_credit_summary`: **completed**
* Manual pilot runner: **passed** — success/fail/partial flows, duplicate callbacks, pilot reconciliation `Passed`

## Manual pilot checks

* Successful video: `VG-2026-07462` — `credit_status=Consumed`, `status=Completed`, consumed 3.0 credits
* Failed video: `VG-2026-07468` — `credit_status=Released`, `status=Failed`, balance unchanged after reserve+release
* Partial-cost video: `VG-2026-07474` — estimated 3.0, actual 1.0; auto-released 2.0 remainder; `credit_status=Consumed`
* Duplicate callback: success retry logged `Replayed` with no balance change; failure retry returned `idempotent_replay=true`
* Insufficient credit: covered by `test_10` — `InsufficientCreditError` before provider call
* Reconciliation: pilot account `CA-eb011db201622d3836f9` — `summary_status=Passed`, 0 mismatches
* Ledger report: 8 entries for pilot account — GRANT, RESERVE, CONSUME_RESERVE, RELEASE_RESERVE chain correct; reservations reference `Video Generation` jobs
* Integration log: `reserve_credits` rows reference video job names; `consume_reserved_credits` rows logged with `source_app=video_generation`

## Balance verification

* Starting balance: current=1000.0, reserved=0.0, available=1000.0
* After success: current=997.0, reserved=0.0, available=997.0 (−3.0 consumed)
* After failure: current=997.0, reserved=0.0, available=997.0 (reserve then release — net zero)
* After partial: current=996.0, reserved=0.0, available=996.0 (−1.0 consumed; 2.0 auto-released)
* Reserved balance: 0.0 after all flows settled
* Available balance: 996.0 final (1000 granted − 4 consumed lifetime)

## Issues found

* **Verified integration bug (fixed):** `ReconciliationService.derive_balances_from_ledger` used `if/elif` so `CONSUME_RESERVE` decreased `current_balance` but skipped `reserved_balance` decrease → reconciliation `Mismatch` after reserve+consume. Fixed by splitting current and reserved balance updates into separate `if` blocks in `credit_management/services/reconciliation_service.py`.
* **Test flakiness:** Occasional MariaDB `QueryDeadlockError` during concurrent `Credit Ledger Entry` naming in dummy_website test runs; passes on sequential re-run. Not a business-logic defect.
* **Staging noise:** `reconcile_recent_accounts` reports mismatches on accounts created by embedded credit_management test fixtures; pilot account reconciles clean when baselined separately.

## Gatekeeper decision requested

Choose one:

* **Ready for production pilot**
* Needs pilot fixes
* Blocked

**Recommendation: Ready for production pilot** — reservation-first flow, idempotency, partial consume, and reconciliation validated on staging with clean pilot account.

## Next recommended milestone

Milestone 13: Production Pilot