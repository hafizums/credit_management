# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class CreditIntegrationLog(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(
				_("Credit Integration Log records are append-only and cannot be modified"),
				frappe.ValidationError,
			)

	def on_trash(self):
		frappe.throw(
			_("Credit Integration Log records cannot be deleted"),
			frappe.ValidationError,
		)