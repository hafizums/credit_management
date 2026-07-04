# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _

from credit_management.report_utils import date_range_clause, enforce_report_access

REPORT_NAME = "Credit Usage by App"


def execute(filters=None):
	enforce_report_access(REPORT_NAME)
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Source App"),
			"fieldname": "source_app",
			"fieldtype": "Data",
			"width": 160,
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
		conditions.append("cle.credit_type = %s")
		values.append(filters["credit_type"])
	if filters.get("source_app"):
		conditions.append("cle.source_app = %s")
		values.append(filters["source_app"])

	date_clause, date_values = date_range_clause(filters, "creation")
	if date_clause:
		conditions.append(date_clause.replace("`creation`", "cle.`creation`"))
		values.extend(date_values)

	where_sql = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT
			IFNULL(cle.source_app, '') AS source_app,
			cle.credit_type,
			SUM(CASE WHEN cle.entry_type IN ('CONSUME', 'CONSUME_RESERVE') THEN cle.amount ELSE 0 END) AS consumed,
			SUM(CASE WHEN cle.entry_type = 'RESERVE' THEN cle.amount ELSE 0 END) AS reserved,
			SUM(CASE WHEN cle.entry_type = 'RELEASE_RESERVE' THEN cle.amount ELSE 0 END) AS released,
			SUM(CASE WHEN cle.entry_type = 'EXPIRE' THEN cle.amount ELSE 0 END) AS expired,
			SUM(CASE WHEN cle.entry_type = 'REFUND' THEN cle.amount ELSE 0 END) AS refund,
			COUNT(*) AS entry_count
		FROM `tabCredit Ledger Entry` cle
		WHERE {where_sql}
		GROUP BY IFNULL(cle.source_app, ''), cle.credit_type
		ORDER BY consumed DESC, source_app ASC, cle.credit_type ASC
		""",
		tuple(values),
		as_dict=True,
	)