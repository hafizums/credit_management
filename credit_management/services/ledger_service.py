# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Append-only ledger writes."""

import frappe
from frappe.utils import flt

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
)


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