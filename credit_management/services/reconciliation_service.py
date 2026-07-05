# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Ledger-derived balance reconciliation and expiry-lot consistency checks."""

import json

import frappe
from frappe import _
from frappe.utils import add_to_date, flt, now_datetime

from credit_management.exceptions import CreditReconciliationError
from credit_management.services.account_service import AccountService
from credit_management.services.ledger_service import CREDIT_ENTRY_TYPES

CURRENT_INCREASE = frozenset({"GRANT", "REFUND", "ADJUST_IN", "TRANSFER_IN"})
CURRENT_DECREASE = frozenset({"CONSUME", "CONSUME_RESERVE", "ADJUST_OUT", "EXPIRE", "TRANSFER_OUT"})
RESERVED_INCREASE = frozenset({"RESERVE"})
RESERVED_DECREASE = frozenset({"RELEASE_RESERVE", "CONSUME_RESERVE"})
LIFETIME_GRANT_TYPES = frozenset({"GRANT"})
LIFETIME_CONSUMED_TYPES = frozenset({"CONSUME", "CONSUME_RESERVE"})
LIFETIME_EXPIRED_TYPES = frozenset({"EXPIRE"})

RECENT_WINDOW_HOURS = 24
MAX_DETAILS_JSON_LENGTH = 500000
MAX_STORED_ACCOUNT_DETAILS = 100

ACCOUNT_SUMMARY_KEYS = (
	"credit_account",
	"status",
	"expected_current_balance",
	"actual_current_balance",
	"expected_reserved_balance",
	"actual_reserved_balance",
	"expected_available_balance",
	"actual_available_balance",
	"current_difference",
	"reserved_difference",
	"available_difference",
	"mismatch_count",
	"error_count",
	"error",
)


