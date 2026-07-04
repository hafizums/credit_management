# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CreditLedgerEntry(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Ledger entry amount must be positive"), frappe.ValidationError)

		previous = self.get_doc_before_save()
		if previous and previous.docstatus == 1:
			frappe.throw(
				_("Submitted Credit Ledger Entries cannot be modified"),
				frappe.ValidationError,
			)

	def before_update_after_submit(self):
		frappe.throw(
			_("Credit Ledger Entries are append-only and cannot be amended"),
			frappe.ValidationError,
		)

	def on_cancel(self):
		frappe.throw(
			_("Credit Ledger Entries cannot be cancelled; create a REVERSAL entry instead"),
			frappe.ValidationError,
		)