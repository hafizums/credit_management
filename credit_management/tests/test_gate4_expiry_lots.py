# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today

import credit_management.api as api
from credit_management import tasks
from credit_management.install import seed_defaults


class TestGate4ExpiryLots(FrappeTestCase):
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

	def _disable_expiry(self):
		settings = frappe.get_single("Credit Settings")
		settings.reload()
		settings.enable_credit_expiry = 0
		settings.save(ignore_permissions=True)

	def _future_expiry(self, days=30):
		return add_days(today(), days)

	def _past_expiry(self, days=1):
		return add_days(today(), -days)

	def test_01_grant_without_expires_on_no_lot(self):
		owner = self._owner("no-expiry")
		self._enable_expiry()
		account = api.get_or_create_account(self.owner_doctype, owner, self.credit_type)
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 50)
		self.assertEqual(frappe.db.count("Credit Expiry Lot", {"credit_account": account}), 0)

	def test_02_grant_with_expires_on_creates_credit_grant(self):
		owner = self._owner("grant-doc")
		self._enable_expiry()
		result = api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			40,
			expires_on=self._future_expiry(),
			idempotency_key=f"grant-doc-{self._suffix}",
		)
		self.assertTrue(result.get("credit_grant"))
		self.assertTrue(frappe.db.exists("Credit Grant", result["credit_grant"]))

	def test_03_grant_with_expiry_enabled_creates_lot(self):
		owner = self._owner("grant-lot")
		self._enable_expiry()
		result = api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			60,
			expires_on=self._future_expiry(),
		)
		self.assertTrue(result.get("expiry_lot"))
		lot = frappe.get_doc("Credit Expiry Lot", result["expiry_lot"])
		self.assertEqual(lot.original_amount, 60)
		self.assertEqual(lot.remaining_amount, 60)
		self.assertEqual(lot.status, "Active")

	def test_04_grant_with_expiry_disabled_no_lot(self):
		owner = self._owner("grant-disabled")
		self._disable_expiry()
		result = api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			45,
			expires_on=self._future_expiry(),
		)
		self.assertFalse(result.get("expiry_lot"))
		self.assertFalse(result.get("credit_grant"))

	def test_05_lot_amounts_correct(self):
		owner = self._owner("lot-amounts")
		self._enable_expiry()
		result = api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			75,
			expires_on=self._future_expiry(10),
		)
		lot = frappe.get_doc("Credit Expiry Lot", result["expiry_lot"])
		self.assertEqual(lot.original_amount, 75)
		self.assertEqual(lot.remaining_amount, 75)
		self.assertEqual(getdate(lot.expires_on), getdate(self._future_expiry(10)))

	def test_06_direct_consume_fifo_earliest_first(self):
		owner = self._owner("fifo")
		self._enable_expiry()
		api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			30,
			expires_on=self._future_expiry(20),
		)
		late = api.grant_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			30,
			expires_on=self._future_expiry(40),
		)
		early_lot = frappe.get_all(
			"Credit Expiry Lot",
			filters={"credit_account": late["credit_account"]},
			order_by="expires_on asc",
			pluck="name",
		)[0]
		api.consume_credits(self.owner_doctype, owner, self.credit_type, 25)
		early = frappe.get_doc("Credit Expiry Lot", early_lot)
		self.assertEqual(early.consumed_amount, 25)
		self.assertEqual(early.remaining_amount, 5)

	def test_07_direct_consume_spans_multiple_lots(self):
		owner = self._owner("multi-lot")
		self._enable_expiry()
		api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 20, expires_on=self._future_expiry(5)
		)
		api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 20, expires_on=self._future_expiry(15)
		)
		api.consume_credits(self.owner_doctype, owner, self.credit_type, 35)
		lots = frappe.get_all(
			"Credit Expiry Lot",
			filters={"credit_account": api.get_or_create_account(self.owner_doctype, owner, self.credit_type)},
			fields=["consumed_amount", "remaining_amount", "status"],
			order_by="expires_on asc",
		)
		self.assertEqual(lots[0]["consumed_amount"], 20)
		self.assertEqual(lots[0]["status"], "Exhausted")
		self.assertEqual(lots[1]["consumed_amount"], 15)
		self.assertEqual(lots[1]["remaining_amount"], 5)

	def test_08_direct_consume_expiring_and_non_expiring(self):
		owner = self._owner("mixed-consume")
		self._enable_expiry()
		api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 30, expires_on=self._future_expiry()
		)
		api.grant_credits(self.owner_doctype, owner, self.credit_type, 50)
		api.consume_credits(self.owner_doctype, owner, self.credit_type, 70)
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["current_balance"], 10)

	def test_09_direct_consume_marks_lot_exhausted(self):
		owner = self._owner("exhausted")
		self._enable_expiry()
		result = api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 25, expires_on=self._future_expiry()
		)
		api.consume_credits(self.owner_doctype, owner, self.credit_type, 25)
		lot = frappe.get_doc("Credit Expiry Lot", result["expiry_lot"])
		self.assertEqual(lot.status, "Exhausted")
		self.assertEqual(lot.remaining_amount, 0)

	def test_10_daily_expiry_creates_expire_ledger(self):
		owner = self._owner("expire-ledger")
		self._enable_expiry()
		api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 40, expires_on=self._past_expiry()
		)
		tasks.expire_credits()
		entry = frappe.db.get_value(
			"Credit Ledger Entry",
			{"entry_type": "EXPIRE", "docstatus": 1},
			"name",
			order_by="creation desc",
		)
		self.assertTrue(entry)

	def test_11_daily_expiry_decreases_current_balance(self):
		owner = self._owner("expire-balance")
		self._enable_expiry()
		api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 40, expires_on=self._past_expiry()
		)
		before = api.get_balance(self.owner_doctype, owner, self.credit_type)
		tasks.expire_credits()
		after = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(after["current_balance"], before["current_balance"] - 40)

	def test_12_daily_expiry_increases_lifetime_expired(self):
		owner = self._owner("lifetime-expired")
		self._enable_expiry()
		account = api.get_or_create_account(self.owner_doctype, owner, self.credit_type)
		api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 35, expires_on=self._past_expiry()
		)
		tasks.expire_credits()
		lifetime = frappe.db.get_value("Credit Account", account, "lifetime_expired")
		self.assertEqual(lifetime, 35)

	def test_13_daily_expiry_not_twice_on_exhausted(self):
		owner = self._owner("no-double-expire")
		self._enable_expiry()
		result = api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 20, expires_on=self._future_expiry()
		)
		api.consume_credits(self.owner_doctype, owner, self.credit_type, 20)
		lot = frappe.get_doc("Credit Expiry Lot", result["expiry_lot"])
		lot.db_set("expires_on", self._past_expiry())
		first = tasks.expire_credits()
		second = tasks.expire_credits()
		self.assertEqual(first["expired"], 0)
		self.assertEqual(second["expired"], 0)

	def test_14_daily_expiry_idempotent(self):
		owner = self._owner("expire-idempotent")
		self._enable_expiry()
		result = api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 22, expires_on=self._past_expiry()
		)
		first = tasks.expire_credits()
		second = tasks.expire_credits()
		self.assertGreaterEqual(first["expired"], 1)
		self.assertEqual(second["expired"], 0)
		expire_key = f"expiry-lot:{result['expiry_lot']}:expire"
		self.assertEqual(
			frappe.db.count(
				"Credit Ledger Entry",
				{"idempotency_key": expire_key, "entry_type": "EXPIRE", "docstatus": 1},
			),
			1,
		)

	def test_15_reservation_allocates_earliest_lot_first(self):
		owner = self._owner("reserve-fifo")
		self._enable_expiry()
		api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 50, expires_on=self._future_expiry(10)
		)
		api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 50, expires_on=self._future_expiry(30)
		)
		reserve = api.reserve_credits(self.owner_doctype, owner, self.credit_type, 30)
		reservation = frappe.get_doc("Credit Reservation", reserve["reservation"])
		self.assertEqual(len(reservation.expiry_lot_allocations), 1)
		early_lot = frappe.get_all(
			"Credit Expiry Lot",
			filters={"credit_account": reserve["credit_account"]},
			order_by="expires_on asc",
			pluck="name",
		)[0]
		self.assertEqual(reservation.expiry_lot_allocations[0].expiry_lot, early_lot)

	def test_16_reserved_consume_updates_lot_amounts(self):
		owner = self._owner("reserved-consume-lot")
		self._enable_expiry()
		grant = api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 50, expires_on=self._future_expiry()
		)
		reserve = api.reserve_credits(self.owner_doctype, owner, self.credit_type, 40)
		api.consume_reserved_credits(reserve["reservation"], actual_amount=40)
		lot = frappe.get_doc("Credit Expiry Lot", grant["expiry_lot"])
		self.assertEqual(lot.reserved_amount, 0)
		self.assertEqual(lot.consumed_amount, 40)
		self.assertEqual(lot.remaining_amount, 10)

	def test_17_reserved_release_updates_lot_reserved_not_remaining(self):
		owner = self._owner("reserved-release-lot")
		self._enable_expiry()
		grant = api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 50, expires_on=self._future_expiry()
		)
		reserve = api.reserve_credits(self.owner_doctype, owner, self.credit_type, 30)
		lot_before = frappe.get_doc("Credit Expiry Lot", grant["expiry_lot"])
		api.release_reservation(reserve["reservation"], reason="cancelled")
		lot = frappe.get_doc("Credit Expiry Lot", grant["expiry_lot"])
		self.assertEqual(lot.reserved_amount, 0)
		self.assertEqual(lot.remaining_amount, lot_before.remaining_amount)

	def test_18_partial_reserved_consume_releases_unused_allocation(self):
		owner = self._owner("partial-reserve-release")
		self._enable_expiry()
		api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 100, expires_on=self._future_expiry()
		)
		reserve = api.reserve_credits(self.owner_doctype, owner, self.credit_type, 100)
		api.consume_reserved_credits(reserve["reservation"], actual_amount=70)
		reservation = frappe.get_doc("Credit Reservation", reserve["reservation"])
		self.assertEqual(reservation.released_amount, 30)
		entries = frappe.get_all(
			"Credit Ledger Entry",
			{
				"reference_name": reserve["reservation"],
				"docstatus": 1,
			},
			["entry_type", "amount"],
		)
		types = {row.entry_type: row.amount for row in entries}
		self.assertEqual(types.get("CONSUME_RESERVE"), 70)
		self.assertEqual(types.get("RELEASE_RESERVE"), 30)

	def test_19_reserved_amount_not_expired_while_active(self):
		owner = self._owner("reserved-not-expired")
		self._enable_expiry()
		grant = api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 50, expires_on=self._past_expiry()
		)
		reserve = api.reserve_credits(self.owner_doctype, owner, self.credit_type, 40)
		tasks.expire_credits()
		lot = frappe.get_doc("Credit Expiry Lot", grant["expiry_lot"])
		self.assertEqual(lot.reserved_amount, 40)
		self.assertEqual(lot.remaining_amount, 40)
		self.assertEqual(lot.expired_amount, 10)
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["current_balance"], 40)

	def test_20_released_reserved_from_expired_lot_expired_by_scheduler(self):
		owner = self._owner("released-then-expired")
		self._enable_expiry()
		grant = api.grant_credits(
			self.owner_doctype, owner, self.credit_type, 50, expires_on=self._past_expiry()
		)
		reserve = api.reserve_credits(self.owner_doctype, owner, self.credit_type, 40)
		tasks.expire_credits()
		api.release_reservation(reserve["reservation"], reason="failure")
		balance_after_release = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance_after_release["current_balance"], 0)
		tasks.expire_credits()
		balance_final = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance_final["current_balance"], 0)
		lot = frappe.get_doc("Credit Expiry Lot", grant["expiry_lot"])
		self.assertGreaterEqual(lot.expired_amount, 50)

	def test_21_gate2_tests_still_pass(self):
		from credit_management.tests.test_gate2_core_ledger import TestGate2CoreLedger

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate2CoreLedger)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())

	def test_22_gate3_tests_still_pass(self):
		from credit_management.tests.test_gate3_reservations import TestGate3Reservations

		suite = unittest.TestLoader().loadTestsFromTestCase(TestGate3Reservations)
		result = unittest.TextTestRunner().run(suite)
		self.assertTrue(result.wasSuccessful())