# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Optional whitelisted REST wrappers over the trusted Python API."""

import frappe

import credit_management.api as api
from credit_management.rest_permissions import authorize


@frappe.whitelist()
def get_balance(owner_doctype, owner_name, credit_type, company=None):
	authorize("get_balance", owner_doctype=owner_doctype, owner_name=owner_name)
	return api.get_balance(owner_doctype, owner_name, credit_type, company)


@frappe.whitelist()
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
	authorize("grant_credits")
	return api.grant_credits(
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


@frappe.whitelist()
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
	authorize("consume_credits")
	return api.consume_credits(
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


@frappe.whitelist()
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
	authorize("reserve_credits")
	return api.reserve_credits(
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


@frappe.whitelist()
def consume_reserved_credits(
	reservation_name,
	actual_amount=None,
	idempotency_key=None,
	source_app=None,
	metadata=None,
):
	authorize("consume_reserved_credits")
	return api.consume_reserved_credits(
		reservation_name=reservation_name,
		actual_amount=actual_amount,
		idempotency_key=idempotency_key,
		source_app=source_app,
		metadata=metadata,
	)


@frappe.whitelist()
def release_reservation(reservation_name, reason=None, idempotency_key=None):
	authorize("release_reservation")
	return api.release_reservation(
		reservation_name=reservation_name,
		reason=reason,
		idempotency_key=idempotency_key,
	)


@frappe.whitelist()
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
	authorize("refund_credits")
	return api.refund_credits(
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


@frappe.whitelist()
def adjust_credits(
	owner_doctype,
	owner_name,
	credit_type,
	amount,
	reason,
	idempotency_key=None,
):
	authorize("adjust_credits")
	return api.adjust_credits(
		owner_doctype,
		owner_name,
		credit_type,
		amount,
		reason,
		idempotency_key=idempotency_key,
	)


@frappe.whitelist()
def transfer_credits(
	from_account,
	to_account,
	credit_type,
	amount,
	reference_doctype=None,
	reference_name=None,
	idempotency_key=None,
):
	authorize("transfer_credits")
	return api.transfer_credits(
		from_account,
		to_account,
		credit_type,
		amount,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		idempotency_key=idempotency_key,
	)


@frappe.whitelist()
def expire_credits():
	authorize("expire_credits")
	return api.expire_credits()


@frappe.whitelist()
def reconcile_account(credit_account):
	authorize("reconcile_account")
	return api.reconcile_account(credit_account)


@frappe.whitelist()
def reconcile_all_accounts():
	authorize("reconcile_all_accounts")
	return api.reconcile_all_accounts()