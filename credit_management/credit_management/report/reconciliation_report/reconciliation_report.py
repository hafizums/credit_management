# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _

from credit_management.report_utils import date_range_clause, enforce_report_access

REPORT_NAME = "Reconciliation Report"


def execute(filters=None):
	enforce_report_access(REPORT_NAME)
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Run"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Credit Reconciliation Run",
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
			"label": _("Run Type"),
			"fieldname": "run_type",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Expected Current Balance"),
			"fieldname": "expected_current_balance",
			"fieldtype": "Float",
			"width": 170,
		},
		{
			"label": _("Actual Current Balance"),
			"fieldname": "actual_current_balance",
			"fieldtype": "Float",
			"width": 160,
		},
		{
			"label": _("Expected Reserved Balance"),
			"fieldname": "expected_reserved_balance",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": _("Actual Reserved Balance"),
			"fieldname": "actual_reserved_balance",
			"fieldtype": "Float",
			"width": 170,
		},
		{
			"label": _("Expected Available Balance"),
			"fieldname": "expected_available_balance",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": _("Actual Available Balance"),
			"fieldname": "actual_available_balance",
			"fieldtype": "Float",
			"width": 170,
		},
		{
			"label": _("Current Difference"),
			"fieldname": "current_difference",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("Reserved Difference"),
			"fieldname": "reserved_difference",
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"label": _("Available Difference"),
			"fieldname": "available_difference",
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"label": _("Lot Remaining Total"),
			"fieldname": "lot_remaining_total",
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"label": _("Lot Reserved Total"),
			"fieldname": "lot_reserved_total",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("Lot Consumed Total"),
			"fieldname": "lot_consumed_total",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("Lot Expired Total"),
			"fieldname": "lot_expired_total",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("Checked Accounts"),
			"fieldname": "checked_accounts",
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"label": _("Mismatch Count"),
			"fieldname": "mismatch_count",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Error Count"),
			"fieldname": "error_count",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Started At"),
			"fieldname": "started_at",
			"fieldtype": "Datetime",
			"width": 160,
		},
		{
			"label": _("Completed At"),
			"fieldname": "completed_at",
			"fieldtype": "Datetime",
			"width": 160,
		},
		{
			"label": _("Remarks"),
			"fieldname": "remarks",
			"fieldtype": "Data",
			"width": 200,
		},
	]


def get_data(filters):
	conditions = []
	values = []

	if filters.get("credit_account"):
		conditions.append("crr.credit_account = %s")
		values.append(filters["credit_account"])
	if filters.get("run_type"):
		conditions.append("crr.run_type = %s")
		values.append(filters["run_type"])
	if filters.get("status"):
		conditions.append("crr.status = %s")
		values.append(filters["status"])

	date_clause, date_values = date_range_clause(filters, "started_at")
	if date_clause:
		conditions.append(date_clause.replace("`started_at`", "crr.`started_at`"))
		values.extend(date_values)

	where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
	return frappe.db.sql(
		f"""
		SELECT
			crr.name,
			crr.creation,
			crr.credit_account,
			crr.run_type,
			crr.status,
			crr.expected_current_balance,
			crr.actual_current_balance,
			crr.expected_reserved_balance,
			crr.actual_reserved_balance,
			crr.expected_available_balance,
			crr.actual_available_balance,
			crr.current_difference,
			crr.reserved_difference,
			crr.available_difference,
			crr.lot_remaining_total,
			crr.lot_reserved_total,
			crr.lot_consumed_total,
			crr.lot_expired_total,
			crr.checked_accounts,
			crr.mismatch_count,
			crr.error_count,
			crr.started_at,
			crr.completed_at,
			crr.remarks
		FROM `tabCredit Reconciliation Run` crr
		{where_sql}
		ORDER BY crr.started_at DESC, crr.creation DESC
		""",
		tuple(values),
		as_dict=True,
	)