# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Atomic credit transfers between accounts."""

import frappe
from frappe import _
from frappe.utils import flt

from credit_management.exceptions import InvalidCreditAmountError, InvalidCreditTransferError
from credit_management.services.account_service import AccountService
from credit_management.services.expiry_service import ExpiryService
from credit_management.services.ledger_service import LedgerService


class TransferService:
	@staticmethod
	def find_by_idempotency_key(idempotency_key):
		if not idempotency_key:
			return None
		name = frappe.db.get_value("Credit Transfer", {"idempotency_key": idempotency_key})
		return frappe.get_doc("Credit Transfer", name) if name else None

	@staticmethod
	def build_result_from_transfer(transfer, from_account, to_account, idempotent_replay=False):
		return {
			"credit_transfer": transfer.name,
			"from_credit_account": from_account.name,
			"to_credit_account": to_account.name,
			"credit_type": transfer.credit_type,
			"amount": flt(transfer.amount),
			"status": transfer.status,
			"transfer_out_ledger_entry": transfer.transfer_out_ledger_entry,
			"transfer_in_ledger_entry": transfer.transfer_in_ledger_entry,
			"source_current_balance": flt(from_account.current_balance),
			"source_available_balance": flt(from_account.available_balance),
			"target_current_balance": flt(to_account.current_balance),
			"target_available_balance": flt(to_account.available_balance),
			"idempotent_replay": idempotent_replay,
		}

	@staticmethod
	def transfer_credits(
		from_account,
		to_account,
		credit_type,
		amount,
		reference_doctype=None,
		reference_name=None,
		idempotency_key=None,
		source_app=None,
		metadata=None,
	):
		amount = flt(amount)
		if amount <= 0:
			frappe.throw(_("Transfer amount must be positive"), InvalidCreditAmountError)

		if from_account == to_account:
			frappe.throw(
				_("Source and target credit accounts must be different"),
				InvalidCreditTransferError,
			)

		if not frappe.db.exists("Credit Account", from_account):
			frappe.throw(
				_("Source credit account {0} does not exist").format(from_account),
				InvalidCreditTransferError,
			)

		if not frappe.db.exists("Credit Account", to_account):
			frappe.throw(
				_("Target credit account {0} does not exist").format(to_account),
				InvalidCreditTransferError,
			)

		AccountService.get_active_credit_type(credit_type)

		if idempotency_key:
			existing = TransferService.find_by_idempotency_key(idempotency_key)
			if existing:
				locked = AccountService.lock_accounts_in_order(
					existing.from_credit_account, existing.to_credit_account
				)
				return TransferService.build_result_from_transfer(
					existing,
					locked[existing.from_credit_account],
					locked[existing.to_credit_account],
					idempotent_replay=True,
				)

		locked = AccountService.lock_accounts_in_order(from_account, to_account)
		from_doc = locked[from_account]
		to_doc = locked[to_account]

		if from_doc.credit_type != credit_type or to_doc.credit_type != credit_type:
			frappe.throw(
				_("Both accounts must use credit type {0}").format(credit_type),
				InvalidCreditTransferError,
			)

		AccountService.validate_account_can_transfer(from_doc)
		amount = AccountService.round_amount(amount, from_doc.credit_type)
		AccountService.validate_sufficient_balance(from_doc, amount)

		transfer = frappe.get_doc(
			{
				"doctype": "Credit Transfer",
				"from_credit_account": from_account,
				"to_credit_account": to_account,
				"credit_type": credit_type,
				"amount": amount,
				"status": "Draft",
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"idempotency_key": idempotency_key,
				"source_app": source_app,
				"metadata_json": AccountService.serialize_metadata(metadata),
			}
		)
		transfer.flags.ignore_links = True
		transfer.insert(ignore_permissions=True)

		out_key = f"{idempotency_key}:transfer-out" if idempotency_key else None
		in_key = f"{idempotency_key}:transfer-in" if idempotency_key else None

		if ExpiryService.get_active_lots(from_doc.name, from_doc.credit_type):
			ExpiryService.consume_from_expiry_lots(from_doc, amount)

		source_balance = flt(from_doc.current_balance) - amount
		from_doc = AccountService.update_balances(from_doc, current_balance=source_balance)

		out_entry = LedgerService.create_and_submit_entry(
			from_doc,
			"TRANSFER_OUT",
			amount,
			reference_doctype="Credit Transfer",
			reference_name=transfer.name,
			source_app=source_app,
			idempotency_key=out_key,
			metadata=metadata,
		)

		target_balance = flt(to_doc.current_balance) + amount
		to_doc = AccountService.update_balances(to_doc, current_balance=target_balance)

		in_entry = LedgerService.create_and_submit_entry(
			to_doc,
			"TRANSFER_IN",
			amount,
			reference_doctype="Credit Transfer",
			reference_name=transfer.name,
			source_app=source_app,
			idempotency_key=in_key,
			metadata=metadata,
		)

		transfer.status = "Completed"
		transfer.transfer_out_ledger_entry = out_entry.name
		transfer.transfer_in_ledger_entry = in_entry.name
		transfer.save(ignore_permissions=True)

		return TransferService.build_result_from_transfer(transfer, from_doc, to_doc)