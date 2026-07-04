# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CreditAccount(Document):
	def validate(self):
		self.update_available_credit()
		self.validate_credit_limit()

	def update_available_credit(self):
		self.available_credit = max(flt(self.credit_limit) - flt(self.outstanding_balance), 0)

	def validate_credit_limit(self):
		if flt(self.outstanding_balance) > flt(self.credit_limit):
			settings = frappe.get_single("Credit Management Settings")
			if settings.block_transactions_on_limit_exceeded:
				frappe.throw(
					_("Outstanding balance cannot exceed the credit limit for account {0}").format(
						self.name
					)
				)