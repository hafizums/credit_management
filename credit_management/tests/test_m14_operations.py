# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from credit_management.services.integration_log_cleanup_service import IntegrationLogCleanupService
from credit_management.services.integration_log_service import IntegrationLogService


class TestM14Operations(FrappeTestCase):
	def test_cleanup_old_integration_logs_dry_run(self):
		settings = self._settings()
		settings.audit_log_retention_days = 90
		settings.save(ignore_permissions=True)

		old_name = IntegrationLogService.log_success(
			"grant_credits",
			request={"amount": 1},
			response={"amount": 1},
		)
		frappe.db.set_value(
			"Credit Integration Log",
			old_name,
			"creation",
			add_to_date(now_datetime(), days=-120),
		)
		frappe.db.commit()

		result = IntegrationLogCleanupService.cleanup_old_integration_logs(dry_run=True)
		self.assertTrue(result["dry_run"])
		self.assertGreaterEqual(result["eligible"], 1)
		self.assertEqual(result["deleted"], 0)
		self.assertTrue(frappe.db.exists("Credit Integration Log", old_name))

	def test_cleanup_old_integration_logs_deletes_when_not_dry_run(self):
		settings = self._settings()
		settings.audit_log_retention_days = 30
		settings.save(ignore_permissions=True)

		old_name = IntegrationLogService.log_success(
			"reserve_credits",
			request={"amount": 1},
			response={"reservation": "CR-test"},
		)
		frappe.db.set_value(
			"Credit Integration Log",
			old_name,
			"creation",
			add_to_date(now_datetime(), days=-60),
		)
		frappe.db.commit()

		result = IntegrationLogCleanupService.cleanup_old_integration_logs(dry_run=False)
		self.assertFalse(result["dry_run"])
		self.assertGreaterEqual(result["deleted"], 1)
		self.assertFalse(frappe.db.exists("Credit Integration Log", old_name))

	def _settings(self):
		return frappe.get_single("Credit Settings")