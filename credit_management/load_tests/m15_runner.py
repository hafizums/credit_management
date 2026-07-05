# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Milestone 15 performance and scale test suite — bench execute entry point."""

import importlib
import json
import platform
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import frappe
from frappe.utils import add_to_date, now_datetime

import credit_management.api as credit_api
from credit_management.tasks import (
	cleanup_old_integration_logs,
	expire_credits,
	generate_daily_credit_summary,
	reconcile_recent_accounts,
	release_expired_reservations,
	retry_failed_webhooks,
)

CREDIT_TYPE = "GENERAL"
LOAD_PREFIX = "m15-load"
SITE = None

REPORT_MODULES = [
	("credit_management.credit_management.report.credit_balance_report.credit_balance_report", "Credit Balance Report"),
	("credit_management.credit_management.report.credit_ledger_report.credit_ledger_report", "Credit Ledger Report"),
	("credit_management.credit_management.report.credit_usage_by_app.credit_usage_by_app", "Credit Usage by App"),
	("credit_management.credit_management.report.credit_usage_by_owner.credit_usage_by_owner", "Credit Usage by Owner"),
	("credit_management.credit_management.report.reservation_aging_report.reservation_aging_report", "Reservation Aging Report"),
	("credit_management.credit_management.report.expired_credits_report.expired_credits_report", "Expired Credits Report"),
	("credit_management.credit_management.report.reconciliation_report.reconciliation_report", "Reconciliation Report"),
	("credit_management.credit_management.report.top_credit_consumers.top_credit_consumers", "Top Credit Consumers"),
	("credit_management.credit_management.report.credit_grant_history.credit_grant_history", "Credit Grant History"),
	("credit_management.credit_management.report.credit_transfer_history.credit_transfer_history", "Credit Transfer History"),
]


def _owner(scenario, index):
	return f"{LOAD_PREFIX}-{scenario}-{index}@staging-load.test"


def _timed(label, func):
	start = time.perf_counter()
	error = None
	result = None
	try:
		result = func()
	except Exception as exc:
		error = {"type": type(exc).__name__, "message": str(exc)}
	frappe.db.commit()
	return {
		"label": label,
		"runtime_seconds": round(time.perf_counter() - start, 3),
		"result": result,
		"error": error,
	}


def _counts():
	return {
		"credit_accounts": frappe.db.count("Credit Account"),
		"ledger_entries": frappe.db.count("Credit Ledger Entry", {"docstatus": 1}),
		"reservations": frappe.db.count("Credit Reservation"),
		"integration_logs": frappe.db.count("Credit Integration Log"),
		"webhook_events": frappe.db.count("Credit Webhook Event"),
		"video_jobs": frappe.db.count("Video Generation"),
		"expiry_lots": frappe.db.count("Credit Expiry Lot"),
	}


def bulk_grant(count, amount=100):
	start = time.perf_counter()
	errors = []
	for index in range(count):
		try:
			credit_api.grant_credits(
				"User",
				_owner(count, index),
				CREDIT_TYPE,
				amount,
				idempotency_key=f"m15:grant:{count}:{index}",
				source_app="m15_load_test",
			)
		except Exception as exc:
			errors.append({"index": index, "error": str(exc), "type": type(exc).__name__})
			if len(errors) > 20:
				break
	frappe.db.commit()
	elapsed = time.perf_counter() - start
	sample_account = credit_api.get_or_create_account("User", _owner(count, 0), CREDIT_TYPE)
	recon = credit_api.reconcile_account(sample_account)
	return {
		"scenario": count,
		"runtime_seconds": round(elapsed, 3),
		"average_ms": round((elapsed / max(count, 1)) * 1000, 2),
		"errors": errors,
		"ledger_entries": frappe.db.count("Credit Ledger Entry", {"docstatus": 1}),
		"integration_logs": frappe.db.count("Credit Integration Log"),
		"reconciliation": recon.get("summary_status"),
	}


