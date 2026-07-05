# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Milestone 17 admin UX tests."""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

import credit_management.admin_ux as admin_ux
import credit_management.api as api
from credit_management.install import seed_defaults

STALE_MVP_DOCTYPES = {"Credit Transaction", "Credit Management Settings"}
REQUIRED_SHORTCUTS = {
	"Credit Account",
	"Credit Ledger Entry",
	"Credit Reservation",
	"Credit Grant",
	"Credit Expiry Lot",
	"Credit Transfer",
	"Credit Reconciliation Run",
	"Credit Integration Log",
	"Credit Webhook Event",
	"Credit Settings",
	"Credit Admin Tools",
}


class TestM17AdminUX(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_defaults()
		cls._suffix = frappe.generate_hash(length=8)
		cls.credit_user = cls._ensure_user(
			f"m17-user-{cls._suffix}@example.com", ["Credit User"]
		)
		cls.credit_manager = cls._ensure_user(
			f"m17-manager-{cls._suffix}@example.com", ["Credit Manager"]
		)

	def setUp(self):
		self.owner_doctype = "User"
		self.credit_type = "GENERAL"
		self._suffix = self.__class__._suffix
		self._owner = f"m17-owner-{self._suffix}"

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

	def _grant(self, owner=None, amount=100):
		owner = owner or self._owner
		api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			amount,
			idempotency_key=f"m17-grant-{owner}-{self._suffix}",
		)
		return api.get_or_create_account(self.owner_doctype, owner, self.credit_type)

	def test_01_credit_manager_can_use_top_up_helper(self):
		frappe.set_user(self.credit_manager)
		result = admin_ux.admin_top_up_credits(
			self.owner_doctype,
			self._owner,
			self.credit_type,
			25,
			grant_reason="M17 manager top-up",
		)
		self.assertEqual(result["entry_type"], "GRANT")
		self.assertGreater(result["balance_after"]["current_balance"], result["balance_before"]["current_balance"])

	def test_02_credit_user_cannot_use_top_up_helper(self):
		frappe.set_user(self.credit_user)
		with self.assertRaises(frappe.PermissionError):
			admin_ux.admin_top_up_credits(
				self.owner_doctype,
				self.credit_user,
				self.credit_type,
				10,
				grant_reason="should fail",
			)

	def test_03_top_up_helper_creates_grant_ledger_entry(self):
		frappe.set_user(self.credit_manager)
		result = admin_ux.admin_top_up_credits(
			self.owner_doctype,
			self._owner,
			self.credit_type,
			15,
			grant_reason="M17 grant ledger",
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		self.assertEqual(entry.entry_type, "GRANT")
		self.assertEqual(entry.docstatus, 1)

	def test_04_top_up_helper_does_not_mutate_balance_directly(self):
		frappe.set_user(self.credit_manager)
		account = self._grant(amount=50)
		before_entries = frappe.db.count(
			"Credit Ledger Entry", {"credit_account": account, "entry_type": "GRANT"}
		)
		result = admin_ux.admin_top_up_credits(
			self.owner_doctype,
			self._owner,
			self.credit_type,
			5,
			grant_reason="ledger path only",
		)
		after_entries = frappe.db.count(
			"Credit Ledger Entry", {"credit_account": account, "entry_type": "GRANT"}
		)
		self.assertEqual(after_entries, before_entries + 1)
		self.assertTrue(result["ledger_entry"])
		self.assertEqual(result["entry_type"], "GRANT")

	def test_05_refund_helper_creates_refund_ledger_entry(self):
		self._grant(amount=80)
		frappe.set_user(self.credit_manager)
		result = admin_ux.admin_refund_credits(
			self.owner_doctype,
			self._owner,
			self.credit_type,
			10,
			refund_reason="M17 refund test",
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		self.assertEqual(entry.entry_type, "REFUND")
		self.assertEqual(entry.docstatus, 1)

	def test_06_credit_user_cannot_refund(self):
		self._grant(owner=self.credit_user, amount=40)
		frappe.set_user(self.credit_user)
		with self.assertRaises(frappe.PermissionError):
			admin_ux.admin_refund_credits(
				self.owner_doctype,
				self.credit_user,
				self.credit_type,
				5,
				refund_reason="should fail",
			)

	def test_07_reservation_release_action_releases_active_reservation(self):
		self._grant(amount=50)
		reserve = api.reserve_credits(
			owner_doctype=self.owner_doctype,
			owner_name=self._owner,
			credit_type=self.credit_type,
			amount=10,
			idempotency_key=f"m17-reserve-{self._suffix}",
		)
		frappe.set_user(self.credit_manager)
		result = admin_ux.admin_release_reservation(
			reserve["reservation"],
			reason="M17 admin release",
		)
		self.assertEqual(result["entry_type"], "RELEASE_RESERVE")
		reservation = frappe.get_doc("Credit Reservation", reserve["reservation"])
		self.assertIn(reservation.status, ("Released", "Expired"))

	def test_08_reservation_release_action_blocks_consumed_reservation(self):
		self._grant(amount=50)
		reserve = api.reserve_credits(
			owner_doctype=self.owner_doctype,
			owner_name=self._owner,
			credit_type=self.credit_type,
			amount=8,
			idempotency_key=f"m17-reserve-consume-{self._suffix}",
		)
		api.consume_reserved_credits(
			reserve["reservation"],
			actual_amount=8,
			idempotency_key=f"m17-consume-{self._suffix}",
		)
		frappe.set_user(self.credit_manager)
		with self.assertRaises(frappe.ValidationError):
			admin_ux.admin_release_reservation(
				reserve["reservation"],
				reason="should fail on consumed",
			)

	def test_09_reconciliation_review_action_runs_detect_only_reconcile(self):
		account = self._grant(amount=30)
		frappe.set_user(self.credit_manager)
		result = admin_ux.admin_rerun_reconcile_account(account)
		self.assertEqual(result["auto_repair_performed"], False)
		self.assertIn(result["reconciliation"]["summary_status"], ("Passed", "Mismatch"))

	def test_10_reconciliation_review_does_not_auto_repair(self):
		account = self._grant(amount=30)
		frappe.db.set_value("Credit Account", account, "current_balance", 999)
		account_doc = frappe.get_doc("Credit Account", account)
		before_current = account_doc.current_balance

		frappe.set_user(self.credit_manager)
		result = admin_ux.admin_rerun_reconcile_account(account)
		account_doc.reload()

		self.assertEqual(result["auto_repair_performed"], False)
		self.assertEqual(float(account_doc.current_balance), float(before_current))
		self.assertEqual(result["reconciliation"]["summary_status"], "Mismatch")

	def test_11_balance_quick_view_respects_role_permissions(self):
		self._grant(owner=self.credit_user, amount=20)
		other = f"m17-other-{self._suffix}"
		self._grant(owner=other, amount=20)

		frappe.set_user(self.credit_user)
		own = admin_ux.admin_get_account_balance_overview(
			"User", self.credit_user, self.credit_type
		)
		self.assertEqual(own["account"]["owner_name"], self.credit_user)

		with self.assertRaises(frappe.PermissionError):
			admin_ux.admin_get_account_balance_overview("User", other, self.credit_type)

		frappe.set_user(self.credit_manager)
		other_view = admin_ux.admin_get_account_balance_overview("User", other, self.credit_type)
		self.assertEqual(other_view["account"]["owner_name"], other)

	def test_12_workspace_has_admin_shortcuts(self):
		if not frappe.db.exists("Workspace", "Credit Management"):
			self.skipTest("Credit Management workspace not installed")

		workspace = frappe.get_doc("Workspace", "Credit Management")
		shortcuts = {row.label for row in workspace.shortcuts if row.label}
		missing = REQUIRED_SHORTCUTS - shortcuts
		self.assertFalse(missing, f"Missing workspace shortcuts: {missing}")

	def test_13_workspace_has_no_old_mvp_links(self):
		if not frappe.db.exists("Workspace", "Credit Management"):
			self.skipTest("Credit Management workspace not installed")

		workspace = frappe.get_doc("Workspace", "Credit Management")
		linked = set()
		for row in workspace.links:
			if row.link_to:
				linked.add(row.link_to)
		for row in workspace.shortcuts:
			if row.link_to:
				linked.add(row.link_to)
		stale = linked.intersection(STALE_MVP_DOCTYPES)
		self.assertFalse(stale, f"Workspace contains stale MVP links: {stale}")

	def test_14_existing_gate_tests_still_pass(self):
		from credit_management.tests.test_gate6_permissions_workspace import (
			TestGate6PermissionsWorkspace,
		)
		from credit_management.tests.test_gate8_integration_layer import (
			TestGate8IntegrationLayer,
		)
		from credit_management.tests.test_m16_security_review import TestM16SecurityReview

		for testcase in (
			TestGate6PermissionsWorkspace,
			TestGate8IntegrationLayer,
			TestM16SecurityReview,
		):
			suite = unittest.TestLoader().loadTestsFromTestCase(testcase)
			result = unittest.TextTestRunner().run(suite)
			self.assertTrue(result.wasSuccessful(), f"{testcase.__name__} regressed")