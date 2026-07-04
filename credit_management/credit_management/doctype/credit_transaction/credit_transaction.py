# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from credit_management.credit_management.utils.credit import (
	get_signed_amount,
	reverse_account_balance,
	update_account_balance,
)


class CreditTransaction(Document):
	def validate(self):
		self.validate_amount()
		self.validate_account_status()
		self.validate_available_credit()

	def before_submit(self):
		self.status = "Submitted"

	def on_submit(self):
		signed_amount = get_signed_amount(self.transaction_type, self.amount)
		update_account_balance(self.credit_account, signed_amount)

	def before_cancel(self):
		self.status = "Cancelled"

	def on_cancel(self):
		signed_amount = get_signed_amount(self.transaction_type, self.amount)
		reverse_account_balance(self.credit_account, signed_amount)

	def validate_amount(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero"))

	def validate_account_status(self):
		account_status = frappe.db.get_value("Credit Account", self.credit_account, "status")
		if account_status != "Active":
			frappe.throw(_("Credit Account {0} is not active").format(self.credit_account))

	def validate_available_credit(self):
		if self.transaction_type not in ("Disbursement", "Interest Charge", "Adjustment (Increase)"):
			return

		account = frappe.get_doc("Credit Account", self.credit_account)
		projected_balance = flt(account.outstanding_balance) + flt(self.amount)

		if projected_balance > flt(account.credit_limit):
			settings = frappe.get_single("Credit Management Settings")
			if settings.block_transactions_on_limit_exceeded:
				frappe.throw(
					_(
						"This transaction would exceed the credit limit of {0} for account {1}"
					).format(account.credit_limit, self.credit_account)
				)