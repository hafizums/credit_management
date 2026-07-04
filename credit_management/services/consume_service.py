# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Direct credit consumption."""

import frappe
from frappe import _
from frappe.utils import flt

from credit_management.exceptions import InvalidCreditAmountError
from credit_management.services.account_service import AccountService
from credit_management.services.ledger_service import LedgerService


class ConsumeService:
	@staticmethod
	def consume_credits(
		owner_doctype,
		owner_name,
		credit_type,
		amount,
		reference_doctype=None,
		reference_name=None,
		idempotency_key=None,
		source_app=None,
		metadata=None,
		company=None,
	):
		amount = flt(amount)
		if amount <= 0:
			frappe.throw(_("Consume amount must be positive"), InvalidCreditAmountError)

		account_doc = AccountService.get_or_create_account(
			owner_doctype, owner_name, credit_type, company
		)
		account = AccountService.lock_account(account_doc.name)

		if idempotency_key:
			existing = LedgerService.find_by_idempotency_key(idempotency_key, entry_type="CONSUME")
			if existing and existing.credit_account == account.name:
				return LedgerService.build_result_from_entry(existing, account, idempotent_replay=True)

		AccountService.validate_account_can_consume(account)

		amount = AccountService.round_amount(amount, account.credit_type)
		AccountService.validate_sufficient_balance(account, amount)

		new_balance = flt(account.current_balance) - amount

		account = AccountService.update_balances(
			account,
			current_balance=new_balance,
			lifetime_consumed_delta=amount,
		)

		entry = LedgerService.create_and_submit_entry(
			account,
			"CONSUME",
			amount,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			source_app=source_app,
			idempotency_key=idempotency_key,
			metadata=metadata,
		)

		return LedgerService.build_result_from_entry(entry, account)