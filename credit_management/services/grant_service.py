# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Credit grant and top-up operations."""

import frappe
from frappe import _
from frappe.utils import flt

from credit_management.exceptions import InvalidCreditAmountError
from credit_management.services.account_service import AccountService
from credit_management.services.ledger_service import LedgerService


class GrantService:
	@staticmethod
	def grant_credits(
		owner_doctype,
		owner_name,
		credit_type,
		amount,
		reference_doctype=None,
		reference_name=None,
		expires_on=None,
		idempotency_key=None,
		source_app=None,
		metadata=None,
	):
		if expires_on is not None:
			# Expiry lots are implemented in Gate 4; ignore for now without failing callers.
			pass

		amount = flt(amount)
		if amount <= 0:
			frappe.throw(_("Grant amount must be positive"), InvalidCreditAmountError)

		account_doc = AccountService.get_or_create_account(
			owner_doctype, owner_name, credit_type
		)
		account = AccountService.lock_account(account_doc.name)

		if idempotency_key:
			existing = LedgerService.find_by_idempotency_key(idempotency_key, entry_type="GRANT")
			if existing and existing.credit_account == account.name:
				return LedgerService.build_result_from_entry(existing, account, idempotent_replay=True)

		amount = AccountService.round_amount(amount, account.credit_type)
		new_balance = flt(account.current_balance) + amount

		account = AccountService.update_balances(
			account,
			current_balance=new_balance,
			lifetime_granted_delta=amount,
		)

		entry = LedgerService.create_and_submit_entry(
			account,
			"GRANT",
			amount,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			source_app=source_app,
			idempotency_key=idempotency_key,
			metadata=metadata,
		)

		return LedgerService.build_result_from_entry(entry, account)