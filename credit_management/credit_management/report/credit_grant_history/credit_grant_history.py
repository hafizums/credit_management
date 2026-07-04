# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _

from credit_management.report_utils import date_range_clause, enforce_report_access

REPORT_NAME = "Credit Grant History"


def execute(filters=None):
	enforce_report_access(REPORT_NAME)
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Grant"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Credit Grant",
			"width": 140,
		},
		{
			"label": _("Creation"),
			"fieldname": "creation",
			"fieldtype": "Datetime",
			"width": 160,
		},
		{
			"label": _("Credit Account"),
			"fieldname": "credit_account",
			"fieldtype": "Link",
			"options": "Credit Account",
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
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Grant Reason"),
			"fieldname": "grant_reason",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Valid From"),
			"fieldname": "valid_from",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Expires On"),
			"fieldname": "expires_on",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Source App"),
			"fieldname": "source_app",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Reference DocType"),
			"fieldname": "reference_doctype",
			"fieldtype": "Link",
			"options": "DocType",
			"width": 150,
		},
		{
			"label": _("Reference Name"),
			"fieldname": "reference_name",
			"fieldtype": "Dynamic Link",
			"options": "reference_doctype",
			"width": 160,
		},
		{
			"label": _("Idempotency Key"),
			"fieldname": "idempotency_key",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Ledger Entry"),
			"fieldname": "ledger_entry",
			"fieldtype": "Link",
			"options": "Credit Ledger Entry",
			"width": 150,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100,
		},
	]


def get_data(filters):
	conditions = []
	values = []

	for fieldname in (
		"credit_account",
		"credit_type",
		"status",
		"source_app",
		"reference_doctype",
		"reference_name",
	):
		if filters.get(fieldname):
			conditions.append(f"cg.`{fieldname}` = %s")
			values.append(filters[fieldname])

	date_clause, date_values = date_range_clause(filters, "creation")
	if date_clause:
		conditions.append(date_clause.replace("`creation`", "cg.`creation`"))
		values.extend(date_values)

	where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
	return frappe.db.sql(
		f"""
		SELECT
			cg.name,
			cg.creation,
			cg.credit_account,
			cg.credit_type,
			cg.amount,
			cg.grant_reason,
			cg.valid_from,
			cg.expires_on,
			cg.source_app,
			cg.reference_doctype,
			cg.reference_name,
			cg.idempotency_key,
			cg.ledger_entry,
			cg.status
		FROM `tabCredit Grant` cg
		{where_sql}
		ORDER BY cg.creation DESC, cg.name DESC
		""",
		tuple(values),
		as_dict=True,
	)