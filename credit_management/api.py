# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""
Stable public integration surface for consuming Frappe apps.

All balance-changing operations must go through this module.
Do not mutate Credit Account balances or ledger rows from outside services.
"""

_NOT_IMPLEMENTED = "Not implemented — available from Gate 7 onward."

from credit_management.services.account_service import AccountService
from credit_management.services.adjustment_service import AdjustmentService
from credit_management.services.consume_service import ConsumeService
from credit_management.services.expiry_service import ExpiryService
from credit_management.services.grant_service import GrantService
from credit_management.services.refund_service import RefundService
from credit_management.services.reservation_service import ReservationService
from credit_management.services.transfer_service import TransferService


def get_or_create_account(owner_doctype, owner_name, credit_type, company=None):
	account = AccountService.get_or_create_account(
		owner_doctype, owner_name, credit_type, company
	)
	return account.name


def get_balance(owner_doctype, owner_name, credit_type, company=None):
	return AccountService.get_balance(owner_doctype, owner_name, credit_type, company)


def grant_credits(
	owner_doctype,
	owner_name,
	credit_type,
	amount,
	reference_doctype=None,
	reference_name=None,
	expires_on=None,
	idempotency_key=None,
	source_app=None,
	metadata=None,
):
	return GrantService.grant_credits(
		owner_doctype,
		owner_name,
		credit_type,
		amount,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		expires_on=expires_on,
		idempotency_key=idempotency_key,
		source_app=source_app,
		metadata=metadata,
	)


def consume_credits(
	owner_doctype,
	owner_name,
	credit_type,
	amount,
	reference_doctype=None,
	reference_name=None,
	idempotency_key=None,
	source_app=None,
	metadata=None,
):
	return ConsumeService.consume_credits(
		owner_doctype,
		owner_name,
		credit_type,
		amount,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		idempotency_key=idempotency_key,
		source_app=source_app,
		metadata=metadata,
	)


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
):
	return ReservationService.reserve_credits(
		owner_doctype=owner_doctype,
		owner_name=owner_name,
		credit_type=credit_type,
		amount=amount,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		expires_at=expires_at,
		idempotency_key=idempotency_key,
		source_app=source_app,
		metadata=metadata,
	)


def consume_reserved_credits(
	reservation_name,
	actual_amount=None,
	idempotency_key=None,
	source_app=None,
	metadata=None,
):
	return ReservationService.consume_reserved_credits(
		reservation_name=reservation_name,
		actual_amount=actual_amount,
		idempotency_key=idempotency_key,
		source_app=source_app,
		metadata=metadata,
	)


def release_reservation(reservation_name, reason=None, idempotency_key=None):
	return ReservationService.release_reservation(
		reservation_name=reservation_name,
		reason=reason,
		idempotency_key=idempotency_key,
	)


def refund_credits(
	owner_doctype,
	owner_name,
	credit_type,
	amount,
	reference_doctype=None,
	reference_name=None,
	idempotency_key=None,
	source_app=None,
	metadata=None,
):
	return RefundService.refund_credits(
		owner_doctype,
		owner_name,
		credit_type,
		amount,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		idempotency_key=idempotency_key,
		source_app=source_app,
		metadata=metadata,
	)


def adjust_credits(
	owner_doctype,
	owner_name,
	credit_type,
	amount,
	reason,
	idempotency_key=None,
):
	return AdjustmentService.adjust_credits(
		owner_doctype,
		owner_name,
		credit_type,
		amount,
		reason,
		idempotency_key=idempotency_key,
	)


def transfer_credits(
	from_account,
	to_account,
	credit_type,
	amount,
	reference_doctype=None,
	reference_name=None,
	idempotency_key=None,
):
	return TransferService.transfer_credits(
		from_account,
		to_account,
		credit_type,
		amount,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		idempotency_key=idempotency_key,
	)


def expire_credits():
	return ExpiryService.expire_credits()


def reconcile_account(credit_account):
	raise NotImplementedError(_NOT_IMPLEMENTED)


def reconcile_all_accounts():
	raise NotImplementedError(_NOT_IMPLEMENTED)


__all__ = [
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
]