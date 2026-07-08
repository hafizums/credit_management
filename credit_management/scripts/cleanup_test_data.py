# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""
Remove credit_management test data from a site.

Preview:
  bench --site <site> execute credit_management.scripts.cleanup_test_data.run

Full dev reset (keeps Credit Type + Credit Settings, deletes all accounts/ledger/logs):
  bench --site <site> execute credit_management.scripts.cleanup_test_data.run --kwargs '{"dry_run": false, "mode": "full"}'

Safe mode (example.com owners + integration logs only):
  bench --site <site> execute credit_management.scripts.cleanup_test_data.run --kwargs '{"dry_run": false, "mode": "safe"}'
"""

from __future__ import annotations

import frappe
from frappe.utils import cint

# Delete child rows first, then parents.
_PURGE_DOCTYPES = (
	"Credit Reservation Lot Allocation",
	"Credit Reservation",
	"Credit Ledger Entry",
	"Credit Grant",
	"Credit Transfer",
	"Credit Expiry Lot",
	"Credit Reconciliation Run",
	"Credit Webhook Event",
	"Credit Integration Log",
	"Credit Account",
)

_TEST_OWNER_SQL = """
	account_owner_name LIKE %s
	OR account_owner_name LIKE %s
	OR account_owner_name LIKE 'gate%'
	OR account_owner_name LIKE 'm1%'
	OR account_owner_name LIKE 'credit-user-%'
	OR account_owner_name LIKE 'credit-manager-%'
	OR account_owner_name LIKE 'pilot-video-%'
	OR account_owner_name LIKE 'all-%'
	OR account_owner_name LIKE 'clean-%'
	OR account_owner_name LIKE 'lot-%'
	OR account_owner_name LIKE 'negative-%'
	OR account_owner_name LIKE 'available-%'
	OR account_owner_name LIKE 'reserved-%'
	OR account_owner_name LIKE 'current-%'
	OR account_owner_name LIKE 'run-record-%'
