# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Expiry lot FIFO consumption and scheduled expiry."""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from credit_management.services.account_service import AccountService
from credit_management.services.ledger_service import LedgerService

LOT_STATUS_ACTIVE = "Active"
LOT_STATUS_EXHAUSTED = "Exhausted"
LOT_STATUS_EXPIRED = "Expired"


class ExpiryService:
	@staticmethod
	def is_expiry_enabled():
		return bool(frappe.get_single("Credit Settings").enable_credit_expiry)

	@staticmethod
	def normalize_expires_on(expires_on):
		if not expires_on:
			return None
		return getdate(expires_on)

	@staticmethod
	def find_grant_by_idempotency_key(idempotency_key):
		if not idempotency_key:
			return None
		name = frappe.db.get_value("Credit Grant", {"idempotency_key": idempotency_key})
		return frappe.get_doc("Credit Grant", name) if name else None

	@staticmethod
	def lock_lot(lot_name):
		return frappe.get_doc("Credit Expiry Lot", lot_name, for_update=True)

	@staticmethod
	def lot_available_amount(lot):
		return flt(lot.remaining_amount) - flt(lot.reserved_amount)

	@staticmethod
	def allocation_remaining(allocation):
		return (
			flt(allocation.reserved_amount)
			- flt(allocation.consumed_amount)
			- flt(allocation.released_amount)
		)

	@staticmethod
	def get_active_lots(account_name, credit_type=None):
		filters = {"credit_account": account_name, "status": LOT_STATUS_ACTIVE}
		if credit_type:
			filters["credit_type"] = credit_type

		return frappe.get_all(
			"Credit Expiry Lot",
			filters=filters,
			fields=[
				"name",
				"remaining_amount",
				"reserved_amount",
				"consumed_amount",
				"expired_amount",
				"expires_on",
				"status",
			],
			order_by="expires_on asc, creation asc",
		)

	@staticmethod
	def update_lot(lot, **values):
		lot = frappe.get_doc(lot) if isinstance(lot, str) else lot
		if values:
			frappe.db.set_value("Credit Expiry Lot", lot.name, values, update_modified=True)
			lot.reload()
		return lot

	@staticmethod
	def refresh_lot_status(lot):
		lot = ExpiryService.lock_lot(lot.name if hasattr(lot, "name") else lot)
		if lot.status == LOT_STATUS_EXPIRED:
			return lot

		if flt(lot.remaining_amount) <= 0:
			lot = ExpiryService.update_lot(lot, status=LOT_STATUS_EXHAUSTED)
		return lot

	@staticmethod
	def create_expiry_lot_for_grant(grant_doc, account, amount, expires_on):
		expires_on = ExpiryService.normalize_expires_on(expires_on)
		amount = AccountService.round_amount(amount, account.credit_type)

		lot = frappe.get_doc(
			{
				"doctype": "Credit Expiry Lot",
				"credit_account": account.name,
				"credit_type": account.credit_type,
				"original_amount": amount,
				"remaining_amount": amount,
				"reserved_amount": 0,
				"consumed_amount": 0,
				"expired_amount": 0,
				"expires_on": expires_on,
				"source_grant": grant_doc.name,
				"status": LOT_STATUS_ACTIVE,
			}
		)
		lot.insert(ignore_permissions=True)
		return lot

	@staticmethod
	def create_credit_grant(
		account,
		amount,
		entry,
		*,
		expires_on=None,
		reference_doctype=None,
		reference_name=None,
		idempotency_key=None,
		source_app=None,
		metadata=None,
	):
		grant = frappe.get_doc(
			{
				"doctype": "Credit Grant",
				"credit_account": account.name,
				"credit_type": account.credit_type,
				"amount": amount,
				"valid_from": today(),
				"expires_on": ExpiryService.normalize_expires_on(expires_on),
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"source_app": source_app,
				"idempotency_key": idempotency_key,
				"metadata_json": AccountService.serialize_metadata(metadata),
				"ledger_entry": entry.name,
				"status": "Granted",
			}
		)
		grant.flags.ignore_links = True
		grant.insert(ignore_permissions=True)
		return grant

	@staticmethod
	def consume_from_expiry_lots(account, amount):
		amount = AccountService.round_amount(amount, account.credit_type)
		remaining = amount
		lot_updates = []

		for lot_row in ExpiryService.get_active_lots(account.name, account.credit_type):
			if remaining <= 0:
				break

			lot = ExpiryService.lock_lot(lot_row.name)
			available = ExpiryService.lot_available_amount(lot)
			if available <= 0:
				continue

			take = min(remaining, available)
			take = AccountService.round_amount(take, account.credit_type)
			if take <= 0:
				continue

			new_remaining = flt(lot.remaining_amount) - take
			new_consumed = flt(lot.consumed_amount) + take
			lot = ExpiryService.update_lot(
				lot,
				remaining_amount=new_remaining,
				consumed_amount=new_consumed,
			)
			lot = ExpiryService.refresh_lot_status(lot)
			lot_updates.append({"lot": lot.name, "amount": take})
			remaining -= take

		non_expiring_amount = AccountService.round_amount(remaining, account.credit_type)
		return lot_updates, non_expiring_amount

	@staticmethod
	def reserve_from_expiry_lots(account, amount):
		amount = AccountService.round_amount(amount, account.credit_type)
		remaining = amount
		allocations = []

		for lot_row in ExpiryService.get_active_lots(account.name, account.credit_type):
			if remaining <= 0:
				break

			lot = ExpiryService.lock_lot(lot_row.name)
			available = ExpiryService.lot_available_amount(lot)
			if available <= 0:
				continue

			take = min(remaining, available)
			take = AccountService.round_amount(take, account.credit_type)
			if take <= 0:
				continue

			new_reserved = flt(lot.reserved_amount) + take
			ExpiryService.update_lot(lot, reserved_amount=new_reserved)
			allocations.append({"expiry_lot": lot.name, "reserved_amount": take})
			remaining -= take

		non_expiring_amount = AccountService.round_amount(remaining, account.credit_type)
		return allocations, non_expiring_amount

	@staticmethod
	def save_reservation_allocations(reservation, allocations):
		if not allocations:
			return reservation

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

		reservation.save(ignore_permissions=True)
		return reservation

	@staticmethod
	def consume_reserved_from_expiry_lots(reservation, actual_amount):
		actual_amount = AccountService.round_amount(actual_amount, reservation.credit_type)
		remaining = actual_amount

		for allocation in reservation.expiry_lot_allocations:
			if remaining <= 0:
				break

			allocation_remaining = ExpiryService.allocation_remaining(allocation)
			if allocation_remaining <= 0:
				continue

			take = min(remaining, allocation_remaining)
			take = AccountService.round_amount(take, reservation.credit_type)
			if take <= 0:
				continue

			lot = ExpiryService.lock_lot(allocation.expiry_lot)
			new_reserved = flt(lot.reserved_amount) - take
			new_remaining = flt(lot.remaining_amount) - take
			new_consumed = flt(lot.consumed_amount) + take
			lot = ExpiryService.update_lot(
				lot,
				reserved_amount=new_reserved,
				remaining_amount=new_remaining,
				consumed_amount=new_consumed,
			)
			ExpiryService.refresh_lot_status(lot)

			allocation.consumed_amount = flt(allocation.consumed_amount) + take
			remaining -= take

		reservation.flags.ignore_links = True
		reservation.save(ignore_permissions=True)
		return reservation

	@staticmethod
	def release_reserved_expiry_lots(reservation, release_amount, account):
		release_amount = AccountService.round_amount(release_amount, reservation.credit_type)
		remaining = release_amount

		for allocation in reservation.expiry_lot_allocations:
			if remaining <= 0:
				break

			allocation_remaining = ExpiryService.allocation_remaining(allocation)
			if allocation_remaining <= 0:
				continue

			take = min(remaining, allocation_remaining)
			take = AccountService.round_amount(take, reservation.credit_type)
			if take <= 0:
				continue

			lot = ExpiryService.lock_lot(allocation.expiry_lot)
			new_reserved = flt(lot.reserved_amount) - take
			ExpiryService.update_lot(lot, reserved_amount=new_reserved)

			allocation.released_amount = flt(allocation.released_amount) + take
			remaining -= take

			if getdate(lot.expires_on) < getdate(today()):
				ExpiryService.expire_lot_amount(
					lot,
					account,
					take,
					idempotency_key=f"expiry-lot:{lot.name}:release-expire:{reservation.name}",
					reference_doctype="Credit Reservation",
					reference_name=reservation.name,
					remarks="Expired released credits from past-expiry lot",
				)

		reservation.flags.ignore_links = True
		reservation.save(ignore_permissions=True)
		return reservation

	@staticmethod
	def release_all_reserved_allocations(reservation, account):
		total = 0
		for allocation in reservation.expiry_lot_allocations:
			allocation_remaining = ExpiryService.allocation_remaining(allocation)
			if allocation_remaining > 0:
				total += allocation_remaining

		if total > 0:
			ExpiryService.release_reserved_expiry_lots(reservation, total, account)
		return reservation

	@staticmethod
	def expire_lot_amount(
		lot,
		account,
		amount,
		*,
		idempotency_key=None,
		reference_doctype=None,
		reference_name=None,
		source_app=None,
		remarks=None,
	):
		amount = AccountService.round_amount(amount, account.credit_type)
		if amount <= 0:
			return None

		if idempotency_key:
			existing = LedgerService.find_by_idempotency_key(idempotency_key, entry_type="EXPIRE")
			if existing:
				return existing

		lot = ExpiryService.lock_lot(lot.name if hasattr(lot, "name") else lot)
		expirable = ExpiryService.lot_available_amount(lot)
		amount = min(amount, expirable)
		if amount <= 0:
			return None

		new_remaining = flt(lot.remaining_amount) - amount
		new_expired = flt(lot.expired_amount) + amount
		new_current = flt(account.current_balance) - amount

		account = AccountService.update_balances(
			account,
			current_balance=new_current,
			lifetime_expired_delta=amount,
		)

		lot = ExpiryService.update_lot(
			lot,
			remaining_amount=new_remaining,
			expired_amount=new_expired,
		)

		if flt(lot.remaining_amount) <= 0 and flt(lot.reserved_amount) <= 0:
			lot = ExpiryService.update_lot(lot, status=LOT_STATUS_EXPIRED)
		else:
			ExpiryService.refresh_lot_status(lot)

		entry = LedgerService.create_and_submit_entry(
			account,
			"EXPIRE",
			amount,
			reference_doctype=reference_doctype or "Credit Expiry Lot",
			reference_name=reference_name or lot.name,
			source_app=source_app or "credit_management",
			idempotency_key=idempotency_key,
			remarks=remarks,
		)
		return entry

	@staticmethod
	def expire_credits():
		current_date = today()
		lots = frappe.get_all(
			"Credit Expiry Lot",
			filters={"status": LOT_STATUS_ACTIVE, "expires_on": ("<", current_date)},
			fields=["name", "credit_account"],
		)

		expired_count = 0
		skipped = 0
		errors = []

		for row in lots:
			try:
				expire_key = f"expiry-lot:{row.name}:expire"
				if LedgerService.find_by_idempotency_key(expire_key, entry_type="EXPIRE"):
					skipped += 1
					continue

				lot = ExpiryService.lock_lot(row.name)
				expirable = ExpiryService.lot_available_amount(lot)
				if expirable <= 0:
					if flt(lot.remaining_amount) <= 0 and flt(lot.reserved_amount) <= 0:
						ExpiryService.update_lot(lot, status=LOT_STATUS_EXPIRED)
					skipped += 1
					continue

				account = AccountService.lock_account(lot.credit_account)
				entry = ExpiryService.expire_lot_amount(
					lot,
					account,
					expirable,
					idempotency_key=expire_key,
					reference_doctype="Credit Expiry Lot",
					reference_name=lot.name,
					remarks="Scheduled credit expiry",
				)
				if entry:
					expired_count += 1
				else:
					skipped += 1
			except Exception as exc:
				errors.append({"lot": row.name, "error": str(exc)})

		return {
			"status": "completed",
			"expired": expired_count,
			"skipped": skipped,
			"errors": errors,
		}