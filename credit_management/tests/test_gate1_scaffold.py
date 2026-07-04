# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import unittest

import credit_management.api as api
from credit_management.exceptions import (
	CreditAccountSuspendedError,
	CreditManagementError,
	CreditReconciliationError,
	CreditReservationError,
	DuplicateCreditOperationError,
	InsufficientCreditError,
	InvalidCreditAmountError,
)


class TestGate1Scaffold(unittest.TestCase):
	def test_public_api_exports(self):
		expected = {
			"get_or_create_account",
			"get_balance",
			"grant_credits",
			"consume_credits",
			"reserve_credits",
			"consume_reserved_credits",
			"release_reservation",
			"refund_credits",
			"adjust_credits",
			"transfer_credits",
			"expire_credits",
			"reconcile_account",
			"reconcile_all_accounts",
		}
		self.assertTrue(expected.issubset(set(api.__all__)))

	def test_gate8_plus_scheduler_stubs_remain(self):
		from credit_management import tasks

		self.assertEqual(tasks.generate_daily_credit_summary()["status"], "stub")
		self.assertEqual(tasks.retry_failed_webhooks()["status"], "stub")

	def test_expire_credits_public_api(self):
		result = api.expire_credits()
		self.assertEqual(result["status"], "completed")

	def test_exception_hierarchy(self):
		self.assertTrue(issubclass(InsufficientCreditError, CreditManagementError))
		self.assertTrue(issubclass(InvalidCreditAmountError, CreditManagementError))
		self.assertTrue(issubclass(CreditAccountSuspendedError, CreditManagementError))
		self.assertTrue(issubclass(CreditReservationError, CreditManagementError))
		self.assertTrue(issubclass(DuplicateCreditOperationError, CreditManagementError))
		self.assertTrue(issubclass(CreditReconciliationError, CreditManagementError))

	def test_service_modules_importable(self):
		from credit_management.services.account_service import AccountService
		from credit_management.services.ledger_service import LedgerService
		from credit_management.services.reservation_service import ReservationService

		self.assertTrue(callable(AccountService))
		self.assertTrue(callable(LedgerService))
		self.assertTrue(callable(ReservationService))

	def test_scheduler_tasks_importable(self):
		from credit_management import tasks

		self.assertTrue(hasattr(tasks, "release_expired_reservations"))
		self.assertEqual(tasks.release_expired_reservations()["status"], "completed")

		self.assertEqual(tasks.expire_credits()["status"], "completed")

		self.assertEqual(tasks.reconcile_recent_accounts()["status"], "completed")

		for name in ("generate_daily_credit_summary", "retry_failed_webhooks"):
			self.assertTrue(hasattr(tasks, name))
			self.assertEqual(tasks.__dict__[name]()["status"], "stub")