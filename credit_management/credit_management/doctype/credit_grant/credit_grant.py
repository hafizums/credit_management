# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CreditGrant(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Grant amount must be positive"), frappe.ValidationError)