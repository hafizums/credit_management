# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Inspect credit_management test data. Run: bench --site <site> execute credit_management.scripts.inspect_test_data.run"""

import frappe


def run():
	queries = {
		"example_accounts": (
			"SELECT COUNT(*) FROM `tabCredit Account` WHERE account_owner_name LIKE '%@example.com'"
		),
		"staging_accounts": (
			"SELECT COUNT(*) FROM `tabCredit Account` WHERE account_owner_name LIKE '%staging-load%'"
		),
		"audio_stem_ledger": (
			"SELECT COUNT(*) FROM `tabCredit Ledger Entry` "
			"WHERE source_app='audio_stem' OR idempotency_key LIKE 'audio_stem:%'"
		),
		"audio_stem_reservations": (
			"SELECT COUNT(*) FROM `tabCredit Reservation` "
			"WHERE reference_doctype='Audio Separation Job' OR idempotency_key LIKE 'audio_stem:%'"
		),
		"null_source_ledger": (
			"SELECT COUNT(*) FROM `tabCredit Ledger Entry` WHERE source_app IS NULL OR source_app=''"
		),
		"cm_source_ledger": (
			"SELECT COUNT(*) FROM `tabCredit Ledger Entry` WHERE source_app='credit_management'"
		),
		"integration_logs": "SELECT COUNT(*) FROM `tabCredit Integration Log`",
		"test_idempotency_ledger": (
			"SELECT COUNT(*) FROM `tabCredit Ledger Entry` "
			"WHERE idempotency_key LIKE 'gate%' OR idempotency_key LIKE 'm16-%' "
			"OR idempotency_key LIKE 'm17-%' OR idempotency_key LIKE 'm15-%' "
			"OR idempotency_key LIKE 'gate8-%'"
		),
	}

	summary = {label: frappe.db.sql(query)[0][0] for label, query in queries.items()}

	sample_test_accounts = frappe.db.sql(
		"""
		SELECT name, account_owner_name, credit_type, current_balance
		FROM `tabCredit Account`
		WHERE account_owner_name LIKE '%@example.com'
		   OR account_owner_name LIKE '%staging-load%'
		ORDER BY modified DESC
		LIMIT 10
		""",
		as_dict=True,
	)

	sample_real_accounts = frappe.db.sql(
		"""
		SELECT name, account_owner_name, credit_type, current_balance
		FROM `tabCredit Account`
		WHERE account_owner_name NOT LIKE '%@example.com'
		  AND account_owner_name NOT LIKE '%staging-load%'
		ORDER BY modified DESC
		LIMIT 10
		""",
		as_dict=True,
	)

	return {
		"summary": summary,
		"sample_test_accounts": sample_test_accounts,
		"sample_real_accounts": sample_real_accounts,
	}
