# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils import cint

from credit_management.report_utils import date_range_clause, enforce_report_access

REPORT_NAME = "Top Credit Consumers"


def execute(filters=None):
	enforce_report_access(REPORT_NAME)
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Account Owner DocType"),
			"fieldname": "account_owner_doctype",
			"fieldtype": "Link",
			"options": "DocType",
			"width": 160,
		},
		{
			"label": _("Account Owner Name"),
			"fieldname": "account_owner_name",
			"fieldtype": "Dynamic Link",
			"options": "account_owner_doctype",
			"width": 180,
		},
		{
			"label": _("Credit Type"),
			"fieldname": "credit_type",
			"fieldtype": "Link",
			"options": "Credit Type",
			"width": 120,
		},
		{
			"label": _("Consumed"),
			"fieldname": "consumed",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Entry Count"),
			"fieldname": "entry_count",
			"fieldtype": "Int",
			"width": 110,
		},
	]


def get_data(filters):
	conditions = [
		"cle.docstatus = 1",
		"cle.entry_type IN ('CONSUME', 'CONSUME_RESERVE')",
	]
	values = []

	if filters.get("credit_type"):
		conditions.append("ca.credit_type = %s")
		values.append(filters["credit_type"])

	date_clause, date_values = date_range_clause(filters, "creation")
	if date_clause:
		conditions.append(date_clause.replace("`creation`", "cle.`creation`"))
		values.extend(date_values)

	limit = cint(filters.get("limit") or 10)
	where_sql = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT
			ca.account_owner_doctype,
			ca.account_owner_name,
			ca.credit_type,
			SUM(cle.amount) AS consumed,
			COUNT(cle.name) AS entry_count
		FROM `tabCredit Ledger Entry` cle
		INNER JOIN `tabCredit Account` ca ON ca.name = cle.credit_account
		WHERE {where_sql}
		GROUP BY ca.account_owner_doctype, ca.account_owner_name, ca.credit_type
		ORDER BY consumed DESC
		LIMIT {limit}
		""",
		tuple(values),
		as_dict=True,
	)