# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class CreditReconciliationRun(Document):
	def validate(self):
		previous = self.get_doc_before_save()
		if previous and not self.is_new():
			frappe.throw(
				_("Credit Reconciliation Run records are read-only after creation"),
				frappe.ValidationError,
			)