# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Gate 6 workspace, number cards, and role seeding."""

import frappe
from frappe.utils import today

STALE_MVP_DOCTYPES = {"Credit Transaction", "Credit Management Settings"}


def execute():
	from credit_management.install import seed_credit_roles

	seed_credit_roles()
	_seed_number_cards()
	_sync_workspace()


def _seed_number_cards():
	cards = [
		{
			"name": "Total Credit Accounts",
			"label": "Total Credit Accounts",
			"type": "Document Type",
			"document_type": "Credit Account",
			"function": "Count",
			"is_public": 1,
			"is_standard": 1,
			"module": "Credit Management",
			"color": "#449CF0",
		},
		{
			"name": "Active Reservations",
			"label": "Active Reservations",
			"type": "Document Type",
			"document_type": "Credit Reservation",
			"function": "Count",
			"filters_json": '[["Credit Reservation","status","=","Active"]]',
			"is_public": 1,
			"is_standard": 1,
			"module": "Credit Management",
			"color": "#29CD42",
		},
		{
			"name": "Credits Reserved",
			"label": "Credits Reserved",
			"type": "Document Type",
			"document_type": "Credit Reservation",
			"function": "Sum",
			"aggregate_function_based_on": "reserved_amount",
			"filters_json": '[["Credit Reservation","status","in",["Active","Partially Consumed"]]]',
			"is_public": 1,
			"is_standard": 1,
			"module": "Credit Management",
			"color": "#FFA00A",
		},
		{
			"name": "Credits Consumed Today",
			"label": "Credits Consumed Today",
			"type": "Document Type",
			"document_type": "Credit Ledger Entry",
			"function": "Sum",
			"aggregate_function_based_on": "amount",
			"filters_json": (
				f'[["Credit Ledger Entry","entry_type","=","CONSUME"],'
				f'["Credit Ledger Entry","creation","Between",["{today()}","{today()}"]]]'
			),
			"is_public": 1,
			"is_standard": 1,
			"module": "Credit Management",
			"color": "#EC864B",
		},
		{
			"name": "Credits Expired Today",
			"label": "Credits Expired Today",
			"type": "Document Type",
			"document_type": "Credit Ledger Entry",
			"function": "Sum",
			"aggregate_function_based_on": "amount",
			"filters_json": (
				f'[["Credit Ledger Entry","entry_type","=","EXPIRE"],'
				f'["Credit Ledger Entry","creation","Between",["{today()}","{today()}"]]]'
			),
			"is_public": 1,
			"is_standard": 1,
			"module": "Credit Management",
			"color": "#CB2929",
		},
	]

	for card in cards:
		if frappe.db.exists("Number Card", card["name"]):
			doc = frappe.get_doc("Number Card", card["name"])
			doc.update(card)
			doc.save(ignore_permissions=True)
			continue

		doc = frappe.get_doc({"doctype": "Number Card", **card})
		doc.insert(ignore_permissions=True)


def _sync_workspace():
	frappe.reload_doc("Credit Management", "workspace", "credit_management", force=True)

	if not frappe.db.exists("Workspace", "Credit Management"):
		return

	workspace = frappe.get_doc("Workspace", "Credit Management")
	workspace.links = [row for row in workspace.links if row.link_to not in STALE_MVP_DOCTYPES]
	workspace.shortcuts = [
		row for row in workspace.shortcuts if row.link_to not in STALE_MVP_DOCTYPES
	]
	workspace.save(ignore_permissions=True)

	from credit_management.workspace_content import apply_workspace_content

	apply_workspace_content(workspace)