# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe


def after_install():
	seed_defaults()


def before_tests():
	seed_defaults()


def seed_defaults():
	seed_credit_type_general()
	seed_credit_settings()


def seed_credit_type_general():
	if not frappe.db.exists("DocType", "Credit Type"):
		return

	if frappe.db.exists("Credit Type", "GENERAL"):
		return

	doc = frappe.get_doc(
		{
			"doctype": "Credit Type",
			"credit_type_code": "GENERAL",
			"title": "General",
			"description": "Default general-purpose credit type",
			"decimal_precision": 2,
			"allow_negative_balance": 0,
			"is_active": 1,
		}
	)
	doc.insert(ignore_permissions=True)


def seed_credit_settings():
	if not frappe.db.exists("DocType", "Credit Settings"):
		return

	settings = frappe.get_single("Credit Settings")
	settings.allow_negative_balance_default = 0
	settings.enable_credit_expiry = 0
	settings.default_reservation_timeout_minutes = 30
	settings.enable_rest_api = 0
	settings.enable_webhooks = 0
	settings.audit_log_retention_days = 365
	settings.balance_reconciliation_enabled = 0
	settings.low_balance_threshold_default = 0
	settings.save(ignore_permissions=True)