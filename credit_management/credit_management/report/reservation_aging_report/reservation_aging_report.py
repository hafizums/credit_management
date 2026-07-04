# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.utils import flt, time_diff_in_hours

from credit_management.report_utils import enforce_report_access

REPORT_NAME = "Reservation Aging Report"
ACTIVE_STATUSES = ("Active", "Partially Consumed")


def execute(filters=None):
	enforce_report_access(REPORT_NAME)
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Reservation"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Credit Reservation",
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
			"label": _("Reserved Amount"),
			"fieldname": "reserved_amount",
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
			"label": _("Released Amount"),
			"fieldname": "released_amount",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Outstanding Amount"),
			"fieldname": "outstanding_amount",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Expires At"),
			"fieldname": "expires_at",
			"fieldtype": "Datetime",
			"width": 160,
		},
		{
			"label": _("Age (Hours)"),
			"fieldname": "age_hours",
			"fieldtype": "Float",
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
	]


def get_data(filters):
	query_filters = {"status": ["in", list(ACTIVE_STATUSES)]}
	for fieldname, filter_key in (
		("credit_account", "credit_account"),
		("credit_type", "credit_type"),
		("source_app", "source_app"),
	):
		if filters.get(filter_key):
			query_filters[fieldname] = filters[filter_key]

	rows = frappe.get_all(
		"Credit Reservation",
		filters=query_filters,
		fields=[
			"name",
			"creation",
			"credit_account",
			"credit_type",
			"reserved_amount",
			"consumed_amount",
			"released_amount",
			"status",
			"expires_at",
			"source_app",
			"reference_doctype",
			"reference_name",
		],
		order_by="creation asc",
	)

	now = frappe.utils.now_datetime()
	min_age = flt(filters.get("min_age_hours"))
	data = []
	for row in rows:
		outstanding = flt(row.reserved_amount) - flt(row.consumed_amount) - flt(row.released_amount)
		if outstanding <= 0:
			continue

		age_hours = time_diff_in_hours(now, row.creation)
		if min_age and age_hours < min_age:
			continue

		data.append(
			{
				**row,
				"outstanding_amount": outstanding,
				"age_hours": age_hours,
			}
		)

	data.sort(key=lambda row: row["age_hours"], reverse=True)
	return data