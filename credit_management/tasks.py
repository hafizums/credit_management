# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""
Scheduler entry points. Business logic will be delegated to services from Gate 3+.
"""


def release_expired_reservations():
	"""Hourly: release active reservations past expires_at."""
	return {"status": "stub", "task": "release_expired_reservations"}


def reconcile_recent_accounts():
	"""Hourly: reconcile accounts changed in the recent window."""
	return {"status": "stub", "task": "reconcile_recent_accounts"}


def expire_credits():
	"""Daily: expire remaining amounts on Credit Expiry Lots."""
	return {"status": "stub", "task": "expire_credits"}


def generate_daily_credit_summary():
	"""Daily: aggregate credit metrics for dashboard/reporting."""
	return {"status": "stub", "task": "generate_daily_credit_summary"}


def retry_failed_webhooks():
	"""Periodic: retry outbound Credit Webhook Event deliveries."""
	return {"status": "stub", "task": "retry_failed_webhooks"}