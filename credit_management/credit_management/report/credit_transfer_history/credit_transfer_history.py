# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _

from credit_management.report_utils import date_range_clause, enforce_report_access

REPORT_NAME = "Credit Transfer History"


def execute(filters=None):
	enforce_report_access(REPORT_NAME)
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Transfer"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Credit Transfer",
			"width": 140,
		},
		{
			"label": _("Creation"),
			"fieldname": "creation",
			"fieldtype": "Datetime",
			"width": 160,
		},
		{
			"label": _("From Credit Account"),
			"fieldname": "from_credit_account",
			"fieldtype": "Link",
			"options": "Credit Account",
			"width": 170,
		},
		{
			"label": _("To Credit Account"),
			"fieldname": "to_credit_account",
			"fieldtype": "Link",
			"options": "Credit Account",
			"width": 170,
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
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 110,
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
			"label": _("Source App"),
			"fieldname": "source_app",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Remarks"),
			"fieldname": "remarks",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Transfer Out Ledger Entry"),
			"fieldname": "transfer_out_ledger_entry",
			"fieldtype": "Link",
			"options": "Credit Ledger Entry",
			"width": 180,
		},
		{
			"label": _("Transfer In Ledger Entry"),
			"fieldname": "transfer_in_ledger_entry",
			"fieldtype": "Link",
			"options": "Credit Ledger Entry",
			"width": 180,
		},
	]


def get_data(filters):
	conditions = []
	values = []

	for fieldname in (
		"from_credit_account",
		"to_credit_account",
		"credit_type",
		"status",
		"source_app",
		"reference_doctype",
		"reference_name",
	):
		if filters.get(fieldname):
			conditions.append(f"ct.`{fieldname}` = %s")
			values.append(filters[fieldname])

	date_clause, date_values = date_range_clause(filters, "creation")
	if date_clause:
		conditions.append(date_clause.replace("`creation`", "ct.`creation`"))
		values.extend(date_values)

	where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
	return frappe.db.sql(
		f"""
		SELECT
			ct.name,
			ct.creation,
			ct.from_credit_account,
			ct.to_credit_account,
			ct.credit_type,
			ct.amount,
			ct.status,
			ct.reference_doctype,
			ct.reference_name,
			ct.idempotency_key,
			ct.source_app,
			ct.remarks,
			ct.transfer_out_ledger_entry,
			ct.transfer_in_ledger_entry
		FROM `tabCredit Transfer` ct
		{where_sql}
		ORDER BY ct.creation DESC, ct.name DESC
		""",
		tuple(values),
		as_dict=True,
	)