def bulk_consume(count, amount=1):
	owner = f"{LOAD_PREFIX}-consume-heavy@staging-load.test"
	credit_api.grant_credits(
		"User",
		owner,
		CREDIT_TYPE,
		count * amount + 200,
		idempotency_key=f"m15:consume-heavy:seed:{count}",
		source_app="m15_load_test",
	)
	account = credit_api.get_or_create_account("User", owner, CREDIT_TYPE)
	start = time.perf_counter()
	errors = []
	for index in range(count):
		try:
			credit_api.consume_credits(
				"User",
				owner,
				CREDIT_TYPE,
				amount,
				idempotency_key=f"m15:consume:{count}:{index}",
				source_app="m15_load_test",
			)
		except Exception as exc:
			errors.append({"index": index, "error": str(exc), "type": type(exc).__name__})
			if len(errors) > 20:
				break
	# idempotency replay (separate key from loop)
	try:
		idem_key = f"m15:consume:idempotent:{count}"
		first = credit_api.consume_credits(
			"User",
			owner,
			CREDIT_TYPE,
			amount,
			idempotency_key=idem_key,
			source_app="m15_load_test",
		)
		second = credit_api.consume_credits(
			"User",
			owner,
			CREDIT_TYPE,
			amount,
			idempotency_key=idem_key,
			source_app="m15_load_test",
		)
		if not second.get("idempotent_replay"):
			errors.append({"index": "idempotent", "error": "duplicate consume did not replay", "type": "IdempotencyError"})
	except Exception as exc:
		errors.append({"index": "idempotent", "error": str(exc), "type": type(exc).__name__})
	frappe.db.commit()
	balance = credit_api.get_balance("User", owner, CREDIT_TYPE)
	recon = credit_api.reconcile_account(account)
	elapsed = time.perf_counter() - start
	return {
		"scenario": count,
		"runtime_seconds": round(elapsed, 3),
		"average_ms": round((elapsed / max(count, 1)) * 1000, 2),
		"errors": errors,
		"final_balance": balance,
		"negative_balance": balance["current_balance"] < 0,
		"reconciliation": recon.get("summary_status"),
	}


def _thread_reserve(job_name):
	frappe.init(site=SITE)
	frappe.connect()
	frappe.set_user("Administrator")
	out = {"job": job_name, "ok": False}
	try:
		from dummy_website.services.video_job_service import VideoJobService

		job = frappe.get_doc("Video Generation", job_name)
		VideoJobService.reserve_before_provider(job)
		frappe.db.commit()
		out["ok"] = True
		out["reservation"] = job.credit_reservation
	except frappe.QueryDeadlockError as exc:
		frappe.db.rollback()
		out.update({"error": str(exc), "error_type": "QueryDeadlockError"})
	except frappe.QueryTimeoutError as exc:
		frappe.db.rollback()
		out.update({"error": str(exc), "error_type": "QueryTimeoutError"})
	except Exception as exc:
		frappe.db.rollback()
		out.update({"error": str(exc), "error_type": type(exc).__name__})
	finally:
		frappe.destroy()
	return out


def concurrent_reservations(worker_count, reserve_amount=5):
	from dummy_website.services import credit_integration
	from dummy_website.services.video_job_service import VideoJobService

	credit_integration.ensure_ai_video_credit_type()
	owner = f"{LOAD_PREFIX}-reserve-heavy@staging-load.test"
	credit_api.grant_credits(
		"User",
		owner,
		"AI_VIDEO",
		worker_count * reserve_amount + 500,
		idempotency_key=f"m15:reserve-heavy:{worker_count}",
		source_app="m15_load_test",
	)
	jobs = []
	for index in range(worker_count):
		job = VideoJobService.create_job(
			f"m15 concurrent reserve {worker_count}-{index}",
			owner_user=owner,
			duration=5,
		)
		jobs.append(job.name)
	frappe.db.commit()

	start = time.perf_counter()
	results = []
	with ThreadPoolExecutor(max_workers=worker_count, initializer=_set_site, initargs=(frappe.local.site,)) as pool:
		futures = [pool.submit(_thread_reserve, name) for name in jobs]
		for future in as_completed(futures):
			results.append(future.result())
	elapsed = time.perf_counter() - start

	account = credit_api.get_or_create_account("User", owner, "AI_VIDEO")
	balance = credit_api.get_balance("User", owner, "AI_VIDEO")
	recon = credit_api.reconcile_account(account)
	return {
		"scenario": worker_count,
		"runtime_seconds": round(elapsed, 3),
		"successful_reservations": sum(1 for row in results if row.get("ok")),
		"blocked_or_failed": sum(1 for row in results if not row.get("ok")),
		"deadlocks": sum(1 for row in results if row.get("error_type") == "QueryDeadlockError"),
		"lock_timeouts": sum(1 for row in results if row.get("error_type") == "QueryTimeoutError"),
		"errors_sample": [row for row in results if not row.get("ok")][:5],
		"final_reserved_balance": balance["reserved_balance"],
		"final_available_balance": balance["available_balance"],
		"negative_available": balance["available_balance"] < 0,
		"reconciliation": recon.get("summary_status"),
	}


