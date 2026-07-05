# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Canonical Credit Management workspace Editor.js content blocks."""

import json

METRIC_NUMBER_CARDS = (
	"Total Credit Accounts",
	"Active Reservations",
	"Credits Consumed Today",
	"Credits Reserved",
	"Credits Expired Today",
	"Failed Webhook Events",
	"Recent Reconciliation Mismatches",
	"Low Balance Accounts",
)

SHORTCUT_NAMES = (
	"Credit Account",
	"Credit Ledger Entry",
	"Credit Reservation",
	"Credit Grant",
	"Credit Expiry Lot",
	"Credit Transfer",
	"Credit Reconciliation Run",
	"Credit Integration Log",
	"Credit Webhook Event",
	"Credit Settings",
	"Credit Admin Tools",
)


def build_workspace_content():
	"""Build Frappe workspace content JSON referencing child-table widgets."""
	blocks = [
		{
			"id": "cm-header",
			"type": "header",
			"data": {
				"text": '<span class="h4"><b>Credit Management Platform</b></span>',
				"col": 12,
			},
		},
		{
			"id": "cm-desc",
			"type": "paragraph",
			"data": {
				"text": "Ledger, reservations, expiry lots, transfers, reconciliation, reports, and admin tools.",
				"col": 12,
			},
		},
		{
			"id": "cm-metrics-header",
			"type": "header",
			"data": {"text": '<span class="h4"><b>Metrics</b></span>', "col": 12},
		},
	]

	for idx, name in enumerate(METRIC_NUMBER_CARDS):
		blocks.append(
			{
				"id": f"cm-nc-{idx}",
				"type": "number_card",
				"data": {"number_card_name": name, "col": 4},
			}
		)

	blocks.append(
		{
			"id": "cm-shortcuts-header",
			"type": "header",
			"data": {"text": '<span class="h4"><b>Shortcuts</b></span>', "col": 12},
		}
	)

	for idx, name in enumerate(SHORTCUT_NAMES):
		blocks.append(
			{
				"id": f"cm-sc-{idx}",
				"type": "shortcut",
				"data": {"shortcut_name": name, "col": 3},
			}
		)

	blocks.append({"id": "cm-spacer-1", "type": "spacer", "data": {"col": 12}})
	blocks.append(
		{
			"id": "cm-modules-header",
			"type": "header",
			"data": {"text": '<span class="h4"><b>Modules</b></span>', "col": 12},
		}
	)

	for idx, card_name in enumerate(
		("Setup", "Accounts & Ledger", "Operations", "Reports", "Admin Tools")
	):
		blocks.append(
			{
				"id": f"cm-card-{idx}",
				"type": "card",
				"data": {"card_name": card_name, "col": 4},
			}
		)

	blocks.append(
		{
			"id": "cm-quick-header",
			"type": "header",
			"data": {"text": '<span class="h4"><b>Recent Activity</b></span>', "col": 12},
		}
	)
	blocks.append(
		{
			"id": "cm-ql-0",
			"type": "quick_list",
			"data": {"quick_list_name": "Recent Transfers", "col": 12},
		}
	)

	return json.dumps(blocks)


def apply_workspace_content(workspace=None):
	content = build_workspace_content()
	if workspace is None:
		import frappe

		if not frappe.db.exists("Workspace", "Credit Management"):
			return None
		workspace = frappe.get_doc("Workspace", "Credit Management")

	workspace.content = content
	workspace.save(ignore_permissions=True)
	return workspace