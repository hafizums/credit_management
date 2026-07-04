# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _

from credit_management.report_utils import date_range_clause, enforce_report_access

REPORT_NAME = "Credit Usage by Owner"


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
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Current Balance"),
			"fieldname": "current_balance",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Consumed"),
			"fieldname": "consumed",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Reserved"),
			"fieldname": "reserved",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Released"),
			"fieldname": "released",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Expired"),
			"fieldname": "expired",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Refund"),
			"fieldname": "refund",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Entry Count"),
			"fieldname": "entry_count",
			"fieldtype": "Int",
			"width": 110,
		},
	]


def get_data(filters):
	conditions = ["cle.docstatus = 1"]
	values = []

	if filters.get("credit_type"):
		conditions.append("ca.credit_type = %s")
		values.append(filters["credit_type"])
	if filters.get("owner_doctype"):
		conditions.append("ca.account_owner_doctype = %s")
		values.append(filters["owner_doctype"])
	if filters.get("owner_name"):
		conditions.append("ca.account_owner_name = %s")
		values.append(filters["owner_name"])
	if filters.get("company"):
		conditions.append("ca.company = %s")
		values.append(filters["company"])

	date_clause, date_values = date_range_clause(filters, "creation")
	if date_clause:
		conditions.append(date_clause.replace("`creation`", "cle.`creation`"))
		values.extend(date_values)

	where_sql = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT
			ca.account_owner_doctype,
			ca.account_owner_name,
			ca.credit_type,
			ca.company,
			ca.current_balance,
			SUM(CASE WHEN cle.entry_type IN ('CONSUME', 'CONSUME_RESERVE') THEN cle.amount ELSE 0 END) AS consumed,
			SUM(CASE WHEN cle.entry_type = 'RESERVE' THEN cle.amount ELSE 0 END) AS reserved,
			SUM(CASE WHEN cle.entry_type = 'RELEASE_RESERVE' THEN cle.amount ELSE 0 END) AS released,
			SUM(CASE WHEN cle.entry_type = 'EXPIRE' THEN cle.amount ELSE 0 END) AS expired,
			SUM(CASE WHEN cle.entry_type = 'REFUND' THEN cle.amount ELSE 0 END) AS refund,
			COUNT(cle.name) AS entry_count
		FROM `tabCredit Account` ca
		LEFT JOIN `tabCredit Ledger Entry` cle
			ON cle.credit_account = ca.name
		WHERE {where_sql}
		GROUP BY
			ca.name,
			ca.account_owner_doctype,
			ca.account_owner_name,
			ca.credit_type,
			ca.company,
			ca.current_balance
		ORDER BY consumed DESC, ca.account_owner_name ASC, ca.credit_type ASC
		""",
		tuple(values),
		as_dict=True,
	)