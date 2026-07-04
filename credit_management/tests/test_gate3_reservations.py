# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

import credit_management.api as api
from credit_management import tasks
from credit_management.exceptions import (
	CreditAccountSuspendedError,
	CreditReservationError,
	InsufficientCreditError,
)
from credit_management.install import seed_defaults
class TestGate3Reservations(FrappeTestCase):
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

	def _fund(self, owner, amount=1000):
		api.grant_credits(self.owner_doctype, owner, self.credit_type, amount)

	def _reserve(self, owner, amount, **kwargs):
		return api.reserve_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			amount,
			**kwargs,
		)

	def test_01_reserve_creates_credit_reservation(self):
		owner = self._owner("reserve-doc")
		self._fund(owner)
		result = self._reserve(owner, 70, idempotency_key=f"job:{self._suffix}:reserve")
		self.assertTrue(frappe.db.exists("Credit Reservation", result["reservation"]))
		reservation = frappe.get_doc("Credit Reservation", result["reservation"])
		self.assertEqual(reservation.status, "Active")
		self.assertEqual(reservation.reserved_amount, 70)

	def test_02_reserve_creates_reserve_ledger_entry(self):
		owner = self._owner("reserve-ledger")
		self._fund(owner)
		key = f"job:{self._suffix}:reserve-ledger"
		result = self._reserve(owner, 50, idempotency_key=key)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		self.assertEqual(entry.entry_type, "RESERVE")
		self.assertEqual(entry.docstatus, 1)
		self.assertEqual(entry.amount, 50)

	def test_03_reserve_increases_reserved_balance(self):
		owner = self._owner("reserve-inc")
		self._fund(owner, 500)
		self._reserve(owner, 80)
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["reserved_balance"], 80)

	def test_04_reserve_decreases_available_balance(self):
		owner = self._owner("reserve-avail")
		self._fund(owner, 500)
		self._reserve(owner, 120)
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["available_balance"], 380)

	def test_05_reserve_does_not_decrease_current_balance(self):
		owner = self._owner("reserve-current")
		self._fund(owner, 500)
		before = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self._reserve(owner, 90)
		after = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(before["current_balance"], after["current_balance"])

	def test_06_insufficient_balance_blocks_reservation(self):
		owner = self._owner("reserve-insufficient")
		self._fund(owner, 10)
		with self.assertRaises(InsufficientCreditError):
			self._reserve(owner, 50)

	def test_07_suspended_account_cannot_reserve(self):
		owner = self._owner("reserve-suspended")
		account_name = api.get_or_create_account(self.owner_doctype, owner, self.credit_type)
		self._fund(owner, 100)
		frappe.db.set_value("Credit Account", account_name, "status", "Suspended")
		with self.assertRaises(CreditAccountSuspendedError):
			self._reserve(owner, 10)

	def test_08_duplicate_reserve_idempotency(self):
		owner = self._owner("reserve-idempotent")
		self._fund(owner, 200)
		key = f"job:{self._suffix}:reserve-dup"
		first = self._reserve(owner, 40, idempotency_key=key)
		second = self._reserve(owner, 40, idempotency_key=key)
		self.assertTrue(second["idempotent_replay"])
		self.assertEqual(first["reservation"], second["reservation"])
		self.assertEqual(
			frappe.db.count("Credit Reservation", {"idempotency_key": key}),
			1,
		)
		self.assertEqual(
			frappe.db.count(
				"Credit Ledger Entry",
				{"idempotency_key": key, "entry_type": "RESERVE", "docstatus": 1},
			),
			1,
		)

	def test_09_consume_reserved_decreases_current_balance(self):
		owner = self._owner("consume-current")
		self._fund(owner, 500)
		reserve = self._reserve(owner, 60)
		api.consume_reserved_credits(
			reserve["reservation"],
			idempotency_key=f"job:{self._suffix}:consume",
		)
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["current_balance"], 440)

	def test_10_consume_reserved_decreases_reserved_balance(self):
		owner = self._owner("consume-reserved-bal")
		self._fund(owner, 500)
		reserve = self._reserve(owner, 60)
		api.consume_reserved_credits(reserve["reservation"])
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["reserved_balance"], 0)

	def test_11_consume_creates_consume_reserve_ledger_entry(self):
		owner = self._owner("consume-ledger")
		self._fund(owner, 500)
		reserve = self._reserve(owner, 45)
		key = f"job:{self._suffix}:consume-ledger"
		result = api.consume_reserved_credits(reserve["reservation"], idempotency_key=key)
		entry = frappe.get_doc("Credit Ledger Entry", result["consume_ledger_entry"])
		self.assertEqual(entry.entry_type, "CONSUME_RESERVE")
		self.assertEqual(entry.docstatus, 1)
		self.assertEqual(entry.amount, 45)

	def test_12_full_consume_sets_status_consumed(self):
		owner = self._owner("consume-full")
		self._fund(owner, 300)
		reserve = self._reserve(owner, 25)
		api.consume_reserved_credits(reserve["reservation"])
		status = frappe.db.get_value("Credit Reservation", reserve["reservation"], "status")
		self.assertEqual(status, "Consumed")

	def test_13_partial_consume_releases_remainder_automatically(self):
		owner = self._owner("consume-partial")
		self._fund(owner, 1000)
		reserve = self._reserve(owner, 100)
		api.consume_reserved_credits(reserve["reservation"], actual_amount=70)
		reservation = frappe.get_doc("Credit Reservation", reserve["reservation"])
		self.assertEqual(reservation.consumed_amount, 70)
		self.assertEqual(reservation.released_amount, 30)
		self.assertEqual(reservation.status, "Consumed")
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["current_balance"], 930)
		self.assertEqual(balance["reserved_balance"], 0)
		self.assertEqual(balance["available_balance"], 930)

	def test_14_partial_consume_creates_both_ledger_entries(self):
		owner = self._owner("consume-partial-ledger")
		self._fund(owner, 1000)
		reserve = self._reserve(owner, 100)
		key = f"job:{self._suffix}:consume-partial"
		result = api.consume_reserved_credits(
			reserve["reservation"],
			actual_amount=70,
			idempotency_key=key,
		)
		self.assertTrue(result["consume_ledger_entry"])
		self.assertTrue(result["release_ledger_entry"])
		consume = frappe.get_doc("Credit Ledger Entry", result["consume_ledger_entry"])
		release = frappe.get_doc("Credit Ledger Entry", result["release_ledger_entry"])
		self.assertEqual(consume.entry_type, "CONSUME_RESERVE")
		self.assertEqual(consume.amount, 70)
		self.assertEqual(release.entry_type, "RELEASE_RESERVE")
		self.assertEqual(release.amount, 30)

	def test_15_release_restores_available_balance(self):
		owner = self._owner("release-avail")
		self._fund(owner, 500)
		reserve = self._reserve(owner, 80)
		api.release_reservation(reserve["reservation"], reason="provider error")
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["available_balance"], 500)
		self.assertEqual(balance["reserved_balance"], 0)

	def test_16_release_creates_release_reserve_ledger_entry(self):
		owner = self._owner("release-ledger")
		self._fund(owner, 500)
		reserve = self._reserve(owner, 80)
		key = f"job:{self._suffix}:release"
		result = api.release_reservation(
			reserve["reservation"],
			reason="provider error",
			idempotency_key=key,
		)
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
		self.assertEqual(entry.entry_type, "RELEASE_RESERVE")
		self.assertEqual(entry.amount, 80)

	def test_17_duplicate_consume_idempotency(self):
		owner = self._owner("consume-idempotent")
		self._fund(owner, 500)
		reserve = self._reserve(owner, 50)
		key = f"job:{self._suffix}:consume-dup"
		first = api.consume_reserved_credits(reserve["reservation"], idempotency_key=key)
		second = api.consume_reserved_credits(reserve["reservation"], idempotency_key=key)
		self.assertTrue(second["idempotent_replay"])
		self.assertEqual(first["consume_ledger_entry"], second["consume_ledger_entry"])
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["current_balance"], 450)

	def test_18_duplicate_release_idempotency(self):
		owner = self._owner("release-idempotent")
		self._fund(owner, 500)
		reserve = self._reserve(owner, 50)
		key = f"job:{self._suffix}:release-dup"
		first = api.release_reservation(reserve["reservation"], idempotency_key=key)
		second = api.release_reservation(reserve["reservation"], idempotency_key=key)
		self.assertTrue(second["idempotent_replay"])
		self.assertEqual(first["ledger_entry"], second["ledger_entry"])
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["reserved_balance"], 0)

	def test_19_cannot_consume_released_reservation(self):
		owner = self._owner("consume-released")
		self._fund(owner, 500)
		reserve = self._reserve(owner, 50)
		api.release_reservation(reserve["reservation"])
		with self.assertRaises(CreditReservationError):
			api.consume_reserved_credits(reserve["reservation"])

	def test_20_cannot_release_consumed_reservation(self):
		owner = self._owner("release-consumed")
		self._fund(owner, 500)
		reserve = self._reserve(owner, 50)
		api.consume_reserved_credits(reserve["reservation"])
		with self.assertRaises(CreditReservationError):
			api.release_reservation(reserve["reservation"])

	def test_21_expired_scheduler_releases_reservation(self):
		owner = self._owner("expire-scheduler")
		self._fund(owner, 500)
		past = add_to_date(now_datetime(), minutes=-5)
		result = self._reserve(owner, 60, expires_at=past)
		task_result = tasks.release_expired_reservations()
		self.assertGreaterEqual(task_result["released"], 1)
		reservation = frappe.get_doc("Credit Reservation", result["reservation"])
		self.assertEqual(reservation.status, "Expired")
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["reserved_balance"], 0)
		self.assertEqual(balance["available_balance"], 500)

	def test_22_expired_scheduler_is_idempotent(self):
		owner = self._owner("expire-idempotent")
		self._fund(owner, 500)
		past = add_to_date(now_datetime(), minutes=-5)
		result = self._reserve(owner, 40, expires_at=past)
		first = tasks.release_expired_reservations()
		second = tasks.release_expired_reservations()
		self.assertGreaterEqual(first["released"], 1)
		self.assertEqual(second["released"], 0)
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["reserved_balance"], 0)
		expire_key = f"reservation:{result['reservation']}:expire"
		self.assertEqual(
			frappe.db.count(
				"Credit Ledger Entry",
				{
					"idempotency_key": expire_key,
					"entry_type": "RELEASE_RESERVE",
					"docstatus": 1,
				},
			),
			1,
		)

	def test_23_video_generation_success_flow(self):
		owner = self._owner("video-success")
		job_id = f"VID-{self._suffix}"
		self._fund(owner, 1000)
		reserve = api.reserve_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			70,
			reference_name=job_id,
			idempotency_key=f"video-job:{job_id}:reserve",
			source_app="dummy_website",
		)
		consume = api.consume_reserved_credits(
			reserve["reservation"],
			actual_amount=70,
			idempotency_key=f"video-job:{job_id}:consume-reserved",
			source_app="dummy_website",
		)
		self.assertEqual(consume["status"], "Consumed")
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["current_balance"], 930)
		self.assertEqual(balance["reserved_balance"], 0)
		self.assertEqual(balance["available_balance"], 930)

	def test_24_video_generation_failure_flow(self):
		owner = self._owner("video-failure")
		job_id = f"VID-{self._suffix}"
		self._fund(owner, 1000)
		reserve = api.reserve_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			70,
			reference_name=job_id,
			idempotency_key=f"video-job:{job_id}:reserve",
			source_app="dummy_website",
		)
		release = api.release_reservation(
			reserve["reservation"],
			reason="provider error",
			idempotency_key=f"video-job:{job_id}:release",
		)
		self.assertEqual(release["status"], "Released")
		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["current_balance"], 1000)
		self.assertEqual(balance["reserved_balance"], 0)
		self.assertEqual(balance["available_balance"], 1000)

	def test_25_retry_duplicate_callbacks_do_not_double_charge(self):
		owner = self._owner("video-retry")
		job_id = f"VID-{self._suffix}"
		self._fund(owner, 1000)
		reserve_key = f"video-job:{job_id}:reserve"
		consume_key = f"video-job:{job_id}:consume-reserved"
		release_key = f"video-job:{job_id}:release"

		reserve_first = api.reserve_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			70,
			idempotency_key=reserve_key,
		)
		reserve_retry = api.reserve_credits(
			self.owner_doctype,
			owner,
			self.credit_type,
			70,
			idempotency_key=reserve_key,
		)
		self.assertTrue(reserve_retry["idempotent_replay"])

		consume_first = api.consume_reserved_credits(
			reserve_first["reservation"],
			actual_amount=70,
			idempotency_key=consume_key,
		)
		consume_retry = api.consume_reserved_credits(
			reserve_first["reservation"],
			actual_amount=70,
			idempotency_key=consume_key,
		)
		self.assertTrue(consume_retry["idempotent_replay"])
		self.assertEqual(consume_first["consume_ledger_entry"], consume_retry["consume_ledger_entry"])

		balance = api.get_balance(self.owner_doctype, owner, self.credit_type)
		self.assertEqual(balance["current_balance"], 930)

		# Release retries on consumed reservation should fail, not alter balances.
		with self.assertRaises(CreditReservationError):
			api.release_reservation(
				reserve_first["reservation"],
				idempotency_key=release_key,
			)