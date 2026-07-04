# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Credit grant and top-up operations."""

import frappe
from frappe import _
from frappe.utils import flt

from credit_management.exceptions import InvalidCreditAmountError
from credit_management.services.account_service import AccountService
from credit_management.services.expiry_service import ExpiryService
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
		amount = flt(amount)
		if amount <= 0:
			frappe.throw(_("Grant amount must be positive"), InvalidCreditAmountError)

		account_doc = AccountService.get_or_create_account(
			owner_doctype, owner_name, credit_type
		)
		account = AccountService.lock_account(account_doc.name)

		if idempotency_key:
			existing_grant = ExpiryService.find_grant_by_idempotency_key(idempotency_key)
			if existing_grant and existing_grant.credit_account == account.name:
				ledger_entry = frappe.get_doc("Credit Ledger Entry", existing_grant.ledger_entry)
				result = LedgerService.build_result_from_entry(
					ledger_entry, account, idempotent_replay=True
				)
				result["credit_grant"] = existing_grant.name
				return result

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

		result = LedgerService.build_result_from_entry(entry, account)

		expires_on_date = ExpiryService.normalize_expires_on(expires_on)
		if expires_on_date and ExpiryService.is_expiry_enabled():
			grant = ExpiryService.create_credit_grant(
				account,
				amount,
				entry,
				expires_on=expires_on_date,
				reference_doctype=reference_doctype,
				reference_name=reference_name,
				idempotency_key=idempotency_key,
				source_app=source_app,
				metadata=metadata,
			)
			lot = ExpiryService.create_expiry_lot_for_grant(
				grant, account, amount, expires_on_date
			)
			result["credit_grant"] = grant.name
			result["expiry_lot"] = lot.name

		return result