# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils import getdate, today

from credit_management.report_utils import enforce_report_access

REPORT_NAME = "Expired Credits Report"


def execute(filters=None):
	enforce_report_access(REPORT_NAME)
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Expiry Lot"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Credit Expiry Lot",
			"width": 140,
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
			"label": _("Original Amount"),
			"fieldname": "original_amount",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Remaining Amount"),
			"fieldname": "remaining_amount",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Expired Amount"),
			"fieldname": "expired_amount",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Consumed Amount"),
			"fieldname": "consumed_amount",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Reserved Amount"),
			"fieldname": "reserved_amount",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Expires On"),
			"fieldname": "expires_on",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Source Grant"),
			"fieldname": "source_grant",
			"fieldtype": "Link",
			"options": "Credit Grant",
			"width": 140,
		},
	]


def get_data(filters):
	conditions = ["(cel.status = 'Expired' OR cel.expired_amount > 0)"]
	values = []

	if filters.get("credit_account"):
		conditions.append("cel.credit_account = %s")
		values.append(filters["credit_account"])
	if filters.get("credit_type"):
		conditions.append("cel.credit_type = %s")
		values.append(filters["credit_type"])
	if filters.get("status"):
		conditions.append("cel.status = %s")
		values.append(filters["status"])
	if filters.get("from_date"):
		conditions.append("cel.expires_on >= %s")
		values.append(getdate(filters["from_date"]))
	if filters.get("to_date"):
		conditions.append("cel.expires_on <= %s")
		values.append(getdate(filters["to_date"]))
	if not filters.get("from_date") and not filters.get("to_date"):
		conditions.append("cel.expires_on <= %s")
		values.append(today())

	where_sql = " AND ".join(conditions)
	return frappe.db.sql(
		f"""
		SELECT
			cel.name,
			cel.credit_account,
			cel.credit_type,
			cel.original_amount,
			cel.remaining_amount,
			cel.expired_amount,
			cel.consumed_amount,
			cel.reserved_amount,
			cel.expires_on,
			cel.status,
			cel.source_grant
		FROM `tabCredit Expiry Lot` cel
		WHERE {where_sql}
		ORDER BY cel.expires_on DESC, cel.expired_amount DESC, cel.name DESC
		""",
		tuple(values),
		as_dict=True,
	)