def _set_site(site):
	global SITE
	SITE = site


def run_reports():
	report_results = []
	for module_path, title in REPORT_MODULES:
		start = time.perf_counter()
		error = None
		rows = 0
		cols = 0
		try:
			module = importlib.import_module(module_path)
			columns, data = module.execute({})
			cols = len(columns or [])
			rows = len(data or [])
		except Exception as exc:
			error = {"type": type(exc).__name__, "message": str(exc)}
		report_results.append(
			{
				"report": title,
				"runtime_seconds": round(time.perf_counter() - start, 3),
				"columns": cols,
				"rows": rows,
				"error": error,
			}
		)
	return report_results


def index_review():
	queries = {
		"ledger_by_account": (
			"EXPLAIN SELECT name FROM `tabCredit Ledger Entry` "
			"WHERE credit_account=%s AND docstatus=1 ORDER BY creation ASC LIMIT 100",
			(credit_api.get_or_create_account("User", _owner(100, 0), CREDIT_TYPE),),
		),
		"reservation_by_account": (
			"EXPLAIN SELECT name FROM `tabCredit Reservation` WHERE credit_account=%s AND status='Active'",
			(credit_api.get_or_create_account("User", _owner(100, 0), CREDIT_TYPE),),
		),
		"integration_log_source": (
			"EXPLAIN SELECT name FROM `tabCredit Integration Log` WHERE source_app=%s ORDER BY creation DESC LIMIT 50",
			("m15_load_test",),
		),
	}
	explains = {}
	for key, (sql, params) in queries.items():
		try:
			explains[key] = frappe.db.sql(sql, params, as_dict=True)
		except Exception as exc:
			explains[key] = {"error": str(exc)}

	indexes = {}
	for table in [
		"tabCredit Ledger Entry",
		"tabCredit Account",
		"tabCredit Reservation",
		"tabCredit Integration Log",
		"tabCredit Webhook Event",
		"tabCredit Expiry Lot",
		"tabCredit Reconciliation Run",
	]:
		try:
			indexes[table] = frappe.db.sql(f"SHOW INDEX FROM `{table}`", as_dict=True)
		except Exception as exc:
			indexes[table] = {"error": str(exc)}
	return {"explains": explains, "indexes": indexes}


def deadlock_review():
	rows = frappe.db.sql(
		"""
		SELECT name, creation, error
		FROM `tabError Log`
		WHERE creation >= %s
		AND (error LIKE %s OR error LIKE %s OR error LIKE %s)
		ORDER BY creation DESC
		LIMIT 50
		""",
		(
			add_to_date(now_datetime(), days=-1),
			"%Deadlock%",
			"%1213%",
			"%Lock wait%",
		),
		as_dict=True,
	)
	return {
		"error_log_matches": len(rows),
		"sample": rows[:5],
	}


def integration_log_cleanup_test():
	dry = cleanup_old_integration_logs(dry_run=True)
	# Create disposable old log and delete on load site only
	from credit_management.services.integration_log_service import IntegrationLogService

	old_name = IntegrationLogService.log_success(
		"grant_credits",
		request={"m15": "disposable"},
		response={"ok": True},
		source_app="m15_load_test",
	)
	frappe.db.set_value(
		"Credit Integration Log",
		old_name,
		"creation",
		add_to_date(now_datetime(), days=-400),
	)
	frappe.db.commit()
	frappe.db.set_value("Credit Settings", "Credit Settings", "audit_log_retention_days", 365)
	actual = cleanup_old_integration_logs(dry_run=False)
	return {"dry_run": dry, "actual_cleanup": actual}


def _git_commit(app_path):
	try:
		return subprocess.check_output(["git", "-C", app_path, "rev-parse", "--short", "HEAD"], text=True).strip()
	except Exception:
		return "unknown"


