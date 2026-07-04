# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests.utils import FrappeTestCase

import credit_management.api as api
from credit_management.exceptions import (
	CreditAccountSuspendedError,
	InsufficientCreditError,
	InvalidCreditAmountError,
)
from credit_management.install import seed_defaults

STALE_MVP_DOCTYPES = {"Credit Transaction", "Credit Management Settings"}


class TestGate2CoreLedger(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_defaults()

	def setUp(self):
		self.owner_doctype = "User"
		self.owner_name = "Administrator"
		self.credit_type = "GENERAL"
		self._test_suffix = frappe.generate_hash(length=8)

	def test_01_credit_type_default_exists(self):
		self.assertTrue(frappe.db.exists("Credit Type", "GENERAL"))
		general = frappe.get_doc("Credit Type", "GENERAL")
		self.assertEqual(general.credit_type_code, "GENERAL")
		self.assertTrue(general.is_active)

	def test_02_account_creation(self):
		account = api.get_or_create_account(
			self.owner_doctype,
			f"test-user-{self._test_suffix}",
			self.credit_type,
		)
		self.assertTrue(frappe.db.exists("Credit Account", account))
		doc = frappe.get_doc("Credit Account", account)
		self.assertEqual(doc.status, "Active")
		self.assertEqual(doc.current_balance, 0)

	def test_03_account_uniqueness(self):
		owner = f"unique-user-{self._test_suffix}"
		first = api.get_or_create_account(self.owner_doctype, owner, self.credit_type)
		second = api.get_or_create_account(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(first, second)

		company_account = api.get_or_create_account(
			self.owner_doctype, owner, self.credit_type, company="Test Co"
		)
		self.assertNotEqual(first, company_account)

	def test_04_get_balance(self):
		owner = f"balance-user-{self._test_suffix}"
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 25)
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertIn("credit_account", balance)
		self.assertEqual(balance["credit_type"], self.credit_type)
		self.assertEqual(balance["current_balance"], 25)
		self.assertEqual(balance["reserved_balance"], 0)
		self.assertEqual(balance["available_balance"], 25)

	def test_05_grant_increases_balance(self):
		owner = f"grant-user-{self._test_suffix}"
		result = api.grant_credits(self.owner_doctype, owner, self.credit_type, 50)
		self.assertEqual(result["amount"], 50)
		self.assertEqual(result["current_balance"], 50)
		self.assertFalse(result["idempotent_replay"])

	def test_06_grant_creates_ledger_entry(self):
		owner = f"ledger-grant-{self._test_suffix}"
		result = api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			15,
			idempotency_key=f"grant-ledger-{self._test_suffix}",
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		self.assertEqual(entry.entry_type, "GRANT")
		self.assertEqual(entry.docstatus, 1)
		self.assertEqual(entry.amount, 15)

	def test_07_idempotent_grant_does_not_duplicate(self):
		owner = f"idempotent-grant-{self._test_suffix}"
		key = f"idempotent-grant-key-{self._test_suffix}"
		first = api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 10, idempotency_key=key
		)
		second = api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 10, idempotency_key=key
		)
		self.assertTrue(second["idempotent_replay"])
		self.assertEqual(first["ledger_entry"], second["ledger_entry"])
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["current_balance"], 10)

	def test_08_consume_decreases_balance(self):
		owner = f"consume-user-{self._test_suffix}"
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 40)
		result = api.consume_credits(self.owner_doctype, owner, self.credit_type, 12)
		self.assertEqual(result["amount"], 12)
		self.assertEqual(result["current_balance"], 28)

	def test_09_consume_creates_ledger_entry(self):
		owner = f"ledger-consume-{self._test_suffix}"
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 30)
		result = api.consume_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			8,
			idempotency_key=f"consume-ledger-{self._test_suffix}",
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		self.assertEqual(entry.entry_type, "CONSUME")
		self.assertEqual(entry.docstatus, 1)
		self.assertEqual(entry.amount, 8)

	def test_10_insufficient_balance_blocks_consume(self):
		owner = f"insufficient-{self._test_suffix}"
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 5)
		with self.assertRaises(InsufficientCreditError):
			api.consume_credits(self.owner_doctype, owner, self.credit_type, 10)

	def test_11_negative_balance_only_when_allowed(self):
		owner = f"negative-{self._test_suffix}"
		credit_type = f"NEG-{self._test_suffix}"
		frappe.get_doc(
			{
				"doctype": "Credit Type",
				"credit_type_code": credit_type,
				"title": "Negative Allowed",
				"allow_negative_balance": 1,
				"is_active": 1,
			}
		).insert(ignore_permissions=True)

		api.grant_credits(self.owner_doctype, owner, credit_type, 5)
		with self.assertRaises(InsufficientCreditError):
			api.consume_credits(self.owner_doctype, owner, self.credit_type, 10)

		result = api.consume_credits(self.owner_doctype, owner, credit_type, 10)
		self.assertEqual(result["current_balance"], -5)

	def test_12_idempotent_consume_does_not_duplicate(self):
		owner = f"idempotent-consume-{self._test_suffix}"
		key = f"idempotent-consume-key-{self._test_suffix}"
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 20)
		first = api.consume_credits(
			self.owner_doctype, owner, self.credit_type, 7, idempotency_key=key
		)
		second = api.consume_credits(
			self.owner_doctype, owner, self.credit_type, 7, idempotency_key=key
		)
		self.assertTrue(second["idempotent_replay"])
		self.assertEqual(first["ledger_entry"], second["ledger_entry"])
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["current_balance"], 13)

	def test_13_suspended_account_cannot_consume(self):
		owner = f"suspended-{self._test_suffix}"
		account_name = api.get_or_create_account(self.owner_doctype, owner, self.credit_type)
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 20)
		frappe.db.set_value("Credit Account", account_name, "status", "Suspended")

		with self.assertRaises(CreditAccountSuspendedError):
			api.consume_credits(self.owner_doctype, owner, self.credit_type, 5)

	def test_14_ledger_entry_cannot_be_edited_after_submit(self):
		owner = f"immutable-{self._test_suffix}"
		result = api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			10,
			idempotency_key=f"immutable-{self._test_suffix}",
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		entry.amount = 999
		with self.assertRaises(frappe.ValidationError):
			entry.save()

	def test_15_workspace_has_no_stale_mvp_links(self):
		if not frappe.db.exists("Workspace", "Credit Management"):
			self.skipTest("Credit Management workspace not installed")

		workspace = frappe.get_doc("Workspace", "Credit Management")
		linked_doctypes = set()

		for row in workspace.links:
			if row.link_type == "DocType" and row.link_to:
				linked_doctypes.add(row.link_to)

		for row in workspace.shortcuts:
			if row.type == "DocType" and row.link_to:
				linked_doctypes.add(row.link_to)

		stale = linked_doctypes.intersection(STALE_MVP_DOCTYPES)
		self.assertFalse(stale, f"Workspace contains stale MVP links: {stale}")

	def test_grant_rejects_non_positive_amount(self):
		with self.assertRaises(InvalidCreditAmountError):
			api.grant_credits(self.owner_doctype, self.owner_name, self.credit_type, 0)

	def test_consume_rejects_non_positive_amount(self):
		with self.assertRaises(InvalidCreditAmountError):
			api.consume_credits(self.owner_doctype, self.owner_name, self.credit_type, -5)