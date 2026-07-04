# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Credit reservation lifecycle for async workloads."""

import frappe
from frappe import _
from frappe.utils import add_to_date, flt, now_datetime

from credit_management.exceptions import (
	CreditReservationError,
	InvalidCreditAmountError,
)
from credit_management.services.account_service import AccountService
from credit_management.services.expiry_service import ExpiryService
from credit_management.services.ledger_service import LedgerService

ACTIVE_RESERVATION_STATUSES = ("Active", "Partially Consumed")
TERMINAL_RESERVATION_STATUSES = ("Consumed", "Released", "Expired", "Cancelled")


class ReservationService:
	DEFAULT_TIMEOUT_MINUTES = 60

	@staticmethod
	def get_default_expires_at():
		settings = frappe.get_single("Credit Settings")
		minutes = int(settings.default_reservation_timeout_minutes or 0)
		if minutes <= 0:
			minutes = ReservationService.DEFAULT_TIMEOUT_MINUTES
		return add_to_date(now_datetime(), minutes=minutes)

	@staticmethod
	def remaining_amount(reservation):
		return flt(reservation.reserved_amount) - flt(reservation.consumed_amount) - flt(
			reservation.released_amount
		)

	@staticmethod
	def find_reservation_by_idempotency_key(idempotency_key):
		if not idempotency_key:
			return None

		name = frappe.db.get_value("Credit Reservation", {"idempotency_key": idempotency_key})
		if not name:
			return None

		return frappe.get_doc("Credit Reservation", name)

	@staticmethod
	def lock_reservation(reservation_name):
		return frappe.get_doc("Credit Reservation", reservation_name, for_update=True)

	@staticmethod
	def update_reservation(
		reservation,
		*,
		consumed_amount=None,
		released_amount=None,
		status=None,
		failure_reason=None,
	):
		reservation = frappe.get_doc(reservation) if isinstance(reservation, str) else reservation
		values = {}

		if consumed_amount is not None:
			values["consumed_amount"] = flt(consumed_amount)
		if released_amount is not None:
			values["released_amount"] = flt(released_amount)
		if status is not None:
			values["status"] = status
		if failure_reason is not None:
			values["failure_reason"] = failure_reason

		if values:
			frappe.db.set_value("Credit Reservation", reservation.name, values, update_modified=True)
			reservation.reload()

		return reservation

	@staticmethod
	def resolve_release_status(reason=None, expired=False):
		if expired:
			return "Expired"
		if reason and "cancel" in reason.lower():
			return "Cancelled"
		return "Released"

	@staticmethod
	def build_reserve_result(reservation, account, ledger_entry, idempotent_replay=False):
		return {
			"credit_account": account.name,
			"credit_type": account.credit_type,
			"reservation": reservation.name,
			"ledger_entry": ledger_entry.name if ledger_entry else None,
			"reserved_amount": flt(reservation.reserved_amount),
			"consumed_amount": flt(reservation.consumed_amount),
			"released_amount": flt(reservation.released_amount),
			"status": reservation.status,
			"current_balance": flt(account.current_balance),
			"reserved_balance": flt(account.reserved_balance),
			"available_balance": flt(account.available_balance),
			"idempotent_replay": idempotent_replay,
		}

	@staticmethod
	def build_consume_result(
		reservation,
		account,
		consume_entry,
		release_entry=None,
		idempotent_replay=False,
	):
		result = ReservationService.build_reserve_result(
			reservation, account, consume_entry, idempotent_replay=idempotent_replay
		)
		result["consume_ledger_entry"] = consume_entry.name if consume_entry else None
		result["release_ledger_entry"] = release_entry.name if release_entry else None
		result["consumed_amount"] = flt(reservation.consumed_amount)
		result["released_amount"] = flt(reservation.released_amount)
		result["status"] = reservation.status
		return result

	@staticmethod
	def build_release_result(reservation, account, ledger_entry, idempotent_replay=False):
		result = ReservationService.build_reserve_result(
			reservation, account, ledger_entry, idempotent_replay=idempotent_replay
		)
		result["released_amount"] = flt(reservation.released_amount)
		result["status"] = reservation.status
		if reservation.failure_reason:
			result["failure_reason"] = reservation.failure_reason
		return result

	@staticmethod
	def _validate_reservation_mutable(reservation, operation):
		if reservation.status not in ACTIVE_RESERVATION_STATUSES:
			frappe.throw(
				_("Reservation {0} is {1} and cannot be {2}").format(
					reservation.name,
					reservation.status,
					operation,
				),
				CreditReservationError,
			)

		if ReservationService.remaining_amount(reservation) <= 0:
			frappe.throw(
				_("Reservation {0} has no remaining reserved amount").format(reservation.name),
				CreditReservationError,
			)

	@staticmethod
	def reserve_credits(
		owner_doctype,
		owner_name,
		credit_type,
		amount,
		reference_doctype=None,
		reference_name=None,
		expires_at=None,
		idempotency_key=None,
		source_app=None,
		metadata=None,
		company=None,
	):
		amount = flt(amount)
		if amount <= 0:
			frappe.throw(_("Reserve amount must be positive"), InvalidCreditAmountError)

		if idempotency_key:
			existing = ReservationService.find_reservation_by_idempotency_key(idempotency_key)
			if existing:
				account = AccountService.lock_account(existing.credit_account)
				ledger_entry = LedgerService.find_by_idempotency_key(idempotency_key, entry_type="RESERVE")
				return ReservationService.build_reserve_result(
					existing, account, ledger_entry, idempotent_replay=True
				)

		account_doc = AccountService.get_or_create_account(
			owner_doctype, owner_name, credit_type, company
		)
		account = AccountService.lock_account(account_doc.name)
		AccountService.validate_account_can_reserve(account)

		amount = AccountService.round_amount(amount, account.credit_type)
		AccountService.validate_sufficient_balance(account, amount)

		new_reserved = flt(account.reserved_balance) + amount
		account = AccountService.update_balances(account, reserved_balance=new_reserved)

		if not expires_at:
			expires_at = ReservationService.get_default_expires_at()

		reservation = frappe.get_doc(
			{
				"doctype": "Credit Reservation",
				"credit_account": account.name,
				"credit_type": account.credit_type,
				"reserved_amount": amount,
				"consumed_amount": 0,
				"released_amount": 0,
				"status": "Active",
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"source_app": source_app,
				"expires_at": expires_at,
				"idempotency_key": idempotency_key,
				"metadata_json": AccountService.serialize_metadata(metadata),
			}
		)
		reservation.flags.ignore_links = True
		allocations, _non_expiring = ExpiryService.reserve_from_expiry_lots(account, amount)
		for row in allocations:
			reservation.append(
				"expiry_lot_allocations",
				{
					"expiry_lot": row["expiry_lot"],
					"reserved_amount": row["reserved_amount"],
					"consumed_amount": 0,
					"released_amount": 0,
				},
			)

		try:
			reservation.insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			if idempotency_key:
				existing = ReservationService.find_reservation_by_idempotency_key(idempotency_key)
				if existing:
					account = AccountService.lock_account(existing.credit_account)
					ledger_entry = LedgerService.find_by_idempotency_key(
						idempotency_key, entry_type="RESERVE"
					)
					return ReservationService.build_reserve_result(
						existing, account, ledger_entry, idempotent_replay=True
					)
			raise

		ledger_entry = LedgerService.create_and_submit_entry(
			account,
			"RESERVE",
			amount,
			reference_doctype="Credit Reservation",
			reference_name=reservation.name,
			source_app=source_app,
			idempotency_key=idempotency_key,
			metadata=metadata,
		)

		return ReservationService.build_reserve_result(reservation, account, ledger_entry)

	@staticmethod
	def consume_reserved_credits(
		reservation_name,
		actual_amount=None,
		idempotency_key=None,
		source_app=None,
		metadata=None,
	):
		if not reservation_name or not frappe.db.exists("Credit Reservation", reservation_name):
			frappe.throw(_("Credit Reservation {0} does not exist").format(reservation_name))

		if idempotency_key:
			existing_entry = LedgerService.find_by_idempotency_key(
				idempotency_key, entry_type="CONSUME_RESERVE"
			)
			if existing_entry:
				reservation = frappe.get_doc("Credit Reservation", reservation_name)
				account = AccountService.lock_account(reservation.credit_account)
				release_entry = LedgerService.find_by_idempotency_key(
					f"{idempotency_key}:auto-release", entry_type="RELEASE_RESERVE"
				)
				return ReservationService.build_consume_result(
					reservation,
					account,
					existing_entry,
					release_entry=release_entry,
					idempotent_replay=True,
				)

		reservation = ReservationService.lock_reservation(reservation_name)
		account = AccountService.lock_account(reservation.credit_account)
		ReservationService._validate_reservation_mutable(reservation, "consumed")

		remaining = ReservationService.remaining_amount(reservation)
		if actual_amount is None:
			actual_amount = remaining

		actual_amount = AccountService.round_amount(actual_amount, reservation.credit_type)
		if actual_amount <= 0:
			frappe.throw(_("Consume amount must be positive"), InvalidCreditAmountError)

		if actual_amount > remaining:
			frappe.throw(
				_("Consume amount cannot exceed remaining reserved amount"),
				InvalidCreditAmountError,
			)

		remainder = flt(remaining - actual_amount)

		ExpiryService.consume_reserved_from_expiry_lots(reservation, actual_amount)
		lot_release = sum(
			ExpiryService.allocation_remaining(row)
			for row in reservation.expiry_lot_allocations
		)
		if lot_release > 0:
			ExpiryService.release_reserved_expiry_lots(reservation, lot_release, account)

		new_current = flt(account.current_balance) - actual_amount
		new_reserved = flt(account.reserved_balance) - remaining

		account = AccountService.update_balances(
			account,
			current_balance=new_current,
			reserved_balance=new_reserved,
			lifetime_consumed_delta=actual_amount,
		)

		consume_entry = LedgerService.create_and_submit_entry(
			account,
			"CONSUME_RESERVE",
			actual_amount,
			reference_doctype="Credit Reservation",
			reference_name=reservation.name,
			source_app=source_app,
			idempotency_key=idempotency_key,
			metadata=metadata,
		)

		release_entry = None
		if remainder > 0:
			release_entry = LedgerService.create_and_submit_entry(
				account,
				"RELEASE_RESERVE",
				remainder,
				reference_doctype="Credit Reservation",
				reference_name=reservation.name,
				source_app=source_app,
				idempotency_key=f"{idempotency_key}:auto-release" if idempotency_key else None,
				remarks="Automatic release of unused reserved amount",
				metadata=metadata,
			)

		reservation = ReservationService.update_reservation(
			reservation,
			consumed_amount=flt(reservation.consumed_amount) + actual_amount,
			released_amount=flt(reservation.released_amount) + remainder,
			status="Consumed",
		)

		return ReservationService.build_consume_result(
			reservation, account, consume_entry, release_entry=release_entry
		)

	@staticmethod
	def release_reservation(
		reservation_name,
		reason=None,
		idempotency_key=None,
		*,
		expired=False,
		source_app=None,
		metadata=None,
	):
		if not reservation_name or not frappe.db.exists("Credit Reservation", reservation_name):
			frappe.throw(_("Credit Reservation {0} does not exist").format(reservation_name))

		if idempotency_key:
			existing_entry = LedgerService.find_by_idempotency_key(
				idempotency_key, entry_type="RELEASE_RESERVE"
			)
			if existing_entry:
				reservation = frappe.get_doc("Credit Reservation", reservation_name)
				account = AccountService.lock_account(reservation.credit_account)
				return ReservationService.build_release_result(
					reservation, account, existing_entry, idempotent_replay=True
				)

		reservation = ReservationService.lock_reservation(reservation_name)
		account = AccountService.lock_account(reservation.credit_account)
		ReservationService._validate_reservation_mutable(reservation, "released")

		release_amount = ReservationService.remaining_amount(reservation)
		release_amount = AccountService.round_amount(release_amount, reservation.credit_type)

		if release_amount <= 0:
			frappe.throw(
				_("Reservation {0} has no remaining amount to release").format(reservation.name),
				CreditReservationError,
			)

		ExpiryService.release_reserved_expiry_lots(reservation, release_amount, account)

		new_reserved = flt(account.reserved_balance) - release_amount
		account = AccountService.update_balances(account, reserved_balance=new_reserved)

		ledger_entry = LedgerService.create_and_submit_entry(
			account,
			"RELEASE_RESERVE",
			release_amount,
			reference_doctype="Credit Reservation",
			reference_name=reservation.name,
			source_app=source_app,
			idempotency_key=idempotency_key,
			remarks=reason,
			metadata=metadata,
		)

		status = ReservationService.resolve_release_status(reason=reason, expired=expired)
		reservation = ReservationService.update_reservation(
			reservation,
			released_amount=flt(reservation.released_amount) + release_amount,
			status=status,
			failure_reason=reason,
		)

		return ReservationService.build_release_result(reservation, account, ledger_entry)

	@staticmethod
	def release_expired_reservations():
		now = now_datetime()
		expired_reservations = frappe.get_all(
			"Credit Reservation",
			filters={
				"status": ("in", list(ACTIVE_RESERVATION_STATUSES)),
				"expires_at": ("<", now),
			},
			fields=["name"],
		)

		released = 0
		skipped = 0
		errors = []

		for row in expired_reservations:
			try:
				expire_key = f"reservation:{row.name}:expire"
				if LedgerService.find_by_idempotency_key(expire_key, entry_type="RELEASE_RESERVE"):
					skipped += 1
					continue

				ReservationService.release_reservation(
					row.name,
					reason="Reservation expired",
					idempotency_key=expire_key,
					expired=True,
					source_app="credit_management",
				)
				released += 1
			except CreditReservationError:
				skipped += 1
			except Exception as exc:
				errors.append({"reservation": row.name, "error": str(exc)})

		return {
			"status": "completed",
			"released": released,
			"skipped": skipped,
			"errors": errors,
		}