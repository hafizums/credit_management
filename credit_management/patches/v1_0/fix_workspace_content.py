# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Populate workspace content blocks so shortcuts/cards render in Desk."""

import frappe

from credit_management.workspace_content import apply_workspace_content


def execute():
	frappe.reload_doc("Credit Management", "workspace", "credit_management", force=True)
	apply_workspace_content()
	frappe.clear_cache()