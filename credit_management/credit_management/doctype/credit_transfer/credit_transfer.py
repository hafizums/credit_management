# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from credit_management.exceptions import InvalidCreditTransferError


class CreditTransfer(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Transfer amount must be positive"), InvalidCreditTransferError)

		if self.from_credit_account == self.to_credit_account:
			frappe.throw(
				_("Source and target credit accounts must be different"),
				InvalidCreditTransferError,
			)