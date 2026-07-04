# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

BALANCE_FIELDS = (
	"current_balance",
	"reserved_balance",
	"available_balance",
	"lifetime_granted",
	"lifetime_consumed",
	"lifetime_expired",
)


class CreditAccount(Document):
	def autoname(self):
		from credit_management.services.account_service import AccountService

		self.name = AccountService.make_account_name(
			self.account_owner_doctype,
			self.account_owner_name,
			self.credit_type,
			self.company,
		)

	def validate(self):
		self._validate_available_balance()
		self._prevent_direct_balance_mutation()

	def _validate_available_balance(self):
		expected = flt(self.current_balance) - flt(self.reserved_balance)
		if flt(self.available_balance) != flt(expected):
			self.available_balance = expected

	def _prevent_direct_balance_mutation(self):
		if self.is_new() or getattr(frappe.flags, "allow_credit_balance_update", False):
			return

		previous = self.get_doc_before_save()
		if not previous:
			return

		for field in BALANCE_FIELDS:
			if flt(self.get(field)) != flt(previous.get(field)):
				frappe.throw(
					_("Credit Account balances can only be updated through credit_management.api"),
					frappe.ValidationError,
				)