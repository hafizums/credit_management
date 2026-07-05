# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Milestone 16 security-focused regression tests."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

import credit_management.api as api
import credit_management.rest_api as rest_api
from credit_management.install import seed_defaults
from credit_management.report_utils import enforce_report_access
from credit_management.services.integration_log_service import IntegrationLogService
from credit_management.services.webhook_service import WebhookService


class TestM16SecurityReview(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_defaults()
		cls._suffix = frappe.generate_hash(length=8)
		cls.credit_user = cls._ensure_user(
			f"m16-user-{cls._suffix}@example.com", ["Credit User"]
		)
		cls.credit_manager = cls._ensure_user(
			f"m16-manager-{cls._suffix}@example.com", ["Credit Manager"]
		)
		cls.credit_auditor = cls._ensure_user(
			f"m16-auditor-{cls._suffix}@example.com", ["Credit Auditor"]
		)
		cls.credit_developer = cls._ensure_user(
			f"m16-developer-{cls._suffix}@example.com", ["Credit Developer"]
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
			idempotency_key=key or f"m16-grant-{owner}-{self._suffix}",
			metadata=metadata,
		)
		return api.get_or_create_account(self.owner_doctype, owner, self.credit_type)

	def test_01_rest_disabled_blocks_all_endpoints(self):
		self._set_settings(enable_rest_api=0)
		owner = self._owner("rest-blocked")
		account = self._grant_account(owner, amount=20)
		frappe.set_user(self.credit_manager)

		endpoints = (
			("get_balance", {"owner_doctype": self.owner_doctype, "owner_name": owner, "credit_type": self.credit_type}),
			("grant_credits", {"owner_doctype": self.owner_doctype, "owner_name": owner, "credit_type": self.credit_type, "amount": 1}),
			("consume_credits", {"owner_doctype": self.owner_doctype, "owner_name": owner, "credit_type": self.credit_type, "amount": 1}),
			("reconcile_account", {"credit_account": account}),
			("reconcile_all_accounts", {}),
			("expire_credits", {}),
		)
		for method_name, kwargs in endpoints:
			with self.subTest(method=method_name):
				with self.assertRaises(frappe.PermissionError):
					getattr(rest_api, method_name)(**kwargs)

	def test_02_credit_user_cannot_call_rest_mutation(self):
		self._set_settings(enable_rest_api=1)
		frappe.set_user(self.credit_user)
		with self.assertRaises(frappe.PermissionError):
			rest_api.grant_credits(
				self.owner_doctype,
				self.credit_user,
				self.credit_type,
				5,
			)

	def test_03_credit_user_cannot_get_another_users_balance(self):
		self._set_settings(enable_rest_api=1)
		other_owner = self._owner("rest-other-balance")
		self._grant_account(other_owner, amount=15)
		frappe.set_user(self.credit_user)
		with self.assertRaises(frappe.PermissionError):
			rest_api.get_balance("User", other_owner, self.credit_type)

	def test_04_credit_auditor_cannot_call_rest_mutation(self):
		self._set_settings(enable_rest_api=1)
		frappe.set_user(self.credit_auditor)
		with self.assertRaises(frappe.PermissionError):
			rest_api.consume_credits(
				self.owner_doctype,
				self._owner("auditor-mut"),
				self.credit_type,
				1,
			)

	def test_05_credit_developer_cannot_call_rest_mutation(self):
		self._set_settings(enable_rest_api=1)
		frappe.set_user(self.credit_developer)
		with self.assertRaises(frappe.PermissionError):
			rest_api.reserve_credits(
				self.owner_doctype,
				self._owner("developer-mut"),
				self.credit_type,
				1,
			)

	def test_06_credit_manager_can_call_mutation_only_when_rest_enabled(self):
		owner = self._owner("rest-manager-toggle")
		self._set_settings(enable_rest_api=0)
		frappe.set_user(self.credit_manager)
		with self.assertRaises(frappe.PermissionError):
			rest_api.grant_credits(
				self.owner_doctype,
				owner,
				self.credit_type,
				3,
			)

		self._set_settings(enable_rest_api=1)
		result = rest_api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			7,
			idempotency_key=f"m16-rest-manager-{self._suffix}",
		)
		self.assertEqual(result["amount"], 7)

	def test_07_integration_log_redacts_nested_sensitive_keys(self):
		owner = self._owner("log-nested-redact")
		nested_metadata = {
			"outer": {"API_KEY": "top-secret", "note": "ok"},
			"credentials": [{"Access_Token": "nested-token", "label": "visible"}],
		}
		self._grant_account(
			owner,
			amount=10,
			metadata=nested_metadata,
			key=f"m16-nested-redact-{self._suffix}",
		)
		logs = frappe.get_all(
			"Credit Integration Log",
			filters={"operation": "grant_credits"},
			fields=["request_json"],
			order_by="creation desc",
			limit=1,
		)
		self.assertTrue(logs)
		request = json.loads(logs[0]["request_json"])
		self.assertEqual(request["metadata"]["outer"]["API_KEY"], "[REDACTED]")
		self.assertEqual(request["metadata"]["outer"]["note"], "ok")
		self.assertEqual(request["metadata"]["credentials"][0]["Access_Token"], "[REDACTED]")
		self.assertEqual(request["metadata"]["credentials"][0]["label"], "visible")

	def test_08_webhook_payload_redacts_nested_sensitive_keys(self):
		serialized = WebhookService._serialize_payload(
			{
				"metadata": {"nested": {"Webhook_Secret": "wh-secret", "safe": "yes"}},
				"credentials": [{"Refresh_Token": "nested-token"}],
			}
		)
		payload = json.loads(serialized)
		self.assertNotIn("wh-secret", serialized)
		self.assertNotIn("nested-token", serialized)
		self.assertEqual(payload["metadata"]["nested"]["Webhook_Secret"], "[REDACTED]")
		self.assertEqual(payload["metadata"]["nested"]["safe"], "yes")
		self.assertEqual(payload["credentials"][0]["Refresh_Token"], "[REDACTED]")

	def test_09_credit_user_cannot_read_integration_logs(self):
		owner = self._owner("log-access")
		self._grant_account(owner, amount=5, key=f"m16-log-access-{self._suffix}")
		log_name = frappe.get_all(
			"Credit Integration Log",
			filters={"operation": "grant_credits"},
			pluck="name",
			order_by="creation desc",
			limit=1,
		)[0]
		frappe.set_user(self.credit_user)
		self.assertFalse(frappe.has_permission("Credit Integration Log", doc=log_name))
		self.assertFalse(frappe.has_permission("Credit Integration Log", ptype="read"))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Credit Integration Log", pluck="name")

	def test_10_credit_user_cannot_read_webhook_events(self):
		self._set_settings(enable_webhooks=1)
		owner = self._owner("wh-access")
		self._grant_account(owner, amount=6, key=f"m16-wh-access-{self._suffix}")
		event_name = frappe.get_all(
			"Credit Webhook Event",
			pluck="name",
			order_by="creation desc",
			limit=1,
		)[0]
		frappe.set_user(self.credit_user)
		self.assertFalse(frappe.has_permission("Credit Webhook Event", doc=event_name))
		self.assertFalse(frappe.has_permission("Credit Webhook Event", ptype="read"))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Credit Webhook Event", pluck="name")

	def test_11_credit_user_report_access_is_own_only_or_blocked(self):
		self._grant_account(self.credit_user, key=f"m16-own-report-{self._suffix}")
		other = self._owner("other-report")
		self._grant_account(other, key=f"m16-other-report-{self._suffix}")

		frappe.set_user(self.credit_user)
		enforce_report_access("Credit Balance Report")
		enforce_report_access("Credit Ledger Report")
		with self.assertRaises(frappe.PermissionError):
			enforce_report_access("Credit Usage by App")
		with self.assertRaises(frappe.PermissionError):
			enforce_report_access("Reconciliation Report")

		module = frappe.get_module(
			"credit_management.credit_management.report.credit_balance_report.credit_balance_report"
		)
		_, data = module.execute({})
		owners = {row.get("account_owner_name") for row in data}
		self.assertIn(self.credit_user, owners)
		self.assertNotIn(other, owners)

	def test_12_ledger_entry_cannot_be_edited_after_submit(self):
		owner = self.credit_user
		self._grant_account(owner, key=f"m16-ledger-edit-{self._suffix}")
		result = api.consume_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			2,
			idempotency_key=f"m16-ledger-edit-consume-{self._suffix}",
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		frappe.set_user(self.credit_manager)
		entry.amount = 999
		with self.assertRaises((frappe.PermissionError, frappe.ValidationError)):
			entry.save()

	def test_13_credit_account_cached_balance_cannot_be_edited_from_desk(self):
		owner = self.credit_user
		account_name = self._grant_account(owner, key=f"m16-account-edit-{self._suffix}")
		frappe.set_user(self.credit_user)
		account = frappe.get_doc("Credit Account", account_name)
		self.assertFalse(frappe.has_permission("Credit Account", ptype="write", doc=account))
		account.current_balance = 999
		with self.assertRaises(frappe.PermissionError):
			account.save()

	def test_14_sanitize_helpers_cover_mixed_case_keys(self):
		payload = {
			"Authorization": "Bearer abc",
			"nested": {"Client_Secret": "cs", "plain": "visible"},
		}
		sanitized = IntegrationLogService.sanitize_payload(payload)
		self.assertEqual(sanitized["Authorization"], "[REDACTED]")
		self.assertEqual(sanitized["nested"]["Client_Secret"], "[REDACTED]")
		self.assertEqual(sanitized["nested"]["plain"], "visible")
		self.assertEqual(
			WebhookService.sanitize_payload(payload)["nested"]["Client_Secret"],
			"[REDACTED]",
		)