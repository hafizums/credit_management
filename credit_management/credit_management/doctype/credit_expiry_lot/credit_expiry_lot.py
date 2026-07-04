# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CreditExpiryLot(Document):
	def validate(self):
		if flt(self.original_amount) <= 0:
			frappe.throw(_("Original amount must be positive"), frappe.ValidationError)