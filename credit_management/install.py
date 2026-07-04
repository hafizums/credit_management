# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe


def after_install():
	if not frappe.db.exists("DocType", "Credit Management Settings"):
		return

	settings = frappe.get_single("Credit Management Settings")
	if settings.is_new():
		settings.save(ignore_permissions=True)