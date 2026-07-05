# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Operations-safe cleanup for old Credit Integration Log rows."""

import frappe
from frappe.utils import add_to_date, cint, now_datetime


class IntegrationLogCleanupService:
	@staticmethod
	def cleanup_old_integration_logs(dry_run=True, retention_days=None):
		settings = frappe.get_single("Credit Settings")
		retention_days = cint(retention_days or settings.audit_log_retention_days or 365)
		cutoff = add_to_date(now_datetime(), days=-retention_days, as_datetime=True)

		eligible_names = frappe.get_all(
			"Credit Integration Log",
			filters={"creation": ["<", cutoff]},
			pluck="name",
			limit_page_length=0,
		)
		eligible = len(eligible_names)
		deleted = 0

		if dry_run:
			return {
				"status": "completed",
				"retention_days": retention_days,
				"dry_run": True,
				"cutoff": cutoff,
				"eligible": eligible,
				"deleted": 0,
			}

		frappe.flags.allow_integration_log_cleanup = True
		try:
			batch_size = 500
			for index in range(0, len(eligible_names), batch_size):
				batch = eligible_names[index : index + batch_size]
				for name in batch:
					frappe.delete_doc("Credit Integration Log", name, force=1, ignore_permissions=True)
					deleted += 1
				frappe.db.commit()
		finally:
			frappe.flags.allow_integration_log_cleanup = False

		return {
			"status": "completed",
			"retention_days": retention_days,
			"dry_run": False,
			"cutoff": cutoff,
			"eligible": eligible,
			"deleted": deleted,
		}