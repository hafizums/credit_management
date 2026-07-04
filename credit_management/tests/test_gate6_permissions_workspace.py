# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

import credit_management.api as api
from credit_management.install import seed_defaults

STALE_MVP_DOCTYPES = {"Credit Transaction", "Credit Management Settings"}
PRODUCTION_WORKSPACE_DOCTYPES = {
	"Credit Account",
	"Credit Ledger Entry",
	"Credit Reservation",
	"Credit Grant",
	"Credit Expiry Lot",
	"Credit Transfer",
	"Credit Type",
	"Credit Settings",
}
CREDIT_ROLES = (
	"Credit User",
	"Credit Manager",
	"Credit Auditor",
	"Credit Developer",
	"System Manager",
)


class TestGate6PermissionsWorkspace(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_defaults()
		cls._suffix = frappe.generate_hash(length=8)
		cls.credit_user = cls._ensure_user(
			f"credit-user-{cls._suffix}@example.com", ["Credit User"]
		)
		cls.credit_manager = cls._ensure_user(
			f"credit-manager-{cls._suffix}@example.com", ["Credit Manager"]
		)
		cls.credit_auditor = cls._ensure_user(
			f"credit-auditor-{cls._suffix}@example.com", ["Credit Auditor"]
		)

	def setUp(self):
		self.owner_doctype = "User"
		self.credit_type = "GENERAL"
		self._suffix = self.__class__._suffix
		self.credit_user = self.__class__.credit_user
		self.credit_manager = self.__class__.credit_manager
		self.credit_auditor = self.__class__.credit_auditor

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

	def _create_account_with_grant(self, owner):
		api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			25,
			idempotency_key=f"gate6-{owner}-{self._suffix}",
		)
		return api.get_or_create_account(self.owner_doctype, owner, self.credit_type)

	def test_01_roles_exist(self):
		for role in CREDIT_ROLES:
			self.assertTrue(frappe.db.exists("Role", role), f"Missing role: {role}")

	def test_02_credit_user_can_read_own_credit_account(self):
		owner = self.credit_user
		account = self._create_account_with_grant(owner)
		frappe.set_user(self.credit_user)
		self.assertTrue(frappe.has_permission("Credit Account", doc=account))

	def test_03_credit_user_cannot_read_another_users_credit_account(self):
		other_owner = self._owner("other-user")
		other_account = self._create_account_with_grant(other_owner)
		self._create_account_with_grant(self.credit_user)
		frappe.set_user(self.credit_user)
		self.assertFalse(frappe.has_permission("Credit Account", doc=other_account))

	def test_04_credit_manager_can_read_all_credit_accounts(self):
		account = self._create_account_with_grant(self._owner("manager-read"))
		frappe.set_user(self.credit_manager)
		self.assertTrue(frappe.has_permission("Credit Account", doc=account))

	def test_05_credit_auditor_can_read_all_credit_accounts(self):
		account = self._create_account_with_grant(self._owner("auditor-read"))
		frappe.set_user(self.credit_auditor)
		self.assertTrue(frappe.has_permission("Credit Account", doc=account))

	def test_06_credit_user_can_read_own_ledger_entries(self):
		owner = self.credit_user
		self._create_account_with_grant(owner)
		result = api.consume_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			5,
			idempotency_key=f"gate6-consume-{self._suffix}",
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		frappe.set_user(self.credit_user)
		self.assertTrue(frappe.has_permission("Credit Ledger Entry", doc=entry))

	def test_07_credit_user_cannot_read_another_users_ledger_entries(self):
		other_owner = self._owner("other-ledger")
		self._create_account_with_grant(other_owner)
		result = api.consume_credits(
			self.owner_doctype,
			other_owner,
			self.credit_type,
			3,
			idempotency_key=f"gate6-other-consume-{self._suffix}",
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		frappe.set_user(self.credit_user)
		self.assertFalse(frappe.has_permission("Credit Ledger Entry", doc=entry))

	def test_08_credit_auditor_can_read_all_ledger_entries(self):
		owner = self._owner("auditor-ledger")
		self._create_account_with_grant(owner)
		result = api.consume_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			4,
			idempotency_key=f"gate6-auditor-consume-{self._suffix}",
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		frappe.set_user(self.credit_auditor)
		self.assertTrue(frappe.has_permission("Credit Ledger Entry", doc=entry))

	def test_09_credit_auditor_cannot_mutate_credit_documents(self):
		frappe.set_user(self.credit_auditor)
		self.assertFalse(frappe.has_permission("Credit Grant", ptype="create"))
		self.assertFalse(frappe.has_permission("Credit Ledger Entry", ptype="create"))
		self.assertFalse(frappe.has_permission("Credit Transfer", ptype="create"))
		self.assertFalse(frappe.has_permission("Credit Account", ptype="write"))

	def test_10_credit_user_cannot_edit_cached_credit_account_balances(self):
		owner = self.credit_user
		account_name = self._create_account_with_grant(owner)
		frappe.set_user(self.credit_user)
		account = frappe.get_doc("Credit Account", account_name)
		self.assertFalse(frappe.has_permission("Credit Account", ptype="write", doc=account))
		account.current_balance = 999
		with self.assertRaises(frappe.PermissionError):
			account.save()

	def test_11_credit_user_cannot_edit_submitted_credit_ledger_entry(self):
		owner = self.credit_user
		self._create_account_with_grant(owner)
		result = api.consume_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			2,
			idempotency_key=f"gate6-ledger-edit-{self._suffix}",
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		frappe.set_user(self.credit_user)
		self.assertFalse(frappe.has_permission("Credit Ledger Entry", ptype="write", doc=entry))
		entry.amount = 999
		with self.assertRaises(frappe.PermissionError):
			entry.save()

	def test_12_credit_manager_can_manage_account_status(self):
		owner = self.credit_manager
		account_name = self._create_account_with_grant(owner)
		frappe.set_user(self.credit_manager)
		account = frappe.get_doc("Credit Account", account_name)
		account.status = "Suspended"
		account.save()
		account.reload()
		self.assertEqual(account.status, "Suspended")

	def test_13_credit_settings_inaccessible_to_credit_user(self):
		frappe.set_user(self.credit_user)
		self.assertFalse(frappe.has_permission("Credit Settings", ptype="read"))

	def test_14_workspace_content_references_widgets(self):
		if not frappe.db.exists("Workspace", "Credit Management"):
			self.skipTest("Credit Management workspace not installed")

		import json

		workspace = frappe.get_doc("Workspace", "Credit Management")
		content = json.loads(workspace.content or "[]")
		types = {block.get("type") for block in content}
		self.assertIn("shortcut", types)
		self.assertIn("card", types)
		self.assertIn("number_card", types)

	def test_15_workspace_has_production_links(self):
		if not frappe.db.exists("Workspace", "Credit Management"):
			self.skipTest("Credit Management workspace not installed")

		workspace = frappe.get_doc("Workspace", "Credit Management")
		linked = set()
		for row in workspace.links:
			if row.link_type == "DocType" and row.link_to:
				linked.add(row.link_to)
		for row in workspace.shortcuts:
			if row.type == "DocType" and row.link_to:
				linked.add(row.link_to)

		missing = PRODUCTION_WORKSPACE_DOCTYPES - linked
		self.assertFalse(missing, f"Workspace missing production links: {missing}")

	def test_16_workspace_has_no_old_mvp_links(self):
		if not frappe.db.exists("Workspace", "Credit Management"):
			self.skipTest("Credit Management workspace not installed")

		workspace = frappe.get_doc("Workspace", "Credit Management")
		linked = set()
		for row in workspace.links:
			if row.link_type == "DocType" and row.link_to:
				linked.add(row.link_to)
		for row in workspace.shortcuts:
			if row.type == "DocType" and row.link_to:
				linked.add(row.link_to)

		stale = linked.intersection(STALE_MVP_DOCTYPES)
		self.assertFalse(stale, f"Workspace contains stale MVP links: {stale}")

	def test_17_gate2_tests_still_pass(self):
		from credit_management.tests.test_gate2_core_ledger import TestGate2CoreLedger

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate2CoreLedger)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())

	def test_18_gate3_tests_still_pass(self):
		from credit_management.tests.test_gate3_reservations import TestGate3Reservations

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate3Reservations)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())

	def test_19_gate4_tests_still_pass(self):
		from credit_management.tests.test_gate4_expiry_lots import TestGate4ExpiryLots

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate4ExpiryLots)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())

	def test_20_gate5_tests_still_pass(self):
		from credit_management.tests.test_gate5_transfers_adjustments import (
			TestGate5TransfersAdjustments,
		)

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate5TransfersAdjustments)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())