# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import unittest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

import credit_management.api as api
from credit_management.exceptions import (
	CreditManagementError,
	InsufficientCreditError,
	InvalidCreditTransferError,
)
from credit_management.install import seed_defaults
from credit_management.services.account_service import AccountService
from credit_management.services.ledger_service import LedgerService


class TestGate5TransfersAdjustments(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		seed_defaults()

	def setUp(self):
		self.owner_doctype = "User"
		self.credit_type = "GENERAL"
		self._suffix = frappe.generate_hash(length=8)

	def _owner(self, label):
		return f"{label}-{self._suffix}"

	def _enable_expiry(self):
		settings = frappe.get_single("Credit Settings")
		settings.reload()
		settings.enable_credit_expiry = 1
		settings.save(ignore_permissions=True)

	def _future_expiry(self, days=30):
		return add_days(today(), days)

	def _account(self, owner):
		return api.get_or_create_account(self.owner_doctype, owner, self.credit_type)

	def test_01_refund_increases_balance(self):
		owner = self._owner("refund-balance")
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 50)
		api.consume_credits(self.owner_doctype, owner, self.credit_type, 20)
		result = api.refund_credits(self.owner_doctype, owner, self.credit_type, 10)
		self.assertEqual(result["current_balance"], 40)

	def test_02_refund_creates_refund_ledger_entry(self):
		owner = self._owner("refund-ledger")
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 30)
		result = api.refund_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			5,
			idempotency_key=f"refund-ledger-{self._suffix}",
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		self.assertEqual(entry.entry_type, "REFUND")
		self.assertEqual(entry.docstatus, 1)
		self.assertEqual(entry.amount, 5)

	def test_03_refund_idempotency_does_not_duplicate(self):
		owner = self._owner("refund-idem")
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 20)
		key = f"refund-idem-{self._suffix}"
		first = api.refund_credits(
			self.owner_doctype, owner, self.credit_type, 8, idempotency_key=key
		)
		second = api.refund_credits(
			self.owner_doctype, owner, self.credit_type, 8, idempotency_key=key
		)
		self.assertTrue(second["idempotent_replay"])
		self.assertEqual(first["ledger_entry"], second["ledger_entry"])
		self.assertEqual(
			frappe.db.count("Credit Ledger Entry", {"idempotency_key": key}), 1
		)

	def test_04_positive_adjustment_increases_balance(self):
		owner = self._owner("adjust-in-balance")
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 10)
		result = api.adjust_credits(
			self.owner_doctype, owner, self.credit_type, 15, reason="Promotional credit"
		)
		self.assertEqual(result["current_balance"], 25)

	def test_05_positive_adjustment_creates_adjust_in_entry(self):
		owner = self._owner("adjust-in-ledger")
		key = f"adjust-in-{self._suffix}"
		result = api.adjust_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			12,
			reason="Manual top-up",
			idempotency_key=key,
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		self.assertEqual(entry.entry_type, "ADJUST_IN")
		self.assertEqual(entry.amount, 12)

	def test_06_negative_adjustment_decreases_balance(self):
		owner = self._owner("adjust-out-balance")
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 40)
		result = api.adjust_credits(
			self.owner_doctype, owner, self.credit_type, -10, reason="Correction"
		)
		self.assertEqual(result["current_balance"], 30)

	def test_07_negative_adjustment_creates_adjust_out_entry(self):
		owner = self._owner("adjust-out-ledger")
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 25)
		key = f"adjust-out-{self._suffix}"
		result = api.adjust_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			-7,
			reason="Write-off",
			idempotency_key=key,
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		self.assertEqual(entry.entry_type, "ADJUST_OUT")
		self.assertEqual(entry.amount, 7)

	def test_08_negative_adjustment_blocks_insufficient_balance(self):
		owner = self._owner("adjust-insufficient")
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 5)
		with self.assertRaises(InsufficientCreditError):
			api.adjust_credits(
				self.owner_doctype, owner, self.credit_type, -10, reason="Too much"
			)

	def test_09_adjustment_requires_reason(self):
		owner = self._owner("adjust-reason")
		with self.assertRaises(CreditManagementError):
			api.adjust_credits(self.owner_doctype, owner, self.credit_type, 5, reason="")

	def test_10_adjustment_idempotency_does_not_duplicate(self):
		owner = self._owner("adjust-idem")
		key = f"adjust-idem-{self._suffix}"
		first = api.adjust_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			6,
			reason="Bonus",
			idempotency_key=key,
		)
		second = api.adjust_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			6,
			reason="Bonus",
			idempotency_key=key,
		)
		self.assertTrue(second["idempotent_replay"])
		self.assertEqual(first["ledger_entry"], second["ledger_entry"])

	def test_11_transfer_creates_credit_transfer_record(self):
		source_owner = self._owner("transfer-record-src")
		target_owner = self._owner("transfer-record-tgt")
		source = self._account(source_owner)
		target = self._account(target_owner)
		api.grant_credits(self.owner_doctype, source_owner, self.credit_type, 50)
		result = api.transfer_credits(source, target, self.credit_type, 20)
		self.assertTrue(result["credit_transfer"])
		self.assertTrue(frappe.db.exists("Credit Transfer", result["credit_transfer"]))
		transfer = frappe.get_doc("Credit Transfer", result["credit_transfer"])
		self.assertEqual(transfer.status, "Completed")

	def test_12_transfer_creates_transfer_out_and_in_entries(self):
		source_owner = self._owner("transfer-ledger-src")
		target_owner = self._owner("transfer-ledger-tgt")
		source = self._account(source_owner)
		target = self._account(target_owner)
		api.grant_credits(self.owner_doctype, source_owner, self.credit_type, 40)
		key = f"transfer-ledger-{self._suffix}"
		result = api.transfer_credits(
			source, target, self.credit_type, 15, idempotency_key=key
		)
		out_entry = frappe.get_doc(
			"Credit Ledger Entry", result["transfer_out_ledger_entry"]
		)
		in_entry = frappe.get_doc(
			"Credit Ledger Entry", result["transfer_in_ledger_entry"]
		)
		self.assertEqual(out_entry.entry_type, "TRANSFER_OUT")
		self.assertEqual(in_entry.entry_type, "TRANSFER_IN")
		self.assertEqual(out_entry.amount, 15)
		self.assertEqual(in_entry.amount, 15)

	def test_13_transfer_decreases_source_balance(self):
		source_owner = self._owner("transfer-src-bal")
		target_owner = self._owner("transfer-src-bal-tgt")
		source = self._account(source_owner)
		target = self._account(target_owner)
		api.grant_credits(self.owner_doctype, source_owner, self.credit_type, 60)
		result = api.transfer_credits(source, target, self.credit_type, 25)
		self.assertEqual(result["source_current_balance"], 35)

	def test_14_transfer_increases_target_balance(self):
		source_owner = self._owner("transfer-tgt-bal")
		target_owner = self._owner("transfer-tgt-bal-tgt")
		source = self._account(source_owner)
		target = self._account(target_owner)
		api.grant_credits(self.owner_doctype, source_owner, self.credit_type, 60)
		result = api.transfer_credits(source, target, self.credit_type, 25)
		self.assertEqual(result["target_current_balance"], 25)

	def test_15_transfer_validates_same_credit_type(self):
		source_owner = self._owner("transfer-type-src")
		target_owner = self._owner("transfer-type-tgt")
		source = self._account(source_owner)
		target = self._account(target_owner)
		api.grant_credits(self.owner_doctype, source_owner, self.credit_type, 20)
		if not frappe.db.exists("Credit Type", "BONUS"):
			frappe.get_doc(
				{
					"doctype": "Credit Type",
					"credit_type_code": "BONUS",
					"title": "Bonus",
					"is_active": 1,
				}
			).insert(ignore_permissions=True)
		with self.assertRaises(InvalidCreditTransferError):
			api.transfer_credits(source, target, "BONUS", 5)

	def test_16_transfer_blocks_same_source_and_target(self):
		owner = self._owner("transfer-same")
		account = self._account(owner)
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 20)
		with self.assertRaises(InvalidCreditTransferError):
			api.transfer_credits(account, account, self.credit_type, 5)

	def test_17_transfer_blocks_insufficient_source_balance(self):
		source_owner = self._owner("transfer-insufficient-src")
		target_owner = self._owner("transfer-insufficient-tgt")
		source = self._account(source_owner)
		target = self._account(target_owner)
		api.grant_credits(self.owner_doctype, source_owner, self.credit_type, 10)
		with self.assertRaises(InsufficientCreditError):
			api.transfer_credits(source, target, self.credit_type, 25)

	def test_18_transfer_idempotency_does_not_duplicate(self):
		source_owner = self._owner("transfer-idem-src")
		target_owner = self._owner("transfer-idem-tgt")
		source = self._account(source_owner)
		target = self._account(target_owner)
		api.grant_credits(self.owner_doctype, source_owner, self.credit_type, 50)
		key = f"transfer-idem-{self._suffix}"
		first = api.transfer_credits(
			source, target, self.credit_type, 12, idempotency_key=key
		)
		second = api.transfer_credits(
			source, target, self.credit_type, 12, idempotency_key=key
		)
		self.assertTrue(second["idempotent_replay"])
		self.assertEqual(first["credit_transfer"], second["credit_transfer"])
		self.assertEqual(
			frappe.db.count("Credit Transfer", {"idempotency_key": key}), 1
		)
		self.assertEqual(
			frappe.db.count("Credit Ledger Entry", {"idempotency_key": f"{key}:transfer-out"}),
			1,
		)
		self.assertEqual(
			frappe.db.count("Credit Ledger Entry", {"idempotency_key": f"{key}:transfer-in"}),
			1,
		)

	def test_19_transfer_locks_accounts_in_deterministic_order(self):
		source_owner = self._owner("transfer-lock-src")
		target_owner = self._owner("transfer-lock-tgt")
		source = self._account(source_owner)
		target = self._account(target_owner)
		api.grant_credits(self.owner_doctype, source_owner, self.credit_type, 30)
		lock_order = []

		original_lock = AccountService.lock_account

		def tracking_lock(account_name):
			lock_order.append(account_name)
			return original_lock(account_name)

		with patch.object(AccountService, "lock_account", side_effect=tracking_lock):
			api.transfer_credits(source, target, self.credit_type, 10)

		self.assertEqual(lock_order, sorted([source, target]))

	def test_20_transfer_source_deduction_uses_fifo_expiry_lots(self):
		self._enable_expiry()
		source_owner = self._owner("transfer-fifo-src")
		target_owner = self._owner("transfer-fifo-tgt")
		source = self._account(source_owner)
		target = self._account(target_owner)
		api.grant_credits(
			self.owner_doctype,
			source_owner,
			self.credit_type,
			30,
			expires_on=self._future_expiry(10),
		)
		api.grant_credits(
			self.owner_doctype,
			source_owner,
			self.credit_type,
			30,
			expires_on=self._future_expiry(40),
		)
		early_lot = frappe.get_all(
			"Credit Expiry Lot",
			filters={"credit_account": source},
			order_by="expires_on asc",
			pluck="name",
		)[0]
		api.transfer_credits(source, target, self.credit_type, 25)
		early = frappe.get_doc("Credit Expiry Lot", early_lot)
		self.assertEqual(early.consumed_amount, 25)
		self.assertEqual(early.remaining_amount, 5)

	def test_21_transfer_target_balance_is_non_expiring(self):
		self._enable_expiry()
		source_owner = self._owner("transfer-nonexp-src")
		target_owner = self._owner("transfer-nonexp-tgt")
		source = self._account(source_owner)
		target = self._account(target_owner)
		api.grant_credits(
			self.owner_doctype,
			source_owner,
			self.credit_type,
			40,
			expires_on=self._future_expiry(15),
		)
		api.transfer_credits(source, target, self.credit_type, 20)
		self.assertEqual(
			frappe.db.count("Credit Expiry Lot", {"credit_account": target}), 0
		)
		balance = api.get_balance(self.owner_doctype, target_owner, self.credit_type)
		self.assertEqual(balance["current_balance"], 20)

	def test_22_refund_is_non_expiring_by_policy(self):
		self._enable_expiry()
		owner = self._owner("refund-nonexp")
		api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			50,
			expires_on=self._future_expiry(20),
		)
		api.consume_credits(self.owner_doctype, owner, self.credit_type, 20)
		lot_count_before = frappe.db.count(
			"Credit Expiry Lot", {"credit_account": api.get_or_create_account(self.owner_doctype, owner, self.credit_type)}
		)
		api.refund_credits(self.owner_doctype, owner, self.credit_type, 10)
		account = api.get_or_create_account(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(
			frappe.db.count("Credit Expiry Lot", {"credit_account": account}),
			lot_count_before,
		)
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["current_balance"], 40)

	def test_23_negative_adjustment_uses_fifo_expiry_lots(self):
		self._enable_expiry()
		owner = self._owner("adjust-fifo")
		account = self._account(owner)
		api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			20,
			expires_on=self._future_expiry(5),
		)
		api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			20,
			expires_on=self._future_expiry(25),
		)
		early_lot = frappe.get_all(
			"Credit Expiry Lot",
			filters={"credit_account": account},
			order_by="expires_on asc",
			pluck="name",
		)[0]
		api.adjust_credits(
			self.owner_doctype, owner, self.credit_type, -15, reason="FIFO deduction"
		)
		early = frappe.get_doc("Credit Expiry Lot", early_lot)
		self.assertEqual(early.consumed_amount, 15)
		self.assertEqual(early.remaining_amount, 5)

	def test_24_reversal_creates_reversal_ledger_entry(self):
		owner = self._owner("reversal-entry")
		api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			30,
			idempotency_key=f"grant-reversal-{self._suffix}",
		)
		grant_entry = LedgerService.find_by_idempotency_key(
			f"grant-reversal-{self._suffix}", entry_type="GRANT"
		)
		result = LedgerService.reverse_ledger_entry(grant_entry.name)
		reversal = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		self.assertEqual(reversal.entry_type, "REVERSAL")
		self.assertEqual(reversal.docstatus, 1)

	def test_25_reversal_references_reversed_entry(self):
		owner = self._owner("reversal-ref")
		api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			20,
			idempotency_key=f"grant-ref-{self._suffix}",
		)
		grant_entry = LedgerService.find_by_idempotency_key(
			f"grant-ref-{self._suffix}", entry_type="GRANT"
		)
		result = LedgerService.reverse_ledger_entry(grant_entry.name)
		reversal = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		self.assertEqual(reversal.reversed_entry, grant_entry.name)
		self.assertEqual(result["reversed_entry"], grant_entry.name)

	def test_26_reversal_does_not_edit_original_ledger_entry(self):
		owner = self._owner("reversal-immutable")
		api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			18,
			idempotency_key=f"grant-immutable-{self._suffix}",
		)
		grant_entry = LedgerService.find_by_idempotency_key(
			f"grant-immutable-{self._suffix}", entry_type="GRANT"
		)
		original_amount = grant_entry.amount
		original_docstatus = grant_entry.docstatus
		LedgerService.reverse_ledger_entry(grant_entry.name)
		grant_entry.reload()
		self.assertEqual(grant_entry.amount, original_amount)
		self.assertEqual(grant_entry.docstatus, original_docstatus)

	def test_27_gate2_tests_still_pass(self):
		from credit_management.tests.test_gate2_core_ledger import TestGate2CoreLedger

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate2CoreLedger)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())

	def test_28_gate3_tests_still_pass(self):
		from credit_management.tests.test_gate3_reservations import TestGate3Reservations

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate3Reservations)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())

	def test_29_gate4_tests_still_pass(self):
		from credit_management.tests.test_gate4_expiry_lots import TestGate4ExpiryLots

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate4ExpiryLots)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())