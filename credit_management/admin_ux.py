# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Desk admin UX helpers — whitelisted wrappers over trusted credit_management.api."""

import json

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt

import credit_management.api as credit_api
from credit_management.permissions import (
	_can_mutate_credit_data,
	_credit_user_only,
	_has_privileged_read,
	_is_administrator,
)
from credit_management.services.reservation_service import ACTIVE_RESERVATION_STATUSES


def _ensure_manager(user=None):
	user = user or frappe.session.user
	if not _can_mutate_credit_data(user):
		frappe.throw(
			_("Only Credit Manager or System Manager may perform this action"),
			frappe.PermissionError,
		)


def _ensure_privileged_read(user=None):
	user = user or frappe.session.user
	if _is_administrator(user) or _has_privileged_read(user):
		return
	frappe.throw(_("Not permitted to view credit admin data"), frappe.PermissionError)


def _ensure_balance_view_access(owner_doctype, owner_name, user=None):
	user = user or frappe.session.user
	if _is_administrator(user) or _has_privileged_read(user):
		return
	if _credit_user_only(user) and owner_doctype == "User" and owner_name == user:
		return
	frappe.throw(
		_("Not permitted to view balance for this account"),
		frappe.PermissionError,
	)


def _desk_idempotency_key(prefix, owner_name=None, credit_type=None):
	parts = ["desk", prefix, frappe.generate_hash(length=10)]
	if owner_name:
		parts.append(owner_name)
	if credit_type:
		parts.append(credit_type)
	return ":".join(parts)


def _balance_snapshot(owner_doctype, owner_name, credit_type, company=None):
	account_name = credit_api.get_or_create_account(
		owner_doctype, owner_name, credit_type, company
	)
	account = frappe.get_doc("Credit Account", account_name)
	return {
		"credit_account": account.name,
		"current_balance": flt(account.current_balance),
		"reserved_balance": flt(account.reserved_balance),
		"available_balance": flt(account.available_balance),
		"lifetime_granted": flt(account.lifetime_granted),
		"lifetime_consumed": flt(account.lifetime_consumed),
		"lifetime_expired": flt(account.lifetime_expired),
	}


def _wrap_balance_change(owner_doctype, owner_name, credit_type, company, result):
	after = _balance_snapshot(owner_doctype, owner_name, credit_type, company)
	entry = None
	if result.get("ledger_entry"):
		entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
	return {
		"result": result,
		"balance_after": after,
		"ledger_entry": entry.name if entry else None,
		"entry_type": entry.entry_type if entry else None,
	}


@frappe.whitelist()
def admin_top_up_credits(
	owner_doctype,
	owner_name,
	credit_type,
	amount,
	grant_reason,
	expires_on=None,
	reference_doctype=None,
	reference_name=None,
	idempotency_key=None,
	company=None,
):
	_ensure_manager()
	grant_reason = (grant_reason or "").strip()
	if not grant_reason:
		frappe.throw(_("Grant reason is required"))

	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Amount must be positive"))

	balance_before = _balance_snapshot(owner_doctype, owner_name, credit_type, company)
	idempotency_key = idempotency_key or _desk_idempotency_key(
		"grant", owner_name, credit_type
	)
	metadata = {
		"grant_reason": grant_reason,
		"initiated_by": frappe.session.user,
		"source": "desk_admin_top_up",
	}

	result = credit_api.grant_credits(
		owner_doctype,
		owner_name,
		credit_type,
		amount,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		expires_on=expires_on,
		idempotency_key=idempotency_key,
		source_app="credit_management_desk",
		metadata=metadata,
	)

	wrapped = _wrap_balance_change(owner_doctype, owner_name, credit_type, company, result)
	wrapped["balance_before"] = balance_before
	wrapped["grant_reason"] = grant_reason
	return wrapped


@frappe.whitelist()
def admin_refund_credits(
	owner_doctype,
	owner_name,
	credit_type,
	amount,
	refund_reason,
	reference_doctype=None,
	reference_name=None,
	idempotency_key=None,
	company=None,
):
	_ensure_manager()
	refund_reason = (refund_reason or "").strip()
	if not refund_reason:
		frappe.throw(_("Refund reason is required"))

	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Amount must be positive"))

	balance_before = _balance_snapshot(owner_doctype, owner_name, credit_type, company)
	idempotency_key = idempotency_key or _desk_idempotency_key(
		"refund", owner_name, credit_type
	)
	metadata = {
		"refund_reason": refund_reason,
		"initiated_by": frappe.session.user,
		"source": "desk_admin_refund",
	}

	result = credit_api.refund_credits(
		owner_doctype,
		owner_name,
		credit_type,
		amount,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
		idempotency_key=idempotency_key,
		source_app="credit_management_desk",
		metadata=metadata,
	)

	wrapped = _wrap_balance_change(owner_doctype, owner_name, credit_type, company, result)
	wrapped["balance_before"] = balance_before
	wrapped["refund_reason"] = refund_reason
	return wrapped


@frappe.whitelist()
def admin_get_reservation_details(reservation_name):
	_ensure_privileged_read()
	if not frappe.db.exists("Credit Reservation", reservation_name):
		frappe.throw(_("Credit Reservation {0} not found").format(reservation_name))

	reservation = frappe.get_doc("Credit Reservation", reservation_name)
	account = frappe.get_doc("Credit Account", reservation.credit_account)
	return {
		"reservation": {
			"name": reservation.name,
			"status": reservation.status,
			"reserved_amount": flt(reservation.reserved_amount),
			"released_amount": flt(reservation.released_amount),
			"consumed_amount": flt(reservation.consumed_amount),
			"reference_doctype": reservation.reference_doctype,
			"reference_name": reservation.reference_name,
			"expires_at": reservation.expires_at,
		},
		"account": {
			"name": account.name,
			"owner_doctype": account.account_owner_doctype,
			"owner_name": account.account_owner_name,
			"credit_type": account.credit_type,
			"available_balance": flt(account.available_balance),
		},
		"can_release": reservation.status in ACTIVE_RESERVATION_STATUSES,
	}