def run():
	global SITE
	SITE = frappe.local.site
	frappe.set_user("Administrator")
	settings = frappe.get_single("Credit Settings")

	results = {
		"test_site": SITE,
		"site_choice_reason": "Dedicated disposable load-test site isolated from jomveo production pilot",
		"environment": {
			"frappe_version": frappe.__version__,
			"python_version": platform.python_version(),
			"mariadb_version": frappe.db.sql("select version()")[0][0],
			"installed_apps": frappe.get_installed_apps(),
			"credit_app_commit": _git_commit("/home/hafiz/frappe-bench/apps/credit_management"),
			"dummy_website_commit": _git_commit("/home/hafiz/frappe-bench/apps/dummy_website"),
			"rest_enabled": settings.enable_rest_api,
			"webhooks_enabled": settings.enable_webhooks,
			"integration_logs_enabled": settings.enable_integration_logs,
		},
		"baseline_counts": _counts(),
	}

	grant_results = {}
	for count in (100, 1000):
		grant_results[str(count)] = bulk_grant(count)
	if grant_results["1000"]["runtime_seconds"] < 180:
		grant_results["5000"] = bulk_grant(5000)
	else:
		grant_results["5000"] = {"skipped": True, "reason": "1000 grants exceeded 180s threshold"}
	results["bulk_grant"] = grant_results

	consume_results = {}
	for count in (100, 1000):
		consume_results[str(count)] = bulk_consume(count)
	balance_after_1000 = consume_results["1000"]["final_balance"]["current_balance"]
	if consume_results["1000"]["runtime_seconds"] < 120 and balance_after_1000 > 5000:
		consume_results["5000"] = bulk_consume(5000)
	else:
		consume_results["5000"] = {
			"skipped": True,
			"reason": "time or balance threshold",
			"balance_after_1000": balance_after_1000,
		}
	results["bulk_consume"] = consume_results

	reserve_results = {}
	for workers in (10, 25, 50):
		reserve_results[str(workers)] = concurrent_reservations(workers)
	results["reservation_concurrency"] = reserve_results

	from dummy_website.load_tests.video_concurrency import run_video_lifecycle_load

	video_owner = f"{LOAD_PREFIX}-video-heavy@staging-load.test"
	credit_api.grant_credits(
		"User",
		video_owner,
		"AI_VIDEO",
		5000,
		idempotency_key="m15:video-heavy:seed",
		source_app="m15_load_test",
	)
	results["video_lifecycle"] = run_video_lifecycle_load(SITE, video_owner, workers=10)
	video_account = credit_api.get_or_create_account("User", video_owner, "AI_VIDEO")
	results["video_lifecycle"]["reconciliation"] = credit_api.reconcile_account(video_account).get(
		"summary_status"
	)

	heavy_account = credit_api.get_or_create_account("User", _owner(100, 0), CREDIT_TYPE)
	recon_account = _timed("reconcile_account", lambda: credit_api.reconcile_account(heavy_account))
	recon_recent = _timed("reconcile_recent_accounts", reconcile_recent_accounts)
	recon_all = _timed("reconcile_all_accounts", credit_api.reconcile_all_accounts)
	results["reconciliation_scale"] = {
		"reconcile_account": recon_account,
		"reconcile_recent_accounts": recon_recent,
		"reconcile_all_accounts": recon_all,
	}

	results["report_scale"] = run_reports()
	results["scheduler_scale"] = {
		"release_expired_reservations": _timed("release_expired", release_expired_reservations),
		"expire_credits": _timed("expire_credits", expire_credits),
		"reconcile_recent_accounts": _timed("reconcile_recent", reconcile_recent_accounts),
		"generate_daily_credit_summary": _timed("daily_summary", generate_daily_credit_summary),
		"retry_failed_webhooks": _timed("retry_webhooks", retry_failed_webhooks),
		"cleanup_old_integration_logs": _timed(
			"cleanup_logs_dry_run",
			lambda: cleanup_old_integration_logs(dry_run=True),
		),
	}

	results["integration_log_growth"] = integration_log_cleanup_test()
	results["database_index_review"] = index_review()
	results["deadlock_review"] = deadlock_review()
	results["final_counts"] = _counts()
	results["data_volume"] = results["final_counts"]

	return results


if __name__ == "__main__":
	print(json.dumps(run(), default=str, indent=2))