# Gate 5 Summary — Transfers and Adjustments

Date: 2026-07-04
Status: Complete

## Completed
- Implemented `Credit Transfer` DocType with ledger entry links and idempotency key
- Implemented `RefundService`, `AdjustmentService`, and `TransferService`
- Wired public API functions `refund_credits`, `adjust_credits`, and `transfer_credits`
- Extended `LedgerService` with `TRANSFER_IN`/`TRANSFER_OUT` entry types and `reverse_ledger_entry()` helper
- Extended `AccountService` with `lock_accounts_in_order()` and `validate_account_can_transfer()`
- Added expiry-lot compatibility: FIFO source deduction on transfers and negative adjustments; non-expiring refunds and positive adjustments; non-expiring transfer target credits
- Documented Gate 5 policies in `docs/decision_log.md` (D-047 through D-055)
- Added Gate 5 test suite (29 tests) including Gate 2/3/4 regression checks
- Preserved Gate 2, Gate 3, and Gate 4 public API contracts and behavior

## Files changed

### New
- `credit_management/credit_management/doctype/credit_transfer/` — Credit Transfer DocType
- `credit_management/services/refund_service.py` — refund operations
- `credit_management/services/adjustment_service.py` — administrative adjustments
- `credit_management/tests/test_gate5_transfers_adjustments.py` — Gate 5 test suite (29 tests)
- `report/gate_5_transfers_adjustments.md` — this report

### Updated
- `credit_management/services/transfer_service.py` — full atomic transfer implementation
- `credit_management/services/ledger_service.py` — transfer entry types, reversal helper
- `credit_management/services/account_service.py` — deterministic multi-account locking, transfer validation
- `credit_management/credit_management/doctype/credit_ledger_entry/credit_ledger_entry.json` — `TRANSFER_IN`/`TRANSFER_OUT` options (from prior session)
- `credit_management/exceptions.py` — `InvalidCreditTransferError`, `LedgerReversalError` (from prior session)
- `credit_management/api.py` — Gate 5 API wiring; reconcile stubs deferred to Gate 7
- `credit_management/tests/test_gate1_scaffold.py` — stub test now targets `reconcile_account`
- `docs/decision_log.md` — Gate 5 decisions D-047 through D-055
- `report/README.md` — Gate 5 status

### Removed / Deprecated
- None

## Public API implemented
- refund_credits
- adjust_credits
- transfer_credits

## Transfer behavior
- Validation: amount > 0; accounts exist and differ; both accounts use requested `credit_type`; source account active; sufficient available balance unless negative balance allowed
- Atomicity: single transaction creates `Credit Transfer`, `TRANSFER_OUT`, `TRANSFER_IN`, and updates both account balances
- Idempotency: unique key on `Credit Transfer`; ledger keys `{key}:transfer-out` and `{key}:transfer-in`
- Row-locking order: `lock_accounts_in_order()` locks accounts sorted by name
- Expiry-lot policy: source deducts FIFO from active expiry lots; target receives non-expiring balance (no new expiry lot)

## Refund behavior
- Balance behavior: increases `current_balance` and `available_balance`
- Ledger behavior: creates submitted `REFUND` ledger entry
- Expiry-lot policy: non-expiring by default; no lot restoration
- Idempotency: unique key on `REFUND` ledger entry; replays return prior result

## Adjustment behavior
- Positive adjustment: `ADJUST_IN` ledger entry; increases balances; non-expiring
- Negative adjustment: `ADJUST_OUT` ledger entry; FIFO expiry-lot consumption then non-expiring pool; decreases balances; blocks insufficient balance unless negative balance allowed
- Reason requirement: non-empty `reason` stored in ledger `remarks`
- Expiry-lot policy: positive non-expiring; negative FIFO from active lots first
- Idempotency: operation-specific key on `ADJUST_IN` or `ADJUST_OUT` entry

## Reversal behavior
- Supported entry types: `GRANT`, `CONSUME`, `REFUND`, `ADJUST_IN`, `ADJUST_OUT`, `TRANSFER_IN`, `TRANSFER_OUT`
- Unsupported entry types: `RESERVE`, `RELEASE_RESERVE`, `CONSUME_RESERVE`, `EXPIRE`, `REVERSAL` (and already-reversed entries)
- Append-only behavior: creates new `REVERSAL` entry referencing `reversed_entry`; original entry unchanged
- Idempotency: default key `reversal:{entry.name}`; detects existing reversal via `reversed_entry` link

## Ledger behavior
- REFUND: credit to account; increases balance
- ADJUST_IN: credit to account; increases balance
- ADJUST_OUT: debit from account; decreases balance; absolute amount stored
- TRANSFER_OUT: debit from source; decreases source balance; references `Credit Transfer`
- TRANSFER_IN: credit to target; increases target balance; references `Credit Transfer`
- REVERSAL: opposite balance effect of supported original entry types; links `reversed_entry`

## Tests run

```bash
bench --site jomveo migrate
bench --site jomveo run-tests --app credit_management
bench --site jomveo run-tests --app credit_management --module credit_management.tests.test_gate5_transfers_adjustments
```

## Test result

* **Migrate:** Passed (`Credit Transfer` DocType synced; ledger entry types updated)
* **Full app tests:** **99 passed, 0 failed, 0 skipped**
* **Gate 5 module tests:** **29 passed, 0 failed, 0 skipped** (includes Gate 2, Gate 3, and Gate 4 regression subtests)

## Risks or unresolved decisions

* Reversal does not restore expiry-lot state; balance-only correction may desync lot totals from account balance in edge cases
* Refund lot-restoration metadata deferred; refunds always land in non-expiring pool
* Transfer target non-expiring policy means transferred expiring credits lose original expiry on recipient account
* `Credit Transfer` reversal status workflow (`Reversed`) not automated in Gate 5; use `LedgerService.reverse_ledger_entry()` on individual transfer ledger rows

## Next recommended gate

Gate 6: Permissions and Workspace