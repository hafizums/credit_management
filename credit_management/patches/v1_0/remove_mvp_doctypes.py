# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""
Gate 1.5 — Remove legacy MVP DocTypes and related database artifacts.

Idempotent: safe to run when DocTypes/tables are already absent.
"""

import frappe

MVP_DOCTYPES = (
	"Credit Transaction",
	"Credit Account",
	"Credit Management Settings",
)

MVP_TABLE_DOCTYPES = (
	"Credit Transaction",
	"Credit Account",
)


def execute():
	"""Remove MVP DocType metadata, data, and obsolete tables."""
	_delete_mvp_data()
	_delete_mvp_doctypes()
	_drop_mvp_tables()
	_cleanup_mvp_workspace()
	frappe.db.commit()
	frappe.clear_cache()


def _delete_mvp_data():
	# Child records first (Credit Transaction references Credit Account).
	if frappe.db.table_exists("Credit Transaction"):
		frappe.db.delete("Credit Transaction")

	if frappe.db.table_exists("Credit Account"):
		frappe.db.delete("Credit Account")

	# Singles DocType — remove default values stored in tabSingles.
	if frappe.db.exists("DocType", "Credit Management Settings"):
		frappe.db.delete("Singles", {"doctype": "Credit Management Settings"})


def _delete_mvp_doctypes():
	for doctype in MVP_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True)


def _drop_mvp_tables():
	for doctype in MVP_TABLE_DOCTYPES:
		table = f"tab{doctype}"
		if frappe.db.table_exists(doctype):
			frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `{table}`")


def _cleanup_mvp_workspace():
	"""Remove workspace only while MVP DocTypes still exist (idempotent)."""
	if not any(frappe.db.exists("DocType", dt) for dt in MVP_DOCTYPES):
		return
	if frappe.db.exists("Workspace", "Credit Management"):
		frappe.delete_doc("Workspace", "Credit Management", force=True, ignore_permissions=True)