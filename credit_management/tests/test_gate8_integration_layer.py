# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import json
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

import credit_management.api as api
import credit_management.rest_api as rest_api
from credit_management import tasks
from credit_management.exceptions import InsufficientCreditError
from credit_management.install import seed_defaults
from credit_management.services.integration_log_service import IntegrationLogService
from credit_management.services.webhook_service import WebhookService


class TestGate8IntegrationLayer(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_defaults()
		cls._suffix = frappe.generate_hash(length=8)
		cls.credit_user = cls._ensure_user(
			f"gate8-user-{cls._suffix}@example.com", ["Credit User"]
		)
		cls.credit_manager = cls._ensure_user(
			f"gate8-manager-{cls._suffix}@example.com", ["Credit Manager"]
		)
		cls.credit_auditor = cls._ensure_user(
			f"gate8-auditor-{cls._suffix}@example.com", ["Credit Auditor"]
		)

	def setUp(self):
		self.owner_doctype = "User"
		self.credit_type = "GENERAL"
		self._suffix = self.__class__._suffix
		self._reset_settings()

	def tearDown(self):
		frappe.set_user("Administrator")
		self._reset_settings()

	@classmethod
	def _ensure_user(cls, email, roles):
		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
			existing_roles = {row.role for row in user.roles}
			for role in roles:
				if role not in existing_roles:
					user.append("roles", {"role": role})
			user.save(ignore_permissions=True)
		else:
			frappe.flags.in_import = True
			try:
				frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": email.split("@")[0],
						"send_welcome_email": 0,
						"roles": [{"role": role} for role in roles],
					}
				).insert(ignore_permissions=True)
			finally:
				frappe.flags.in_import = False
		frappe.clear_cache(user=email)
		return email

	def _owner(self, label):
		return f"{label}-{self._suffix}"

	def _reset_settings(self):
		settings = frappe.get_single("Credit Settings")
		settings.enable_rest_api = 0
		settings.enable_webhooks = 0
		settings.enable_integration_logs = 1
		settings.webhook_target_url = ""
		settings.webhook_max_retries = 5
		settings.webhook_retry_interval_minutes = 30
		settings.low_balance_threshold_default = 0
		settings.save(ignore_permissions=True)

	def _set_settings(self, **kwargs):
		settings = frappe.get_single("Credit Settings")
		for key, value in kwargs.items():
			setattr(settings, key, value)
		settings.save(ignore_permissions=True)

	def _grant_account(self, owner, amount=50, key=None, metadata=None):
		api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			amount,
			idempotency_key=key or f"gate8-grant-{owner}-{self._suffix}",
			metadata=metadata,
		)
		return api.get_or_create_account(self.owner_doctype, owner, self.credit_type)

	def _latest_integration_log(self, operation):
		return frappe.get_all(
			"Credit Integration Log",
			filters={"operation": operation},
			fields=["name", "status", "request_json", "response_json", "error_message"],
			order_by="creation desc",
			limit=1,
		)

	def _latest_webhook_event(self, event_type):
		return frappe.get_all(
			"Credit Webhook Event",
			filters={"event_type": event_type},
			fields=["name", "status", "payload_json", "retry_count", "max_retries", "last_error"],
			order_by="creation desc",
			limit=1,
		)

	def test_01_credit_integration_log_doctype_exists(self):
		self.assertTrue(frappe.db.exists("DocType", "Credit Integration Log"))

	def test_02_credit_webhook_event_doctype_exists(self):
		self.assertTrue(frappe.db.exists("DocType", "Credit Webhook Event"))

	def test_03_integration_log_records_successful_grant(self):
		owner = self._owner("log-grant")
		self._grant_account(owner, amount=15)
		logs = self._latest_integration_log("grant_credits")
		self.assertTrue(logs)
		self.assertIn(logs[0]["status"], ("Success", "Replayed"))

	def test_04_integration_log_records_failed_consume(self):
		owner = self._owner("log-fail-consume")
		with self.assertRaises(InsufficientCreditError):
			api.consume_credits(
				self.owner_doctype,
				owner,
				self.credit_type,
				10,
				idempotency_key=f"gate8-fail-consume-{self._suffix}",
			)
		logs = self._latest_integration_log("consume_credits")
		self.assertTrue(logs)
		self.assertEqual(logs[0]["status"], "Failed")

	def test_05_integration_log_redacts_sensitive_fields(self):
		owner = self._owner("log-redact")
		self._grant_account(
			owner,
			amount=10,
			metadata={"api_key": "secret-value", "note": "visible"},
		)
		logs = self._latest_integration_log("grant_credits")
		self.assertTrue(logs)
		request = json.loads(logs[0]["request_json"])
		self.assertEqual(request["metadata"]["api_key"], "[REDACTED]")
		self.assertEqual(request["metadata"]["note"], "visible")

	def test_06_integration_logging_can_be_disabled(self):
		self._set_settings(enable_integration_logs=0)
		before = frappe.db.count("Credit Integration Log")
		owner = self._owner("log-disabled")
		self._grant_account(owner, amount=5, key=f"gate8-disabled-{self._suffix}")
		after = frappe.db.count("Credit Integration Log")
		self.assertEqual(before, after)

	def test_07_webhook_event_created_when_webhooks_enabled(self):
		self._set_settings(enable_webhooks=1)
		owner = self._owner("wh-enabled")
		self._grant_account(owner, amount=12, key=f"gate8-wh-enabled-{self._suffix}")
		events = self._latest_webhook_event("credit.granted")
		self.assertTrue(events)
		self.assertEqual(events[0]["status"], "Pending")

	def test_08_no_webhook_event_when_webhooks_disabled(self):
		self._set_settings(enable_webhooks=0)
		before = frappe.db.count("Credit Webhook Event")
		owner = self._owner("wh-disabled")
		self._grant_account(owner, amount=8, key=f"gate8-wh-disabled-{self._suffix}")
		after = frappe.db.count("Credit Webhook Event")
		self.assertEqual(before, after)

	def test_09_webhook_payload_is_sanitized(self):
		self._set_settings(enable_webhooks=1)
		owner = self._owner("wh-sanitize")
		self._grant_account(
			owner,
			amount=9,
			key=f"gate8-wh-sanitize-{self._suffix}",
			metadata={"token": "hidden-token"},
		)
		events = self._latest_webhook_event("credit.granted")
		self.assertTrue(events)
		payload = json.loads(events[0]["payload_json"])
		self.assertNotIn("hidden-token", json.dumps(payload))

	def test_10_retry_failed_webhooks_is_not_stub(self):
		result = tasks.retry_failed_webhooks()
		self.assertEqual(result["status"], "completed")
		self.assertIn("attempted", result)

	def test_11_retry_failed_webhooks_skips_delivered_events(self):
		event = frappe.get_doc(
			{
				"doctype": "Credit Webhook Event",
				"event_type": "credit.granted",
				"status": "Delivered",
				"payload_json": "{}",
				"max_retries": 5,
			}
		).insert(ignore_permissions=True)
		result = tasks.retry_failed_webhooks()
		self.assertGreaterEqual(result["skipped"], 0)
		reloaded = frappe.get_doc("Credit Webhook Event", event.name)
		self.assertEqual(reloaded.status, "Delivered")

	def test_12_retry_failed_webhooks_honors_max_retries(self):
		event = frappe.get_doc(
			{
				"doctype": "Credit Webhook Event",
				"event_type": "credit.consumed",
				"status": "Failed",
				"payload_json": "{}",
				"retry_count": 5,
				"max_retries": 5,
			}
		).insert(ignore_permissions=True)
		result = tasks.retry_failed_webhooks()
		self.assertGreaterEqual(result["skipped"], 1)
		reloaded = frappe.get_doc("Credit Webhook Event", event.name)
		self.assertEqual(reloaded.retry_count, 5)

	def test_13_retry_failed_webhooks_records_failure_when_target_url_missing(self):
		self._set_settings(enable_webhooks=1, webhook_target_url="")
		event = frappe.get_doc(
			{
				"doctype": "Credit Webhook Event",
				"event_type": "credit.refunded",
				"status": "Pending",
				"payload_json": "{}",
				"max_retries": 5,
				"retry_count": 0,
			}
		).insert(ignore_permissions=True)
		result = tasks.retry_failed_webhooks()
		self.assertGreaterEqual(result["failed"], 1)
		reloaded = frappe.get_doc("Credit Webhook Event", event.name)
		self.assertEqual(reloaded.status, "Failed")
		self.assertIn("No webhook target URL configured", reloaded.last_error or "")

	def test_14_generate_daily_credit_summary_is_not_stub(self):
		result = tasks.generate_daily_credit_summary()
		self.assertEqual(result["status"], "completed")

	def test_15_generate_daily_credit_summary_returns_expected_keys(self):
		result = tasks.generate_daily_credit_summary()
		for key in (
			"status",
			"date",
			"total_accounts",
			"active_reservations",
			"consumed_today",
			"granted_today",
			"expired_today",
			"reserved_today",
			"released_today",
			"transfer_in_today",
			"transfer_out_today",
		):
			self.assertIn(key, result)

	def test_16_rest_disabled_blocks_whitelisted_endpoints(self):
		self._set_settings(enable_rest_api=0)
		frappe.set_user(self.credit_manager)
		with self.assertRaises(frappe.PermissionError):
			rest_api.grant_credits(
				self.owner_doctype,
				self._owner("rest-disabled"),
				self.credit_type,
				10,
			)

	def test_17_rest_enabled_allows_credit_manager_mutation_endpoint(self):
		self._set_settings(enable_rest_api=1)
		frappe.set_user(self.credit_manager)
		result = rest_api.grant_credits(
			self.owner_doctype,
			self._owner("rest-manager"),
			self.credit_type,
			11,
			idempotency_key=f"gate8-rest-manager-{self._suffix}",
		)
		self.assertEqual(result["amount"], 11)

	def test_18_rest_enabled_blocks_credit_user_mutation_endpoint(self):
		self._set_settings(enable_rest_api=1)
		frappe.set_user(self.credit_user)
		with self.assertRaises(frappe.PermissionError):
			rest_api.grant_credits(
				self.owner_doctype,
				self.credit_user,
				self.credit_type,
				5,
			)

	def test_19_rest_get_balance_allows_credit_user_own_user_account(self):
		self._set_settings(enable_rest_api=1)
		api.grant_credits(
			"User",
			self.credit_user,
			self.credit_type,
			20,
			idempotency_key=f"gate8-rest-own-grant-{self._suffix}",
		)
		frappe.set_user(self.credit_user)
		result = rest_api.get_balance("User", self.credit_user, self.credit_type)
		self.assertEqual(result["current_balance"], 20)

	def test_20_rest_get_balance_blocks_credit_user_from_other_account(self):
		self._set_settings(enable_rest_api=1)
		other_owner = self._owner("rest-other")
		self._grant_account(other_owner, amount=15)
		frappe.set_user(self.credit_user)
		with self.assertRaises(frappe.PermissionError):
			rest_api.get_balance("User", other_owner, self.credit_type)

	def test_21_credit_auditor_can_call_reconciliation_rest_endpoint_if_enabled(self):
		self._set_settings(enable_rest_api=1)
		owner = self._owner("rest-auditor")
		account = self._grant_account(owner, amount=10)
		frappe.set_user(self.credit_auditor)
		result = rest_api.reconcile_account(account)
		self.assertEqual(result["status"], "completed")

	def test_22_credit_auditor_cannot_call_mutation_rest_endpoint(self):
		self._set_settings(enable_rest_api=1)
		frappe.set_user(self.credit_auditor)
		with self.assertRaises(frappe.PermissionError):
			rest_api.consume_credits(
				self.owner_doctype,
				self._owner("rest-auditor-mut"),
				self.credit_type,
				1,
			)

	def test_23_webhook_event_created_for_credit_granted(self):
		self._set_settings(enable_webhooks=1)
		owner = self._owner("evt-granted")
		self._grant_account(owner, amount=7, key=f"gate8-evt-granted-{self._suffix}")
		self.assertTrue(self._latest_webhook_event("credit.granted"))

	def test_24_webhook_event_created_for_credit_consumed(self):
		self._set_settings(enable_webhooks=1)
		owner = self._owner("evt-consumed")
		self._grant_account(owner, amount=20, key=f"gate8-evt-consumed-grant-{self._suffix}")
		api.consume_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			3,
			idempotency_key=f"gate8-evt-consumed-{self._suffix}",
		)
		self.assertTrue(self._latest_webhook_event("credit.consumed"))

	def test_25_webhook_event_created_for_credit_reserved(self):
		self._set_settings(enable_webhooks=1)
		owner = self._owner("evt-reserved")
		self._grant_account(owner, amount=20, key=f"gate8-evt-reserved-grant-{self._suffix}")
		api.reserve_credits(
			owner_doctype=self.owner_doctype,
			owner_name=owner,
			credit_type=self.credit_type,
			amount=4,
			idempotency_key=f"gate8-evt-reserved-{self._suffix}",
		)
		self.assertTrue(self._latest_webhook_event("credit.reserved"))

	def test_26_webhook_event_created_for_credit_transferred(self):
		self._set_settings(enable_webhooks=1)
		from_owner = self._owner("evt-transfer-from")
		to_owner = self._owner("evt-transfer-to")
		from_account = self._grant_account(from_owner, amount=30, key=f"gate8-evt-transfer-from-{self._suffix}")
		to_account = api.get_or_create_account(self.owner_doctype, to_owner, self.credit_type)
		api.transfer_credits(
			from_account,
			to_account,
			self.credit_type,
			5,
			idempotency_key=f"gate8-evt-transfer-{self._suffix}",
		)
		self.assertTrue(self._latest_webhook_event("credit.transferred"))

	def test_27_webhook_event_created_for_credit_expired(self):
		self._set_settings(enable_webhooks=1, enable_credit_expiry=1)
		owner = self._owner("evt-expired")
		self._grant_account(owner, amount=10, key=f"gate8-evt-expired-grant-{self._suffix}")
		api.expire_credits()
		self.assertTrue(self._latest_webhook_event("credit.expired"))

	def test_28_gate2_tests_still_pass(self):
		from credit_management.tests.test_gate2_core_ledger import TestGate2CoreLedger

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate2CoreLedger)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())

	def test_29_gate3_tests_still_pass(self):
		from credit_management.tests.test_gate3_reservations import TestGate3Reservations

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate3Reservations)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())

	def test_30_gate4_tests_still_pass(self):
		from credit_management.tests.test_gate4_expiry_lots import TestGate4ExpiryLots

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate4ExpiryLots)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())

	def test_31_gate5_tests_still_pass(self):
		from credit_management.tests.test_gate5_transfers_adjustments import (
			TestGate5TransfersAdjustments,
		)

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate5TransfersAdjustments)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())

	def test_32_gate6_tests_still_pass(self):
		from credit_management.tests.test_gate6_permissions_workspace import (
			TestGate6PermissionsWorkspace,
		)

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate6PermissionsWorkspace)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())

	def test_33_gate7_tests_still_pass(self):
		from credit_management.tests.test_gate7_reports_reconciliation import (
			TestGate7ReportsReconciliation,
		)

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate7ReportsReconciliation)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())