"""


def _count_table(doctype: str) -> int:
	return cint(frappe.db.count(doctype))


def _preview_counts() -> dict:
	return {doctype: _count_table(doctype) for doctype in _PURGE_DOCTYPES}


def _test_account_names() -> list[str]:
	return frappe.db.sql(
		f"""
		SELECT name
		FROM `tabCredit Account`
		WHERE {_TEST_OWNER_SQL}
		""",
		("%@example.com", "%staging-load%"),
		pluck=True,
	)


def _delete_for_accounts(account_names: list[str], dry_run: bool) -> dict:
	if not account_names:
		return {"accounts": 0}

	placeholders = ", ".join(["%s"] * len(account_names))
	params = tuple(account_names)
	deleted = {"accounts": len(account_names)}

	if dry_run:
		for doctype in _PURGE_DOCTYPES[:-1]:
			if doctype == "Credit Reservation Lot Allocation":
				deleted[doctype] = cint(
					frappe.db.sql(
						f"""
						SELECT COUNT(*)
						FROM `tabCredit Reservation Lot Allocation` cra
						INNER JOIN `tabCredit Reservation` cr ON cr.name = cra.parent
						WHERE cr.credit_account IN ({placeholders})
						""",
						params,
					)[0][0]
				)
			else:
				deleted[doctype] = cint(
					frappe.db.sql(
						f"SELECT COUNT(*) FROM `tab{doctype}` WHERE credit_account IN ({placeholders})",
						params,
					)[0][0]
				)
		return deleted

	frappe.db.sql(
		f"""
		DELETE cra FROM `tabCredit Reservation Lot Allocation` cra
		INNER JOIN `tabCredit Reservation` cr ON cr.name = cra.parent
		WHERE cr.credit_account IN ({placeholders})
		""",
		params,
	)
	frappe.db.sql(
		f"DELETE FROM `tabCredit Reservation` WHERE credit_account IN ({placeholders})",
		params,
	)
	frappe.db.sql(
		f"DELETE FROM `tabCredit Ledger Entry` WHERE credit_account IN ({placeholders})",
		params,
	)
	frappe.db.sql(
		f"DELETE FROM `tabCredit Grant` WHERE credit_account IN ({placeholders})",
		params,
	)
	frappe.db.sql(
		f"""
		DELETE FROM `tabCredit Transfer`
		WHERE from_credit_account IN ({placeholders})
		   OR to_credit_account IN ({placeholders})
		""",
		params + params,
	)
	frappe.db.sql(
		f"DELETE FROM `tabCredit Expiry Lot` WHERE credit_account IN ({placeholders})",
		params,
	)
	frappe.db.sql(
		f"DELETE FROM `tabCredit Account` WHERE name IN ({placeholders})",
		params,
	)
	frappe.db.commit()
	return deleted


def _purge_all(dry_run: bool) -> dict:
	before = _preview_counts()
	if dry_run:
		return {"dry_run": True, "before": before, "deleted": before}

	deleted = {}
	for doctype in _PURGE_DOCTYPES:
		count = _count_table(doctype)
		frappe.db.sql(f"DELETE FROM `tab{doctype}`")
		deleted[doctype] = count
	frappe.db.commit()
	return {"dry_run": False, "before": before, "deleted": deleted}


def _delete_test_users(dry_run: bool) -> dict:
	names = frappe.db.sql(
		"""
		SELECT name
		FROM `tabUser`
		WHERE name LIKE %s
		   OR name LIKE %s
		   OR name LIKE 'gate%%'
		   OR name LIKE 'm16-%%'
		   OR name LIKE 'm17-%%'
		   OR name LIKE 'gate8-%%'
		   OR name LIKE 'audio-user-%%'
		   OR name LIKE 'audio-limit-%%'
		   OR name LIKE 'credit-user-%%'
		   OR name LIKE 'credit-manager-%%'
		   OR name LIKE 'pilot-video-%%'
		""",
		("%@example.com", "%staging-load%"),
		pluck=True,
	)
	if dry_run:
		return {"eligible_users": len(names), "deleted_users": 0}

	deleted = 0
	for name in names:
		if name in ("Administrator", "Guest"):
			continue
		if frappe.db.exists("User", name):
			frappe.delete_doc("User", name, force=1, ignore_permissions=True)
			deleted += 1
	frappe.db.commit()
	return {"eligible_users": len(names), "deleted_users": deleted}


def run(
	dry_run: bool = True,
	mode: str = "safe",
	delete_test_users: bool = True,
):
	"""Clean credit_management test data.

	modes:
	  safe — test-pattern credit accounts + all integration logs
	  full — wipe all credit accounts, ledger rows, reservations, and logs
	"""
	frappe.only_for("System Manager")
	frappe.set_user("Administrator")

	mode = (mode or "safe").lower()
	result = {"mode": mode, "dry_run": bool(dry_run), "before": _preview_counts()}

	if mode == "full":
		result["purge"] = _purge_all(dry_run=dry_run)
	elif mode == "safe":
		account_names = _test_account_names()
		result["test_accounts"] = len(account_names)
		result["account_cleanup"] = _delete_for_accounts(account_names, dry_run=dry_run)

		log_count = _count_table("Credit Integration Log")
		result["integration_logs"] = {"eligible": log_count, "deleted": 0 if dry_run else log_count}
		if not dry_run and log_count:
			frappe.db.sql("DELETE FROM `tabCredit Integration Log`")
			frappe.db.commit()
			result["integration_logs"]["deleted"] = log_count
	else:
		frappe.throw(f"Unsupported cleanup mode: {mode}")

	if delete_test_users:
		result["users"] = _delete_test_users(dry_run=dry_run)

	if not dry_run:
		from credit_management.install import seed_defaults

		seed_defaults()

	result["after"] = _preview_counts()
	return result