@frappe.whitelist()
def admin_release_reservation(reservation_name, reason, idempotency_key=None):
	_ensure_manager()
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Release reason is required"))

	details = admin_get_reservation_details(reservation_name)
	if not details.get("can_release"):
		frappe.throw(
			_("Reservation {0} cannot be released (status: {1})").format(
				reservation_name, details["reservation"]["status"]
			),
			frappe.ValidationError,
		)

	idempotency_key = idempotency_key or _desk_idempotency_key(
		f"release-{reservation_name}"
	)
	result = credit_api.release_reservation(
		reservation_name,
		reason=reason,
		idempotency_key=idempotency_key,
	)

	entry = frappe.get_doc("Credit Ledger Entry", result["ledger_entry"])
	reservation = frappe.get_doc("Credit Reservation", reservation_name)
	return {
		"result": result,
		"ledger_entry": entry.name,
		"entry_type": entry.entry_type,
		"reservation_status": reservation.status,
	}


@frappe.whitelist()
def admin_get_reconciliation_review(limit=20):
	_ensure_privileged_read()
	limit = cint(limit) or 20
	limit = min(limit, 100)

	rows = frappe.get_all(
		"Credit Reconciliation Run",
		fields=[
			"name",
			"credit_account",
			"run_type",
			"status",
			"current_difference",
			"reserved_difference",
			"available_difference",
			"checked_accounts",
			"mismatch_count",
			"completed_at",
			"creation",
		],
		order_by="creation desc",
		limit=limit,
	)

	for row in rows:
		details = frappe.db.get_value(
			"Credit Reconciliation Run",
			row.name,
			"details_json",
		)
		if details:
			try:
				parsed = json.loads(details) if isinstance(details, str) else details
				row["details_summary"] = parsed if isinstance(parsed, dict) else {"raw": parsed}
			except (TypeError, ValueError):
				row["details_summary"] = {"raw": cstr(details)}
		else:
			row["details_summary"] = {}

	return rows


@frappe.whitelist()
def admin_rerun_reconcile_account(credit_account):
	_ensure_privileged_read()
	if not frappe.db.exists("Credit Account", credit_account):
		frappe.throw(_("Credit Account {0} not found").format(credit_account))

	account = frappe.get_doc("Credit Account", credit_account)
	before = {
		"current_balance": flt(account.current_balance),
		"reserved_balance": flt(account.reserved_balance),
		"available_balance": flt(account.available_balance),
	}

	result = credit_api.reconcile_account(credit_account)
	account.reload()

	return {
		"reconciliation": result,
		"balance_before": before,
		"balance_after": {
			"current_balance": flt(account.current_balance),
			"reserved_balance": flt(account.reserved_balance),
			"available_balance": flt(account.available_balance),
		},
		"auto_repair_performed": False,
	}


@frappe.whitelist()
def admin_get_account_balance_overview(
	owner_doctype,
	owner_name,
	credit_type,
	company=None,
	ledger_limit=10,
):
	_ensure_balance_view_access(owner_doctype, owner_name)
	ledger_limit = min(cint(ledger_limit) or 10, 50)

	account_name = credit_api.get_or_create_account(
		owner_doctype, owner_name, credit_type, company
	)
	account = frappe.get_doc("Credit Account", account_name)

	reservations = frappe.get_all(
		"Credit Reservation",
		filters={
			"credit_account": account.name,
			"status": ("in", list(ACTIVE_RESERVATION_STATUSES)),
		},
		fields=[
			"name",
			"status",
			"reserved_amount",
			"consumed_amount",
			"released_amount",
			"reference_doctype",
			"reference_name",
			"expires_at",
		],
		order_by="creation desc",
		limit=20,
	)

	ledger_entries = frappe.get_all(
		"Credit Ledger Entry",
		filters={"credit_account": account.name, "docstatus": 1},
		fields=["name", "entry_type", "amount", "creation", "reference_doctype", "reference_name"],
		order_by="creation desc",
		limit=ledger_limit,
	)

	return {
		"account": {
			"name": account.name,
			"owner_doctype": account.account_owner_doctype,
			"owner_name": account.account_owner_name,
			"credit_type": account.credit_type,
			"status": account.status,
			"current_balance": flt(account.current_balance),
			"reserved_balance": flt(account.reserved_balance),
			"available_balance": flt(account.available_balance),
			"lifetime_granted": flt(account.lifetime_granted),
			"lifetime_consumed": flt(account.lifetime_consumed),
			"lifetime_expired": flt(account.lifetime_expired),
		},
		"active_reservations": reservations,
		"recent_ledger_entries": ledger_entries,
	}


@frappe.whitelist()
def get_low_balance_account_count():
	"""Custom Number Card method — counts accounts below configured threshold."""
	if not (
		_is_administrator(frappe.session.user) or _has_privileged_read(frappe.session.user)
	):
		return 0
	settings = frappe.get_single("Credit Settings")
	threshold = flt(settings.low_balance_threshold_default)
	if threshold <= 0:
		return 0

	return frappe.db.count(
		"Credit Account",
		{
			"status": "Active",
			"available_balance": ("<", threshold),
		},
	)