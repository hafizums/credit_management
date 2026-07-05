# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Milestone 17 admin UX — number cards, workspace shortcuts, admin page."""

import frappe

STALE_MVP_DOCTYPES = {"Credit Transaction", "Credit Management Settings"}

ADMIN_DOCTYPE_LINKS = (
	"Credit Reconciliation Run",
	"Credit Integration Log",
	"Credit Webhook Event",
)

ADMIN_REPORT_LINKS = (
	"Reservation Aging Report",
	"Reconciliation Report",
	"Top Credit Consumers",
)

OPERATIONS_SHORTCUTS = (
	("Credit Reconciliation Run", "Credit Reconciliation Run", "DocType", "Red"),
	("Credit Integration Log", "Credit Integration Log", "DocType", "Orange"),
	("Credit Webhook Event", "Credit Webhook Event", "DocType", "Pink"),
	("Credit Admin Tools", "credit-admin-tools", "Page", "Blue"),
)


def execute():
	frappe.reload_doc("Credit Management", "page", "credit_admin_tools", force=True)
	_seed_number_cards()
	_sync_workspace()


def _seed_number_cards():
	cards = [
		{
			"name": "Failed Webhook Events",
			"label": "Failed Webhook Events",
			"type": "Document Type",
			"document_type": "Credit Webhook Event",
			"function": "Count",
			"filters_json": '[["Credit Webhook Event","status","=","Failed"]]',
			"is_public": 1,
			"is_standard": 1,
			"module": "Credit Management",
			"color": "#CB2929",
		},
		{
			"name": "Recent Reconciliation Mismatches",
			"label": "Recent Reconciliation Mismatches",
			"type": "Document Type",
			"document_type": "Credit Reconciliation Run",
			"function": "Count",
			"filters_json": '[["Credit Reconciliation Run","status","=","Mismatch"]]',
			"is_public": 1,
			"is_standard": 1,
			"module": "Credit Management",
			"color": "#FFA00A",
		},
		{
			"name": "Low Balance Accounts",
			"label": "Low Balance Accounts",
			"type": "Custom",
			"method": "credit_management.admin_ux.get_low_balance_account_count",
			"function": "Count",
			"is_public": 1,
			"is_standard": 1,
			"module": "Credit Management",
			"color": "#EC864B",
		},
	]

	for card in cards:
		if frappe.db.exists("Number Card", card["name"]):
			doc = frappe.get_doc("Number Card", card["name"])
			doc.update(card)
			doc.save(ignore_permissions=True)
			continue
		frappe.get_doc({"doctype": "Number Card", **card}).insert(ignore_permissions=True)


def _sync_workspace():
	frappe.reload_doc("Credit Management", "workspace", "credit_management", force=True)
	if not frappe.db.exists("Workspace", "Credit Management"):
		return

	workspace = frappe.get_doc("Workspace", "Credit Management")
	workspace.links = [row for row in workspace.links if row.link_to not in STALE_MVP_DOCTYPES]
	workspace.shortcuts = [
		row for row in workspace.shortcuts if row.link_to not in STALE_MVP_DOCTYPES
	]

	linked_doctypes = {
		row.link_to for row in workspace.links if row.link_type == "DocType" and row.link_to
	}
	linked_reports = {
		row.link_to for row in workspace.links if row.link_type == "Report" and row.link_to
	}
	shortcut_targets = {row.link_to for row in workspace.shortcuts if row.link_to}

	if not any(row.label == "Operations" and row.type == "Card Break" for row in workspace.links):
		workspace.append(
			"links",
			{"type": "Card Break", "label": "Operations", "link_count": len(ADMIN_DOCTYPE_LINKS)},
		)

	for label in ADMIN_DOCTYPE_LINKS:
		if label in linked_doctypes:
			continue
		workspace.append(
			"links",
			{"type": "Link", "label": label, "link_type": "DocType", "link_to": label, "onboard": 0},
		)

	for report_name in ADMIN_REPORT_LINKS:
		if report_name in linked_reports:
			continue
		workspace.append(
			"links",
			{
				"type": "Link",
				"label": report_name,
				"link_type": "Report",
				"link_to": report_name,
				"is_query_report": 1,
			},
		)

	if not any(row.label == "Admin Tools" and row.type == "Card Break" for row in workspace.links):
		workspace.append("links", {"type": "Card Break", "label": "Admin Tools", "link_count": 1})

	if "credit-admin-tools" not in shortcut_targets and not any(
		row.link_to == "credit-admin-tools" for row in workspace.links
	):
		workspace.append(
			"links",
			{
				"type": "Link",
				"label": "Credit Admin Tools",
				"link_type": "Page",
				"link_to": "credit-admin-tools",
			},
		)

	for label, link_to, link_type, color in OPERATIONS_SHORTCUTS:
		if link_to in shortcut_targets:
			continue
		workspace.append(
			"shortcuts",
			{
				"type": link_type,
				"label": label,
				"link_to": link_to,
				"color": color,
				"doc_view": "List",
			},
		)
		shortcut_targets.add(link_to)

	workspace.number_cards = []
	for card_name in (
		"Total Credit Accounts",
		"Active Reservations",
		"Credits Consumed Today",
		"Credits Reserved",
		"Credits Expired Today",
		"Failed Webhook Events",
		"Recent Reconciliation Mismatches",
		"Low Balance Accounts",
	):
		workspace.append("number_cards", {"label": card_name, "number_card_name": card_name})

	workspace.save(ignore_permissions=True)

	from credit_management.workspace_content import apply_workspace_content

	apply_workspace_content(workspace)