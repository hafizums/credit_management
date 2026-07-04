# Testing Guide

> Status: Gate 9

## Full test suite

```bash
bench --site <site> migrate
bench --site <site> run-tests --app credit_management
```

Expected: **184 tests** (includes Gate 8 integration layer + Gate 1–7 suites).

## Focused gate modules

```bash
bench --site <site> run-tests --app credit_management --module credit_management.tests.test_gate2_core_ledger
bench --site <site> run-tests --app credit_management --module credit_management.tests.test_gate3_reservations
bench --site <site> run-tests --app credit_management --module credit_management.tests.test_gate4_expiry_lots
bench --site <site> run-tests --app credit_management --module credit_management.tests.test_gate5_transfers_adjustments
bench --site <site> run-tests --app credit_management --module credit_management.tests.test_gate6_permissions_workspace
bench --site <site> run-tests --app credit_management --module credit_management.tests.test_gate7_reports_reconciliation
bench --site <site> run-tests --app credit_management --module credit_management.tests.test_gate8_integration_layer
```

## Smoke commands

```bash
bench --site <site> execute credit_management.tasks.expire_credits
bench --site <site> execute credit_management.tasks.reconcile_recent_accounts
bench --site <site> execute credit_management.tasks.generate_daily_credit_summary
bench --site <site> execute credit_management.tasks.retry_failed_webhooks
```

All should return `status: completed` (not stub).

## Running one test class method

```bash
bench --site <site> run-tests --app credit_management \
  --module credit_management.tests.test_gate8_integration_layer \
  --case TestGate8IntegrationLayer.test_03_integration_log_records_successful_grant
```

## Reading reports

Open reports from **Credit Management** workspace → **Reports** card. Credit User sees only Balance and Ledger reports for own accounts.

## Interpreting test-data mismatches

Gate 7 tests deliberately set `current_balance = 777` to verify mismatch detection. On dev sites:

- `reconcile_recent_accounts` may report many mismatches — **expected**
- `summary_status: Mismatch` in smoke output is not necessarily a production bug
- Filter by accounts created outside test runs for production validation

## Before commit

```bash
bench --site <site> migrate
bench --site <site> run-tests --app credit_management
```