class ReconciliationService:
	@staticmethod
	def is_enabled():
		return bool(frappe.get_single("Credit Settings").balance_reconciliation_enabled)

	@staticmethod
	def reconcile_account(credit_account):
		if not frappe.db.exists("Credit Account", credit_account):
			frappe.throw(
				_("Credit Account {0} does not exist").format(credit_account),
				CreditReconciliationError,
			)

		return ReconciliationService._run_reconciliation(
			run_type="Account",
			account_names=[credit_account],
		)

	@staticmethod
	def reconcile_all_accounts():
		account_names = frappe.get_all("Credit Account", pluck="name", order_by="name asc")
		return ReconciliationService._run_reconciliation(
			run_type="All Accounts",
			account_names=account_names,
		)

	@staticmethod
	def reconcile_recent_accounts(hours=None):
		hours = int(hours or RECENT_WINDOW_HOURS)
		since = add_to_date(now_datetime(), hours=-hours, as_datetime=True)
		account_names = frappe.db.sql(
			"""
			SELECT DISTINCT credit_account
			FROM `tabCredit Ledger Entry`
			WHERE modified >= %s
			ORDER BY credit_account
			""",
			(since,),
			pluck=True,
		)
		if not account_names:
			account_names = frappe.db.sql(
				"""
				SELECT name
				FROM `tabCredit Account`
				WHERE modified >= %s
				ORDER BY name
				""",
				(since,),
				pluck=True,
			)

		return ReconciliationService._run_reconciliation(
			run_type="Recent Accounts",
			account_names=account_names,
			remarks=f"Recent window: last {hours} hour(s)",
		)

	@staticmethod
	def _run_reconciliation(run_type, account_names, remarks=None):
		started_at = now_datetime()
		account_results = []
		mismatch_count = 0
		error_count = 0

		for account_name in account_names:
			try:
				result = ReconciliationService._check_account(account_name)
				account_results.append(result)
				if result["status"] == "Mismatch":
					mismatch_count += 1
				elif result["status"] == "Failed":
					error_count += 1
			except Exception as exc:
				error_count += 1
				account_results.append(
					{
						"credit_account": account_name,
						"status": "Failed",
						"error": str(exc),
					}
				)

		summary_status = ReconciliationService._summarize_status(
			account_results, mismatch_count, error_count
		)
		completed_at = now_datetime()

		if run_type == "Account" and account_results:
			primary = account_results[0]
			run_doc = ReconciliationService._create_run_doc(
				run_type=run_type,
				status=primary.get("status", summary_status),
				started_at=started_at,
				completed_at=completed_at,
				remarks=remarks,
				result=primary,
				checked_accounts=1,
				mismatch_count=1 if primary.get("status") == "Mismatch" else 0,
				error_count=1 if primary.get("status") == "Failed" else 0,
			)
		else:
			aggregate = ReconciliationService._aggregate_results(account_results)
			run_doc = ReconciliationService._create_run_doc(
				run_type=run_type,
				status=summary_status,
				started_at=started_at,
				completed_at=completed_at,
				remarks=remarks,
				result=aggregate,
				checked_accounts=len(account_names),
				mismatch_count=mismatch_count,
				error_count=error_count,
				account_results=account_results,
			)

		return {
			"status": "completed",
			"reconciliation_run": run_doc.name,
			"run_type": run_type,
			"summary_status": summary_status,
			"checked_accounts": len(account_names),
			"mismatch_count": mismatch_count,
			"error_count": error_count,
			"accounts": account_results,
		}

	@staticmethod
	def _check_account(account_name):
		account = frappe.get_doc("Credit Account", account_name)
		precision = (
			frappe.db.get_value("Credit Type", account.credit_type, "decimal_precision") or 2
		)
		derived = ReconciliationService.derive_balances_from_ledger(account_name)
		lot_summary, lot_issues = ReconciliationService.check_expiry_lots(account_name, account)
		lot_warnings = ReconciliationService.check_lot_account_consistency(
			account, derived, lot_summary
		)
		for warning in lot_warnings:
			lot_issues.append(warning)

		differences = {
			"current": flt(account.current_balance) - flt(derived["current_balance"]),
			"reserved": flt(account.reserved_balance) - flt(derived["reserved_balance"]),
			"available": flt(account.available_balance) - flt(derived["available_balance"]),
		}

		lifetime_warnings = ReconciliationService.check_lifetime_fields(account, derived, precision)

		mismatches = []
		for field, key in (
			("current_balance", "current"),
			("reserved_balance", "reserved"),
			("available_balance", "available"),
		):
			if not ReconciliationService._amounts_equal(
				account.get(field), derived.get(field), precision
			):
				mismatches.append(
					{
						"field": field,
						"cached": flt(account.get(field)),
						"expected": flt(derived.get(field)),
						"difference": differences[key],
					}
				)

		status = "Passed"
		if mismatches or lot_issues:
			status = "Mismatch"

		details = {
			"balance_checks": {
				"derived": derived,
				"cached": {
					"current_balance": flt(account.current_balance),
					"reserved_balance": flt(account.reserved_balance),
					"available_balance": flt(account.available_balance),
				},
				"mismatches": mismatches,
			},
			"lifetime_checks": {"warnings": lifetime_warnings},
			"lot_checks": {"summary": lot_summary, "issues": lot_issues},
			"lot_account_consistency": {"warnings": lot_warnings},
		}

		frappe.db.set_value(
			"Credit Account",
			account_name,
			"last_reconciled_on",
			now_datetime(),
			update_modified=False,
		)

		return {
			"credit_account": account_name,
			"status": status,
			"expected_current_balance": flt(derived["current_balance"]),
			"actual_current_balance": flt(account.current_balance),
			"expected_reserved_balance": flt(derived["reserved_balance"]),
			"actual_reserved_balance": flt(account.reserved_balance),
			"expected_available_balance": flt(derived["available_balance"]),
			"actual_available_balance": flt(account.available_balance),
			"current_difference": differences["current"],
			"reserved_difference": differences["reserved"],
			"available_difference": differences["available"],
			"lot_remaining_total": lot_summary["remaining_total"],
			"lot_reserved_total": lot_summary["reserved_total"],
			"lot_consumed_total": lot_summary["consumed_total"],
			"lot_expired_total": lot_summary["expired_total"],
			"mismatch_count": len(mismatches) + len(lot_issues),
			"error_count": 0,
			"details": details,
		}

	@staticmethod
	def derive_balances_from_ledger(account_name):
		entries = frappe.get_all(
			"Credit Ledger Entry",
			filters={"credit_account": account_name, "docstatus": 1},
			fields=["name", "entry_type", "amount", "reversed_entry"],
			order_by="creation asc, name asc",
		)

		reversed_entry_names = [
			entry.reversed_entry for entry in entries if entry.entry_type == "REVERSAL" and entry.reversed_entry
		]
		reversed_types = {}
		if reversed_entry_names:
			for row in frappe.get_all(
				"Credit Ledger Entry",
				filters={"name": ["in", reversed_entry_names]},
				fields=["name", "entry_type"],
			):
				reversed_types[row.name] = row.entry_type

		current_balance = 0
		reserved_balance = 0
		lifetime_granted = 0
		lifetime_consumed = 0
		lifetime_expired = 0

		for entry in entries:
			amount = flt(entry.amount)
			entry_type = entry.entry_type

			if entry_type == "REVERSAL":
				original_type = reversed_types.get(entry.reversed_entry)
				current_balance += ReconciliationService._reversal_current_delta(
					amount, original_type
				)
				if original_type in LIFETIME_GRANT_TYPES:
					lifetime_granted -= amount
				elif original_type in LIFETIME_CONSUMED_TYPES:
					lifetime_consumed -= amount
				continue

			if entry_type in CURRENT_INCREASE:
				current_balance += amount
			elif entry_type in CURRENT_DECREASE:
				current_balance -= amount

			if entry_type in RESERVED_INCREASE:
				reserved_balance += amount
			elif entry_type in RESERVED_DECREASE:
				reserved_balance -= amount

			if entry_type in LIFETIME_GRANT_TYPES:
				lifetime_granted += amount
			elif entry_type in LIFETIME_CONSUMED_TYPES:
				lifetime_consumed += amount
			elif entry_type in LIFETIME_EXPIRED_TYPES:
				lifetime_expired += amount

		return {
			"current_balance": flt(current_balance),
			"reserved_balance": flt(reserved_balance),
			"available_balance": flt(current_balance - reserved_balance),
			"lifetime_granted": flt(lifetime_granted),
			"lifetime_consumed": flt(lifetime_consumed),
			"lifetime_expired": flt(lifetime_expired),
		}

	@staticmethod
	def _reversal_current_delta(amount, original_type):
		if original_type in CREDIT_ENTRY_TYPES:
			return -flt(amount)
		if original_type in CURRENT_DECREASE:
			return flt(amount)
		return 0

	@staticmethod
	def check_expiry_lots(account_name, account):
		lots = frappe.get_all(
			"Credit Expiry Lot",
			filters={"credit_account": account_name},
			fields=[
				"name",
				"status",
				"remaining_amount",
				"reserved_amount",
				"consumed_amount",
				"expired_amount",
			],
		)

		summary = {
			"remaining_total": 0,
			"reserved_total": 0,
			"consumed_total": 0,
			"expired_total": 0,
		}
		issues = []

		for lot in lots:
			remaining = flt(lot.remaining_amount)
			reserved = flt(lot.reserved_amount)
			consumed = flt(lot.consumed_amount)
			expired = flt(lot.expired_amount)

			summary["remaining_total"] += remaining
			summary["reserved_total"] += reserved
			summary["consumed_total"] += consumed
			summary["expired_total"] += expired

			if remaining < 0:
				issues.append({"lot": lot.name, "issue": "negative_remaining_amount"})
			if reserved < 0:
				issues.append({"lot": lot.name, "issue": "negative_reserved_amount"})
			if reserved > remaining:
				issues.append({"lot": lot.name, "issue": "reserved_exceeds_remaining"})

			usable = remaining - reserved
			if lot.status in ("Exhausted", "Expired") and usable > 0:
				issues.append(
					{
						"lot": lot.name,
						"issue": "terminal_lot_has_usable_remaining",
						"usable_remaining": usable,
					}
				)

		if flt(account.reserved_balance) < flt(summary["reserved_total"]):
			issues.append(
				{
					"issue": "account_reserved_below_lot_reserved_total",
					"account_reserved": flt(account.reserved_balance),
					"lot_reserved_total": flt(summary["reserved_total"]),
				}
			)

		for key in summary:
			summary[key] = flt(summary[key])

		return summary, issues

	@staticmethod
	def check_lot_account_consistency(account, derived, lot_summary):
		warnings = []
		lot_remaining = flt(lot_summary["remaining_total"])
		cached_current = flt(account.current_balance)
		derived_current = flt(derived["current_balance"])

		if lot_remaining > cached_current + 0.0001:
			warnings.append(
				{
					"code": "lot_remaining_exceeds_account_current",
					"lot_remaining_total": lot_remaining,
					"account_current_balance": cached_current,
					"note": "May indicate Gate 5 reversal without expiry-lot restoration",
				}
			)

		if lot_remaining > derived_current + 0.0001:
			warnings.append(
				{
					"code": "lot_remaining_exceeds_ledger_derived_current",
					"lot_remaining_total": lot_remaining,
					"ledger_derived_current": derived_current,
				}
			)

		return warnings

	@staticmethod
	def check_lifetime_fields(account, derived, precision):
		warnings = []
		for field in ("lifetime_granted", "lifetime_consumed", "lifetime_expired"):
			if not ReconciliationService._amounts_equal(
				account.get(field), derived.get(field), precision
			):
				warnings.append(
					{
						"field": field,
						"cached": flt(account.get(field)),
						"derived": flt(derived.get(field)),
					}
				)
		return warnings

	@staticmethod
	def _amounts_equal(left, right, precision):
		return flt(left, int(precision)) == flt(right, int(precision))

	@staticmethod
	def _summarize_status(account_results, mismatch_count, error_count):
		if error_count and mismatch_count:
			return "Partial"
		if error_count:
			return "Failed"
		if mismatch_count:
			return "Mismatch"
		return "Passed"

	@staticmethod
	def _aggregate_results(account_results):
		if not account_results:
			return {
				"expected_current_balance": 0,
				"actual_current_balance": 0,
				"expected_reserved_balance": 0,
				"actual_reserved_balance": 0,
				"expected_available_balance": 0,
				"actual_available_balance": 0,
				"current_difference": 0,
				"reserved_difference": 0,
				"available_difference": 0,
				"lot_remaining_total": 0,
				"lot_reserved_total": 0,
				"lot_consumed_total": 0,
				"lot_expired_total": 0,
				"details": {"accounts": []},
			}

		def total(key):
			return flt(sum(flt(row.get(key, 0)) for row in account_results if "error" not in row))

		return {
			"expected_current_balance": total("expected_current_balance"),
			"actual_current_balance": total("actual_current_balance"),
			"expected_reserved_balance": total("expected_reserved_balance"),
			"actual_reserved_balance": total("actual_reserved_balance"),
			"expected_available_balance": total("expected_available_balance"),
			"actual_available_balance": total("actual_available_balance"),
			"current_difference": total("current_difference"),
			"reserved_difference": total("reserved_difference"),
			"available_difference": total("available_difference"),
			"lot_remaining_total": total("lot_remaining_total"),
			"lot_reserved_total": total("lot_reserved_total"),
			"lot_consumed_total": total("lot_consumed_total"),
			"lot_expired_total": total("lot_expired_total"),
			"details": {"accounts": account_results},
		}

	@staticmethod
	def _compact_account_row_for_storage(row, *, include_nested_details=False):
		compact = {key: row.get(key) for key in ACCOUNT_SUMMARY_KEYS if row.get(key) is not None}
		if include_nested_details and row.get("details"):
			compact["details"] = row["details"]
		return compact

	@staticmethod
	def _compact_details_for_storage(account_results):
		if not account_results:
			return {"accounts": []}

		non_passed = [row for row in account_results if row.get("status") != "Passed"]
		passed_count = len(account_results) - len(non_passed)
		stored = []

		for index, row in enumerate(non_passed):
			include_nested_details = index < 25
			stored.append(
				ReconciliationService._compact_account_row_for_storage(
					row,
					include_nested_details=include_nested_details,
				)
			)
			if len(stored) >= MAX_STORED_ACCOUNT_DETAILS:
				break

		details = {
			"accounts": stored,
			"storage_summary": {
				"total_accounts": len(account_results),
				"passed_count": passed_count,
				"mismatch_count": sum(1 for row in account_results if row.get("status") == "Mismatch"),
				"failed_count": sum(1 for row in account_results if row.get("status") == "Failed"),
				"stored_accounts": len(stored),
				"truncated": len(account_results) > len(stored) or passed_count > 0,
			},
		}

		serialized = json.dumps(details, default=str)
		if len(serialized) > MAX_DETAILS_JSON_LENGTH:
			details["accounts"] = [
				ReconciliationService._compact_account_row_for_storage(row)
				for row in stored[:50]
			]
			details["storage_summary"]["stored_accounts"] = len(details["accounts"])
			details["storage_summary"]["truncated"] = True
			details["storage_summary"]["size_truncated"] = True

		return details

	@staticmethod
	def _create_run_doc(
		*,
		run_type,
		status,
		started_at,
		completed_at,
		remarks,
		result,
		checked_accounts,
		mismatch_count,
		error_count,
		account_results=None,
	):
		details = result.get("details") or {}
		if account_results is not None:
			details = ReconciliationService._compact_details_for_storage(account_results)

		doc = frappe.get_doc(
			{
				"doctype": "Credit Reconciliation Run",
				"credit_account": result.get("credit_account"),
				"run_type": run_type,
				"status": status,
				"expected_current_balance": result.get("expected_current_balance"),
				"actual_current_balance": result.get("actual_current_balance"),
				"expected_reserved_balance": result.get("expected_reserved_balance"),
				"actual_reserved_balance": result.get("actual_reserved_balance"),
				"expected_available_balance": result.get("expected_available_balance"),
				"actual_available_balance": result.get("actual_available_balance"),
				"current_difference": result.get("current_difference"),
				"reserved_difference": result.get("reserved_difference"),
				"available_difference": result.get("available_difference"),
				"lot_remaining_total": result.get("lot_remaining_total"),
				"lot_reserved_total": result.get("lot_reserved_total"),
				"lot_consumed_total": result.get("lot_consumed_total"),
				"lot_expired_total": result.get("lot_expired_total"),
				"checked_accounts": checked_accounts,
				"mismatch_count": mismatch_count,
				"error_count": error_count,
				"started_at": started_at,
				"completed_at": completed_at,
				"remarks": remarks,
				"details_json": details,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc