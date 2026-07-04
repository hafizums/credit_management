# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Gate 7 workspace report links."""

import frappe

STALE_MVP_DOCTYPES = {"Credit Transaction", "Credit Management Settings"}

REPORT_LINKS = (
	"Credit Balance Report",
	"Credit Ledger Report",
	"Credit Usage by App",
	"Credit Usage by Owner",
	"Reservation Aging Report",
	"Expired Credits Report",
	"Reconciliation Report",
	"Top Credit Consumers",
	"Credit Grant History",
	"Credit Transfer History",
)


def execute():
	frappe.reload_doc("Credit Management", "workspace", "credit_management", force=True)

	if not frappe.db.exists("Workspace", "Credit Management"):
		return

	workspace = frappe.get_doc("Workspace", "Credit Management")
	workspace.links = [row for row in workspace.links if row.link_to not in STALE_MVP_DOCTYPES]
	workspace.shortcuts = [
		row for row in workspace.shortcuts if row.link_to not in STALE_MVP_DOCTYPES
	]

	existing_reports = {
		row.link_to
		for row in workspace.links
		if row.link_type == "Report" and row.link_to
	}

	if not any(row.label == "Reports" and row.type == "Card Break" for row in workspace.links):
		workspace.append("links", {"type": "Card Break", "label": "Reports", "link_count": len(REPORT_LINKS)})

	for report_name in REPORT_LINKS:
		if report_name in existing_reports:
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

	workspace.save(ignore_permissions=True)

	from credit_management.workspace_content import apply_workspace_content

	apply_workspace_content(workspace)