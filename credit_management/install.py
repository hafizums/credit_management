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
	settings.reload()
	settings.allow_negative_balance_default = 0
	settings.enable_credit_expiry = 0
	settings.default_reservation_timeout_minutes = 30
	settings.enable_rest_api = 0
	settings.enable_webhooks = 0
	settings.audit_log_retention_days = 365
	settings.balance_reconciliation_enabled = 0
	settings.low_balance_threshold_default = 0
	settings.save(ignore_permissions=True)


def gate_3_1_api_smoke():
	"""Grant → reserve → release smoke check for public reservation API."""
	import credit_management.api as api

	owner_doctype = "User"
	owner_name = "gate3-api-smoke"
	credit_type = "GENERAL"
	reserve_key = "gate3-api-smoke:reserve"
	release_key = "gate3-api-smoke:release"

	seed_defaults()
	api.grant_credits(owner_doctype, owner_name, credit_type, 10, idempotency_key="gate3-api-smoke:grant")

	reserve = api.reserve_credits(
		owner_doctype=owner_doctype,
		owner_name=owner_name,
		credit_type=credit_type,
		amount=1,
		idempotency_key=reserve_key,
	)
	release = api.release_reservation(
		reservation_name=reserve["reservation"],
		reason="gate 3.1 smoke cleanup",
		idempotency_key=release_key,
	)

	return {
		"reserve": reserve,
		"release": release,
		"balance": api.get_balance(owner_doctype, owner_name, credit_type),
	}