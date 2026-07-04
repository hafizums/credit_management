# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Append-only ledger writes."""

import frappe
from frappe import _
from frappe.utils import flt

from credit_management.exceptions import LedgerReversalError
from credit_management.services.account_service import AccountService

ENTRY_TYPES = (
	"GRANT",
	"CONSUME",
	"REFUND",
	"ADJUST_IN",
	"ADJUST_OUT",
	"REVERSAL",
	"RESERVE",
	"RELEASE_RESERVE",
	"CONSUME_RESERVE",
	"EXPIRE",
	"TRANSFER_IN",
	"TRANSFER_OUT",
)

REVERSIBLE_ENTRY_TYPES = (
	"GRANT",
	"CONSUME",
	"REFUND",
	"ADJUST_IN",
	"ADJUST_OUT",
	"TRANSFER_IN",
	"TRANSFER_OUT",
)

CREDIT_ENTRY_TYPES = ("GRANT", "REFUND", "ADJUST_IN", "TRANSFER_IN")


class LedgerService:
	@staticmethod
	def find_by_idempotency_key(idempotency_key, entry_type=None):
		if not idempotency_key:
			return None

		filters = {"idempotency_key": idempotency_key, "docstatus": 1}
		if entry_type:
			filters["entry_type"] = entry_type

		name = frappe.db.get_value("Credit Ledger Entry", filters)
		if not name:
			return None

		return frappe.get_doc("Credit Ledger Entry", name)

	@staticmethod
	def build_result_from_entry(entry, account, idempotent_replay=False):
		return {
			"credit_account": entry.credit_account,
			"credit_type": entry.credit_type,
			"ledger_entry": entry.name,
			"entry_type": entry.entry_type,
			"amount": flt(entry.amount),
			"current_balance": flt(account.current_balance),
			"reserved_balance": flt(account.reserved_balance),
			"available_balance": flt(account.available_balance),
			"balance_after": flt(entry.balance_after),
			"idempotent_replay": idempotent_replay,
		}

	@staticmethod
	def create_and_submit_entry(
		account,
		entry_type,
		amount,
		*,
		reference_doctype=None,
		reference_name=None,
		source_app=None,
		idempotency_key=None,
		remarks=None,
		metadata=None,
		reversed_entry=None,
	):
		account = frappe.get_doc(account) if isinstance(account, str) else account
		amount = AccountService.round_amount(amount, account.credit_type)

		entry = frappe.get_doc(
			{
				"doctype": "Credit Ledger Entry",
				"credit_account": account.name,
				"credit_type": account.credit_type,
				"entry_type": entry_type,
				"amount": amount,
				"balance_after": flt(account.current_balance),
				"reserved_balance_after": flt(account.reserved_balance),
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"source_app": source_app,
				"idempotency_key": idempotency_key,
				"remarks": remarks,
				"metadata_json": AccountService.serialize_metadata(metadata),
				"reversed_entry": reversed_entry,
			}
		)
		try:
			entry.insert(ignore_permissions=True)
			entry.submit()
		except frappe.DuplicateEntryError:
			if idempotency_key:
				existing = LedgerService.find_by_idempotency_key(idempotency_key, entry_type=entry_type)
				if existing:
					return existing
			raise

		return entry

	@staticmethod
	def find_reversal_for_entry(entry_name):
		name = frappe.db.get_value(
			"Credit Ledger Entry",
			{"reversed_entry": entry_name, "entry_type": "REVERSAL", "docstatus": 1},
		)
		return frappe.get_doc("Credit Ledger Entry", name) if name else None

	@staticmethod
	def reverse_ledger_entry(
		entry_name,
		*,
		idempotency_key=None,
		remarks=None,
	):
		entry = frappe.get_doc("Credit Ledger Entry", entry_name)
		if entry.docstatus != 1:
			frappe.throw(
				_("Only submitted ledger entries can be reversed"),
				LedgerReversalError,
			)

		if entry.entry_type == "REVERSAL":
			frappe.throw(_("Cannot reverse a reversal entry"), LedgerReversalError)

		if entry.entry_type not in REVERSIBLE_ENTRY_TYPES:
			frappe.throw(
				_("Ledger entry type {0} cannot be reversed").format(entry.entry_type),
				LedgerReversalError,
			)

		existing_reversal = LedgerService.find_reversal_for_entry(entry.name)
		if existing_reversal:
			account = AccountService.lock_account(entry.credit_account)
			result = LedgerService.build_result_from_entry(
				existing_reversal, account, idempotent_replay=True
			)
			result["reversed_entry"] = entry.name
			return result

		reversal_key = idempotency_key or f"reversal:{entry.name}"
		existing = LedgerService.find_by_idempotency_key(reversal_key, entry_type="REVERSAL")
		if existing:
			account = AccountService.lock_account(entry.credit_account)
			result = LedgerService.build_result_from_entry(
				existing, account, idempotent_replay=True
			)
			result["reversed_entry"] = entry.name
			return result

		account = AccountService.lock_account(entry.credit_account)
		amount = flt(entry.amount)
		is_credit_entry = entry.entry_type in CREDIT_ENTRY_TYPES
		delta = amount if is_credit_entry else -amount
		new_balance = flt(account.current_balance) - delta

		if is_credit_entry:
			AccountService.validate_sufficient_balance(account, amount)

		lifetime_granted_delta = 0
		lifetime_consumed_delta = 0
		if entry.entry_type == "GRANT":
			lifetime_granted_delta = -amount
		elif entry.entry_type == "CONSUME":
			lifetime_consumed_delta = -amount

		account = AccountService.update_balances(
			account,
			current_balance=new_balance,
			lifetime_granted_delta=lifetime_granted_delta,
			lifetime_consumed_delta=lifetime_consumed_delta,
		)

		reversal = LedgerService.create_and_submit_entry(
			account,
			"REVERSAL",
			amount,
			reference_doctype="Credit Ledger Entry",
			reference_name=entry.name,
			idempotency_key=reversal_key,
			remarks=remarks or _("Reversal of {0}").format(entry.name),
			reversed_entry=entry.name,
		)

		result = LedgerService.build_result_from_entry(reversal, account)
		result["reversed_entry"] = entry.name
		return result