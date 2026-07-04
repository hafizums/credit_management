# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""
Scheduler entry points. Business logic is delegated to services.
"""

from credit_management.services.expiry_service import ExpiryService
from credit_management.services.reconciliation_service import ReconciliationService
from credit_management.services.reservation_service import ReservationService


def release_expired_reservations():
	"""Hourly: release active reservations past expires_at."""
	return ReservationService.release_expired_reservations()


def reconcile_recent_accounts():
	"""Hourly: reconcile accounts changed in the recent window."""
	return ReconciliationService.reconcile_recent_accounts()


def expire_credits():
	"""Daily: expire remaining amounts on Credit Expiry Lots."""
	return ExpiryService.expire_credits()


def generate_daily_credit_summary():
	"""Daily: aggregate credit metrics for dashboard/reporting."""
	return {"status": "stub", "task": "generate_daily_credit_summary"}


def retry_failed_webhooks():
	"""Periodic: retry outbound Credit Webhook Event deliveries."""
	return {"status": "stub", "task": "retry_failed_webhooks"}