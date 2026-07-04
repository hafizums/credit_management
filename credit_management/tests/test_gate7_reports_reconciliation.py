# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

import credit_management.api as api
from credit_management import tasks
from credit_management.install import seed_defaults
from credit_management.services.ledger_service import LedgerService

STALE_MVP_DOCTYPES = {"Credit Transaction", "Credit Management Settings"}
REPORT_LINKS = {
	"Credit Balance Report",
	"Credit Ledger Report",
	"Credit Usage by App",
	"Credit Usage by Owner",
	"Reservation Aging Report",
	"Expired Credits Report",
	"Reconciliation Report",
	"Top Credit Consumers",
	"Credit Grant History",
	"Credit Transfer History",
}


class TestGate7ReportsReconciliation(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_defaults()
		cls._suffix = frappe.generate_hash(length=8)
		cls.credit_user = cls._ensure_user(
			f"gate7-user-{cls._suffix}@example.com", ["Credit User"]
		)

	def setUp(self):
		self.owner_doctype = "User"
		self.credit_type = "GENERAL"
		self._suffix = self.__class__._suffix
		self.credit_user = self.__class__.credit_user

	def tearDown(self):
		frappe.set_user("Administrator")

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

	def _grant_account(self, owner, amount=50, key=None):
		api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			amount,
			idempotency_key=key or f"gate7-grant-{owner}-{self._suffix}",
		)
		return api.get_or_create_account(self.owner_doctype, owner, self.credit_type)

	def _run_report(self, module_path):
		module = frappe.get_module(module_path)
		return module.execute({})

	def test_01_credit_reconciliation_run_doctype_exists(self):
		self.assertTrue(frappe.db.exists("DocType", "Credit Reconciliation Run"))

	def test_02_reconcile_account_passes_for_clean_account(self):
		owner = self._owner("clean")
		account = self._grant_account(owner)
		result = api.reconcile_account(account)
		self.assertEqual(result["summary_status"], "Passed")
		self.assertEqual(result["accounts"][0]["status"], "Passed")

	def test_03_reconcile_account_detects_current_balance_mismatch(self):
		owner = self._owner("current-mismatch")
		account = self._grant_account(owner)
		frappe.db.set_value("Credit Account", account, "current_balance", 999)
		result = api.reconcile_account(account)
		self.assertEqual(result["accounts"][0]["status"], "Mismatch")

	def test_04_reconcile_account_detects_reserved_balance_mismatch(self):
		owner = self._owner("reserved-mismatch")
		account = self._grant_account(owner)
		frappe.db.set_value("Credit Account", account, "reserved_balance", 12)
		frappe.db.set_value("Credit Account", account, "available_balance", 38)
		result = api.reconcile_account(account)
		self.assertEqual(result["accounts"][0]["status"], "Mismatch")

	def test_05_reconcile_account_detects_available_balance_mismatch(self):
		owner = self._owner("available-mismatch")
		account = self._grant_account(owner)
		frappe.db.set_value("Credit Account", account, "available_balance", 1)
		result = api.reconcile_account(account)
		self.assertEqual(result["accounts"][0]["status"], "Mismatch")

	def test_06_reconcile_account_detects_negative_expiry_lot_values(self):
		owner = self._owner("negative-lot")
		account = self._grant_account(owner)
		settings = frappe.get_single("Credit Settings")
		settings.enable_credit_expiry = 1
		settings.save(ignore_permissions=True)
		grant = api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			20,
			expires_on=add_days(today(), 30),
			idempotency_key=f"gate7-lot-{self._suffix}",
		)
		frappe.db.set_value("Credit Expiry Lot", grant["expiry_lot"], "remaining_amount", -5)
		result = api.reconcile_account(account)
		self.assertEqual(result["accounts"][0]["status"], "Mismatch")

	def test_07_reconcile_account_detects_lot_reserved_exceeds_remaining(self):
		owner = self._owner("lot-reserved")
		account = self._grant_account(owner)
		settings = frappe.get_single("Credit Settings")
		settings.enable_credit_expiry = 1
		settings.save(ignore_permissions=True)
		grant = api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			20,
			expires_on=add_days(today(), 30),
			idempotency_key=f"gate7-lot-res-{self._suffix}",
		)
		frappe.db.set_value("Credit Expiry Lot", grant["expiry_lot"], "reserved_amount", 25)
		result = api.reconcile_account(account)
		self.assertEqual(result["accounts"][0]["status"], "Mismatch")

	def test_08_reconcile_account_records_credit_reconciliation_run(self):
		owner = self._owner("run-record")
		account = self._grant_account(owner)
		before = frappe.db.count("Credit Reconciliation Run")
		result = api.reconcile_account(account)
		self.assertEqual(frappe.db.count("Credit Reconciliation Run"), before + 1)
		self.assertTrue(frappe.db.exists("Credit Reconciliation Run", result["reconciliation_run"]))

	def test_09_reconcile_all_accounts_processes_multiple_accounts(self):
		self._grant_account(self._owner("all-a"))
		self._grant_account(self._owner("all-b"))
		result = api.reconcile_all_accounts()
		self.assertGreaterEqual(result["checked_accounts"], 2)

	def test_10_reconcile_all_accounts_reports_mismatch_count(self):
		owner = self._owner("all-mismatch")
		account = self._grant_account(owner)
		frappe.db.set_value("Credit Account", account, "current_balance", 500)
		result = api.reconcile_all_accounts()
		self.assertGreaterEqual(result["mismatch_count"], 1)

	def test_11_reconcile_recent_accounts_task_is_not_stub(self):
		result = tasks.reconcile_recent_accounts()
		self.assertNotEqual(result.get("status"), "stub")
		self.assertNotEqual(result, {"status": "stub", "task": "reconcile_recent_accounts"})
		self.assertEqual(result["status"], "completed")
		self.assertEqual(result["run_type"], "Recent Accounts")
		self.assertIn("checked_accounts", result)
		self.assertIn("reconciliation_run", result)

	def test_12_reconciliation_does_not_mutate_ledger_entries(self):
		owner = self._owner("ledger-immutable")
		account = self._grant_account(owner)
		api.consume_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			5,
			idempotency_key=f"gate7-consume-{self._suffix}",
		)
		before = frappe.db.count("Credit Ledger Entry", {"credit_account": account})
		api.reconcile_account(account)
		after = frappe.db.count("Credit Ledger Entry", {"credit_account": account})
		self.assertEqual(before, after)

	def test_13_reconciliation_does_not_silently_repair_balances(self):
		owner = self._owner("no-repair")
		account = self._grant_account(owner)
		frappe.db.set_value("Credit Account", account, "current_balance", 777)
		api.reconcile_account(account)
		self.assertEqual(frappe.db.get_value("Credit Account", account, "current_balance"), 777)

	def test_14_gate5_reversal_lot_inconsistency_is_detectable(self):
		owner = self._owner("reversal-lot")
		settings = frappe.get_single("Credit Settings")
		settings.enable_credit_expiry = 1
		settings.save(ignore_permissions=True)
		grant = api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			30,
			expires_on=add_days(today(), 30),
			idempotency_key=f"gate7-rev-grant-{self._suffix}",
		)
		account = grant["credit_account"]
		entry = LedgerService.find_by_idempotency_key(
			f"gate7-rev-grant-{self._suffix}", entry_type="GRANT"
		)
		LedgerService.reverse_ledger_entry(entry.name)
		result = api.reconcile_account(account)
		self.assertEqual(result["accounts"][0]["status"], "Mismatch")
		details = result["accounts"][0]["details"]
		lot_issues = details["lot_checks"]["issues"]
		self.assertTrue(lot_issues)

	def test_15_credit_balance_report_executes(self):
		columns, data = self._run_report(
			"credit_management.credit_management.report.credit_balance_report.credit_balance_report"
		)
		self.assertTrue(columns)
		self.assertIsInstance(data, list)

	def test_16_credit_ledger_report_executes(self):
		columns, data = self._run_report(
			"credit_management.credit_management.report.credit_ledger_report.credit_ledger_report"
		)
		self.assertTrue(columns)
		self.assertIsInstance(data, list)

	def test_17_credit_usage_by_app_executes(self):
		columns, data = self._run_report(
			"credit_management.credit_management.report.credit_usage_by_app.credit_usage_by_app"
		)
		self.assertTrue(columns)

	def test_18_credit_usage_by_owner_executes(self):
		columns, data = self._run_report(
			"credit_management.credit_management.report.credit_usage_by_owner.credit_usage_by_owner"
		)
		self.assertTrue(columns)

	def test_19_reservation_aging_report_executes(self):
		columns, data = self._run_report(
			"credit_management.credit_management.report.reservation_aging_report.reservation_aging_report"
		)
		self.assertTrue(columns)

	def test_20_expired_credits_report_executes(self):
		columns, data = self._run_report(
			"credit_management.credit_management.report.expired_credits_report.expired_credits_report"
		)
		self.assertTrue(columns)

	def test_21_reconciliation_report_executes(self):
		columns, data = self._run_report(
			"credit_management.credit_management.report.reconciliation_report.reconciliation_report"
		)
		self.assertTrue(columns)

	def test_22_top_credit_consumers_executes(self):
		columns, data = self._run_report(
			"credit_management.credit_management.report.top_credit_consumers.top_credit_consumers"
		)
		self.assertTrue(columns)

	def test_23_credit_grant_history_executes(self):
		columns, data = self._run_report(
			"credit_management.credit_management.report.credit_grant_history.credit_grant_history"
		)
		self.assertTrue(columns)

	def test_24_credit_transfer_history_executes(self):
		columns, data = self._run_report(
			"credit_management.credit_management.report.credit_transfer_history.credit_transfer_history"
		)
		self.assertTrue(columns)

	def test_25_report_permissions_restrict_or_filter_credit_user(self):
		self._grant_account(self.credit_user, key=f"gate7-own-{self._suffix}")
		other = self._owner("other-report")
		self._grant_account(other, key=f"gate7-other-{self._suffix}")

		frappe.set_user(self.credit_user)
		columns, data = self._run_report(
			"credit_management.credit_management.report.credit_balance_report.credit_balance_report"
		)
		owners = {row.get("account_owner_name") for row in data}
		self.assertIn(self.credit_user, owners)
		self.assertNotIn(other, owners)

		with self.assertRaises(frappe.PermissionError):
			self._run_report(
				"credit_management.credit_management.report.credit_usage_by_app.credit_usage_by_app"
			)

	def test_26_workspace_includes_production_report_links(self):
		if not frappe.db.exists("Workspace", "Credit Management"):
			self.skipTest("Credit Management workspace not installed")
		workspace = frappe.get_doc("Workspace", "Credit Management")
		linked = {
			row.link_to
			for row in workspace.links
			if row.link_type == "Report" and row.link_to
		}
		missing = REPORT_LINKS - linked
		self.assertFalse(missing, f"Missing report links: {missing}")

	def test_27_workspace_has_no_old_mvp_links(self):
		if not frappe.db.exists("Workspace", "Credit Management"):
			self.skipTest("Credit Management workspace not installed")
		workspace = frappe.get_doc("Workspace", "Credit Management")
		linked = set()
		for row in workspace.links:
			if row.link_type in ("DocType", "Report") and row.link_to:
				linked.add(row.link_to)
		for row in workspace.shortcuts:
			if row.type == "DocType" and row.link_to:
				linked.add(row.link_to)
		stale = linked.intersection(STALE_MVP_DOCTYPES)
		self.assertFalse(stale)

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