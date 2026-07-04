# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _

from credit_management.report_utils import apply_account_scope, date_range_clause, enforce_report_access

REPORT_NAME = "Credit Ledger Report"


def execute(filters=None):
	enforce_report_access(REPORT_NAME)
	filters = apply_account_scope(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Name"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Credit Ledger Entry",
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
			"label": _("Entry Type"),
			"fieldname": "entry_type",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Amount"),
			"fieldname": "amount",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Balance After"),
			"fieldname": "balance_after",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Reserved Balance After"),
			"fieldname": "reserved_balance_after",
			"fieldtype": "Float",
			"width": 150,
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
			"label": _("Source App"),
			"fieldname": "source_app",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Idempotency Key"),
			"fieldname": "idempotency_key",
			"fieldtype": "Data",
			"width": 180,
		},
	]


def get_data(filters):
	conditions = ["cle.docstatus = 1"]
	values = []

	for fieldname in (
		"credit_account",
		"credit_type",
		"entry_type",
		"reference_doctype",
		"reference_name",
		"source_app",
	):
		if filters.get(fieldname):
			if isinstance(filters[fieldname], (list, tuple)) and filters[fieldname][0] == "in":
				placeholders = ", ".join(["%s"] * len(filters[fieldname][1]))
				conditions.append(f"cle.`{fieldname}` IN ({placeholders})")
				values.extend(filters[fieldname][1])
			else:
				conditions.append(f"cle.`{fieldname}` = %s")
				values.append(filters[fieldname])

	date_clause, date_values = date_range_clause(filters, "creation")
	if date_clause:
		conditions.append(date_clause.replace("`creation`", "cle.`creation`"))
		values.extend(date_values)

	where_sql = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT
			cle.name,
			cle.creation,
			cle.credit_account,
			cle.credit_type,
			cle.entry_type,
			cle.amount,
			cle.balance_after,
			cle.reserved_balance_after,
			cle.reference_doctype,
			cle.reference_name,
			cle.source_app,
			cle.idempotency_key
		FROM `tabCredit Ledger Entry` cle
		WHERE {where_sql}
		ORDER BY cle.creation DESC, cle.name DESC
		""",
		tuple(values),
		as_dict=True,
	)