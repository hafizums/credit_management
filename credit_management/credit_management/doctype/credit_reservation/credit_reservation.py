# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CreditReservation(Document):
	def validate(self):
		if flt(self.reserved_amount) <= 0:
			frappe.throw(_("Reserved amount must be positive"), frappe.ValidationError)

		total = flt(self.consumed_amount) + flt(self.released_amount)
		if total > flt(self.reserved_amount):
			frappe.throw(
				_("Consumed and released amounts cannot exceed reserved amount"),
				frappe.ValidationError,
			)