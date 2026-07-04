# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _

from credit_management.report_utils import credit_user_owner_filters, enforce_report_access

REPORT_NAME = "Credit Balance Report"


def execute(filters=None):
	enforce_report_access(REPORT_NAME)
	filters = filters or {}
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Credit Account"),
			"fieldname": "credit_account",
			"fieldtype": "Link",
			"options": "Credit Account",
			"width": 160,
		},
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
			"label": _("Current Balance"),
			"fieldname": "current_balance",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Reserved Balance"),
			"fieldname": "reserved_balance",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Available Balance"),
			"fieldname": "available_balance",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Data",
			"width": 140,
		},
	]


def get_data(filters):
	query_filters = dict(credit_user_owner_filters())
	field_map = {
		"owner_doctype": "account_owner_doctype",
		"owner_name": "account_owner_name",
	}
	for filter_key, fieldname in (
		("credit_type", "credit_type"),
		("status", "status"),
		("company", "company"),
	):
		if filters.get(filter_key):
			query_filters[fieldname] = filters[filter_key]
	for filter_key, fieldname in field_map.items():
		if filters.get(filter_key):
			query_filters[fieldname] = filters[filter_key]

	return frappe.get_all(
		"Credit Account",
		filters=query_filters,
		fields=[
			"name as credit_account",
			"account_owner_doctype",
			"account_owner_name",
			"credit_type",
			"current_balance",
			"reserved_balance",
			"available_balance",
			"status",
			"company",
		],
		order_by="credit_type asc, account_owner_name asc",
	)