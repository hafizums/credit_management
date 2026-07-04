# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document

MUTABLE_FIELDS = frozenset(
	{
		"status",
		"retry_count",
		"last_error",
		"next_retry_at",
		"delivered_at",
	}
)


class CreditWebhookEvent(Document):
	def validate(self):
		previous = self.get_doc_before_save()
		if previous and not self.is_new():
			for fieldname in self.meta.get_valid_columns():
				if fieldname in ("modified", "modified_by"):
					continue
				if self.get(fieldname) != previous.get(fieldname) and fieldname not in MUTABLE_FIELDS:
					frappe.throw(
						_("Credit Webhook Event audit fields cannot be modified after creation"),
						frappe.ValidationError,
					)

	def on_trash(self):
		frappe.throw(
			_("Credit Webhook Event records cannot be deleted"),
			frappe.ValidationError,
		)