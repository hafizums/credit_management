# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""
Gate 1.5 follow-up — drop MVP tables if still present.

Idempotent. Corrects table_exists usage for sites that ran the first patch pass.
"""

import frappe

MVP_TABLE_DOCTYPES = (
	"Credit Transaction",
	"Credit Account",
)


def execute():
	for doctype in MVP_TABLE_DOCTYPES:
		table = f"tab{doctype}"
		if frappe.db.table_exists(doctype):
			frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `{table}`")
	frappe.db.commit()