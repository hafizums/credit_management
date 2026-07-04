# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""
Stable public integration surface for consuming Frappe apps.

All balance-changing operations must go through this module.
Do not mutate Credit Account balances or ledger rows from outside services.
"""

_NOT_IMPLEMENTED = "Not implemented — available from Gate 2 onward."


def get_or_create_account(owner_doctype, owner_name, credit_type, company=None):
	raise NotImplementedError(_NOT_IMPLEMENTED)


def get_balance(owner_doctype, owner_name, credit_type, company=None):
	raise NotImplementedError(_NOT_IMPLEMENTED)


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
	raise NotImplementedError(_NOT_IMPLEMENTED)


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
	raise NotImplementedError(_NOT_IMPLEMENTED)


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
	raise NotImplementedError(_NOT_IMPLEMENTED)


def consume_reserved_credits(
	reservation_name,
	actual_amount=None,
	idempotency_key=None,
	source_app=None,
	metadata=None,
):
	raise NotImplementedError(_NOT_IMPLEMENTED)


def release_reservation(reservation_name, reason=None, idempotency_key=None):
	raise NotImplementedError(_NOT_IMPLEMENTED)


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
	raise NotImplementedError(_NOT_IMPLEMENTED)


def adjust_credits(
	owner_doctype,
	owner_name,
	credit_type,
	amount,
	reason,
	idempotency_key=None,
):
	raise NotImplementedError(_NOT_IMPLEMENTED)


def transfer_credits(
	from_account,
	to_account,
	credit_type,
	amount,
	reference_doctype=None,
	reference_name=None,
	idempotency_key=None,
):
	raise NotImplementedError(_NOT_IMPLEMENTED)


def expire_credits():
	raise NotImplementedError(_NOT_IMPLEMENTED)


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