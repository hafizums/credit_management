# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Shared helpers for script reports."""

import frappe
from frappe import _

PRIVILEGED_REPORT_ROLES = frozenset(
	{"System Manager", "Credit Manager", "Credit Auditor", "Credit Developer", "Administrator"}
)
CREDIT_USER_REPORTS = frozenset({"Credit Balance Report", "Credit Ledger Report"})
PRIVILEGED_ONLY_REPORTS = frozenset(
	{
		"Credit Usage by App",
		"Credit Usage by Owner",
		"Reservation Aging Report",
		"Expired Credits Report",
		"Reconciliation Report",
		"Top Credit Consumers",
		"Credit Grant History",
		"Credit Transfer History",
	}
)


def enforce_report_access(report_name):
	user = frappe.session.user
	if user == "Administrator":
		return

	roles = set(frappe.get_roles(user))
	if report_name in CREDIT_USER_REPORTS:
		if roles.intersection(PRIVILEGED_REPORT_ROLES) or "Credit User" in roles:
			return
	elif report_name in PRIVILEGED_ONLY_REPORTS:
		if roles.intersection(PRIVILEGED_REPORT_ROLES):
			return
	else:
		if roles.intersection(PRIVILEGED_REPORT_ROLES):
			return

	frappe.throw(_("Not permitted to run report {0}").format(report_name), frappe.PermissionError)


def is_privileged_report_user(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(set(frappe.get_roles(user)).intersection(PRIVILEGED_REPORT_ROLES))


def credit_user_owner_filters(user=None):
	user = user or frappe.session.user
	if is_privileged_report_user(user):
		return {}
	return {"account_owner_doctype": "User", "account_owner_name": user}


def owned_account_names(user=None):
	user = user or frappe.session.user
	if is_privileged_report_user(user):
		return None
	return frappe.get_all(
		"Credit Account",
		filters={"account_owner_doctype": "User", "account_owner_name": user},
		pluck="name",
	)


def apply_account_scope(filters, account_field="credit_account"):
	owned = owned_account_names()
	if owned is None:
		return filters

	scope = owned
	if filters.get(account_field):
		if filters[account_field] not in owned:
			scope = []
		else:
			return filters

	filters = dict(filters or {})
	filters[account_field] = ["in", scope or ["__none__"]]
	return filters


def date_range_clause(filters, fieldname):
	clauses = []
	values = []
	if filters.get("from_date"):
		clauses.append(f"`{fieldname}` >= %s")
		values.append(filters["from_date"])
	if filters.get("to_date"):
		clauses.append(f"`{fieldname}` <= %s")
		values.append(filters["to_date"])
	return (" AND ".join(clauses), values) if clauses else ("", [])


def standard_report_roles(include_credit_user=False):
	roles = [
		{"role": "System Manager"},
		{"role": "Credit Manager"},
		{"role": "Credit Auditor"},
		{"role": "Credit Developer"},
	]
	if include_credit_user:
		roles.append({"role": "Credit User"})
	return roles