# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class CreditManagementSettings(Document):
	def on_update(self):
		frappe.clear_cache()