# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Desk permission hooks for ownership-based credit data access."""

import frappe

READ_PTYPES = frozenset({"read", "select", "export", "print", "email", "report"})
MUTATION_PTYPES = frozenset({"create", "write", "submit", "cancel", "amend", "delete"})

PRIVILEGED_READ_ROLES = frozenset(
	{"System Manager", "Credit Manager", "Credit Auditor", "Credit Developer"}
)
MUTATION_ROLES = frozenset({"System Manager", "Credit Manager"})
AUDIT_ONLY_ROLES = frozenset({"Credit Auditor", "Credit Developer"})


def _roles(user):
	return set(frappe.get_roles(user))


def _is_administrator(user):
	return user == "Administrator"


def _has_privileged_read(user):
	return bool(_roles(user).intersection(PRIVILEGED_READ_ROLES))


def _can_mutate_credit_data(user):
	return _is_administrator(user) or "Credit Manager" in _roles(user) or "System Manager" in _roles(
		user
	)


def _user_owned_accounts_subquery(user):
	return f"""(
		SELECT `name` FROM `tabCredit Account`
		WHERE `account_owner_doctype` = 'User'
		AND `account_owner_name` = {frappe.db.escape(user)}
	)"""


def _user_owns_credit_account(doc, user):
	return (
		doc.get("account_owner_doctype") == "User"
		and doc.get("account_owner_name") == user
	)


def _credit_user_only(user):
	return "Credit User" in _roles(user) and not _has_privileged_read(user)


def _user_owns_linked_account(account, user):
	if not account:
		return False
	return bool(
		frappe.db.exists(
			"Credit Account",
			{
				"name": account,
				"account_owner_doctype": "User",
				"account_owner_name": user,
			},
		)
	)


def _ownership_query(user, doctype, account_field="credit_account"):
	if not user:
		user = frappe.session.user
	if _is_administrator(user) or _has_privileged_read(user):
		return ""
	if _credit_user_only(user):
		return f"`tab{doctype}`.`{account_field}` IN {_user_owned_accounts_subquery(user)}"
	return f"`tab{doctype}`.`name` = ''"


def get_credit_account_query_conditions(user, doctype=None):
	if not user:
		user = frappe.session.user
	if _is_administrator(user) or _has_privileged_read(user):
		return ""
	if _credit_user_only(user):
		return (
			f"`tabCredit Account`.`account_owner_doctype` = 'User' "
			f"AND `tabCredit Account`.`account_owner_name` = {frappe.db.escape(user)}"
		)
	return "`tabCredit Account`.`name` = ''"


def has_credit_account_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user
	if _is_administrator(user):
		return True
	if _has_privileged_read(user):
		if ptype in MUTATION_PTYPES and not _can_mutate_credit_data(user):
			return False
		return None
	if _credit_user_only(user):
		if ptype in READ_PTYPES:
			return _user_owns_credit_account(doc, user)
		return False
	return None


def get_credit_ledger_query_conditions(user, doctype=None):
	if not user:
		user = frappe.session.user
	if _is_administrator(user) or _has_privileged_read(user):
		return ""
	if _credit_user_only(user):
		return f"`tabCredit Ledger Entry`.`credit_account` IN {_user_owned_accounts_subquery(user)}"
	return "`tabCredit Ledger Entry`.`name` = ''"


def has_credit_ledger_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user
	if _is_administrator(user):
		return True

	if doc.get("docstatus") == 1 and ptype in {"write", "cancel", "amend", "delete"}:
		return False

	if _has_privileged_read(user):
		if ptype in MUTATION_PTYPES and not _can_mutate_credit_data(user):
			return False
		return None

	if _credit_user_only(user):
		if ptype in READ_PTYPES:
			return _user_owns_linked_account(doc.get("credit_account"), user)
		return False

	return None


def get_credit_reservation_query_conditions(user, doctype=None):
	return _ownership_query(user, "Credit Reservation")


def has_credit_reservation_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user
	if _is_administrator(user):
		return True
	if _has_privileged_read(user):
		if ptype in MUTATION_PTYPES and not _can_mutate_credit_data(user):
			return False
		return None
	if _credit_user_only(user):
		if ptype in READ_PTYPES:
			return _user_owns_linked_account(doc.get("credit_account"), user)
		return False
	return None


def get_credit_grant_query_conditions(user, doctype=None):
	return _ownership_query(user, "Credit Grant")


def has_credit_grant_permission(doc, ptype, user):
	return has_credit_reservation_permission(doc, ptype, user)


def get_credit_expiry_lot_query_conditions(user, doctype=None):
	return _ownership_query(user, "Credit Expiry Lot")


def has_credit_expiry_lot_permission(doc, ptype, user):
	return has_credit_reservation_permission(doc, ptype, user)


def get_credit_transfer_query_conditions(user, doctype=None):
	if not user:
		user = frappe.session.user
	if _is_administrator(user) or _has_privileged_read(user):
		return ""
	if _credit_user_only(user):
		owned = _user_owned_accounts_subquery(user)
		return (
			f"(`tabCredit Transfer`.`from_credit_account` IN {owned} "
			f"OR `tabCredit Transfer`.`to_credit_account` IN {owned})"
		)
	return "`tabCredit Transfer`.`name` = ''"


def has_credit_transfer_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user
	if _is_administrator(user):
		return True
	if _has_privileged_read(user):
		if ptype in MUTATION_PTYPES and not _can_mutate_credit_data(user):
			return False
		return None
	if _credit_user_only(user):
		if ptype in READ_PTYPES:
			return _user_owns_linked_account(
				doc.get("from_credit_account"), user
			) or _user_owns_linked_account(doc.get("to_credit_account"), user)
		return False
	return None


def get_credit_type_query_conditions(user, doctype=None):
	if not user:
		user = frappe.session.user
	if _is_administrator(user) or _has_privileged_read(user):
		return ""
	return "`tabCredit Type`.`name` = ''"


def has_credit_type_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user
	if _is_administrator(user):
		return True
	if _has_privileged_read(user):
		if ptype in MUTATION_PTYPES and not _can_mutate_credit_data(user):
			return False
		return None
	if _credit_user_only(user):
		return False
	return None


def get_credit_settings_query_conditions(user, doctype=None):
	if not user:
		user = frappe.session.user
	if _is_administrator(user) or _has_privileged_read(user):
		return ""
	return "`tabCredit Settings`.`name` = ''"


def has_credit_settings_permission(doc, ptype, user):
	if not user:
		user = frappe.session.user
	if _is_administrator(user):
		return True
	if _credit_user_only(user):
		return False
	if _has_privileged_read(user):
		if ptype in MUTATION_PTYPES and "System Manager" not in _roles(user):
			return False
		return None
	return None