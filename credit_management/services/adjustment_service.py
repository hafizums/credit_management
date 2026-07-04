# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Administrative credit adjustments."""

import frappe
from frappe import _
from frappe.utils import flt

from credit_management.exceptions import CreditManagementError, InvalidCreditAmountError
from credit_management.services.account_service import AccountService
from credit_management.services.expiry_service import ExpiryService
from credit_management.services.ledger_service import LedgerService


class AdjustmentService:
	@staticmethod
	def adjust_credits(
		owner_doctype,
		owner_name,
		credit_type,
		amount,
		reason,
		idempotency_key=None,
		company=None,
	):
		amount = flt(amount)
		if amount == 0:
			frappe.throw(_("Adjustment amount must be non-zero"), InvalidCreditAmountError)

		if not reason or not str(reason).strip():
			frappe.throw(_("Adjustment reason is required"), CreditManagementError)

		account_doc = AccountService.get_or_create_account(
			owner_doctype, owner_name, credit_type, company
		)
		account = AccountService.lock_account(account_doc.name)

		entry_type = "ADJUST_IN" if amount > 0 else "ADJUST_OUT"
		ledger_amount = abs(amount)

		if idempotency_key:
			existing = LedgerService.find_by_idempotency_key(idempotency_key, entry_type=entry_type)
			if existing and existing.credit_account == account.name:
				return LedgerService.build_result_from_entry(existing, account, idempotent_replay=True)

		ledger_amount = AccountService.round_amount(ledger_amount, account.credit_type)

		if amount > 0:
			new_balance = flt(account.current_balance) + ledger_amount
			account = AccountService.update_balances(account, current_balance=new_balance)
		else:
			AccountService.validate_sufficient_balance(account, ledger_amount)
			if ExpiryService.get_active_lots(account.name, account.credit_type):
				ExpiryService.consume_from_expiry_lots(account, ledger_amount)
			new_balance = flt(account.current_balance) - ledger_amount
			account = AccountService.update_balances(account, current_balance=new_balance)

		entry = LedgerService.create_and_submit_entry(
			account,
			entry_type,
			ledger_amount,
			idempotency_key=idempotency_key,
			remarks=reason,
		)

		return LedgerService.build_result_from_entry(entry, account)