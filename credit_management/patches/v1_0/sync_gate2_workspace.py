# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe

STALE_MVP_DOCTYPES = {"Credit Transaction", "Credit Management Settings"}


def execute():
	if not frappe.db.exists("Workspace", "Credit Management"):
		return

	frappe.reload_doc("Credit Management", "workspace", "credit_management", force=True)

	workspace = frappe.get_doc("Workspace", "Credit Management")
	workspace.links = [row for row in workspace.links if row.link_to not in STALE_MVP_DOCTYPES]
	workspace.shortcuts = [
		row for row in workspace.shortcuts if row.link_to not in STALE_MVP_DOCTYPES
	]
	workspace.save(ignore_permissions=True)