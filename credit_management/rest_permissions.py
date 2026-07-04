# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Authorization rules for optional REST API wrappers."""

import frappe
from frappe import _

MUTATION_OPERATIONS = frozenset(
	{
		"grant_credits",
		"consume_credits",
		"reserve_credits",
		"consume_reserved_credits",
		"release_reservation",
		"refund_credits",
		"adjust_credits",
		"transfer_credits",
		"expire_credits",
	}
)

READ_OPERATIONS = frozenset({"get_balance"})

RECONCILE_OPERATIONS = frozenset({"reconcile_account", "reconcile_all_accounts"})

MUTATION_ROLES = frozenset({"System Manager", "Credit Manager"})
AUDIT_ROLES = frozenset({"Credit Auditor", "Credit Developer", "Credit Manager", "System Manager"})


def ensure_rest_enabled():
	if not frappe.get_single("Credit Settings").enable_rest_api:
		frappe.throw(_("Credit Management REST API is disabled"), frappe.PermissionError)


def authorize(operation, **kwargs):
	ensure_rest_enabled()
	user = frappe.session.user
	roles = set(frappe.get_roles(user))

	if operation in MUTATION_OPERATIONS:
		if not roles.intersection(MUTATION_ROLES):
			frappe.throw(
				_("Not permitted to call REST mutation operation {0}").format(operation),
				frappe.PermissionError,
			)
		return

	if operation in READ_OPERATIONS:
		_check_read_balance_access(user, roles, **kwargs)
		return

	if operation in RECONCILE_OPERATIONS:
		if not roles.intersection(AUDIT_ROLES):
			frappe.throw(
				_("Not permitted to call REST reconciliation operation {0}").format(operation),
				frappe.PermissionError,
			)
		return

	frappe.throw(_("Unsupported REST operation: {0}").format(operation), frappe.PermissionError)


def _check_read_balance_access(user, roles, owner_doctype=None, owner_name=None, **kwargs):
	if user == "Administrator" or roles.intersection(MUTATION_ROLES):
		return

	if "Credit Auditor" in roles or "Credit Developer" in roles:
		return

	if "Credit User" in roles and not roles.intersection(MUTATION_ROLES | AUDIT_ROLES):
		if owner_doctype != "User" or owner_name != user:
			frappe.throw(
				_("Credit User may only read balance for their own User account"),
				frappe.PermissionError,
			)
		return

	frappe.throw(_("Not permitted to call REST read operation get_balance"), frappe.PermissionError)