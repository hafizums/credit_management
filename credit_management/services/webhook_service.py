# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Outbound webhook event tracking and retries."""

import json

import frappe
from frappe import _
from frappe.integrations.utils import make_post_request
from frappe.utils import add_to_date, cstr, now_datetime

from credit_management.services.integration_log_service import (
	MAX_JSON_LENGTH,
	IntegrationLogService,
)

WEBHOOK_EVENT_TYPES = frozenset(
	{
		"credit.granted",
		"credit.consumed",
		"credit.reserved",
		"credit.reservation_consumed",
		"credit.reservation_released",
		"credit.refunded",
		"credit.adjusted",
		"credit.transferred",
		"credit.expired",
		"credit.reconciliation_completed",
		"credit.low_balance",
	}
)


class WebhookService:
	@staticmethod
	def is_enabled():
		if not frappe.db.exists("DocType", "Credit Webhook Event"):
			return False
		return bool(frappe.get_single("Credit Settings").enable_webhooks)

	@staticmethod
	def sanitize_payload(payload):
		return IntegrationLogService.sanitize_payload(payload)

	@staticmethod
	def _serialize_payload(payload):
		sanitized = WebhookService.sanitize_payload(payload)
		text = json.dumps(sanitized, default=str)
		if len(text) > MAX_JSON_LENGTH:
			return text[:MAX_JSON_LENGTH] + "...[truncated]"
		return text

	@staticmethod
	def _settings():
		return frappe.get_single("Credit Settings")

	@staticmethod
	def emit_event(
		event_type,
		payload,
		reference_doctype=None,
		reference_name=None,
		source_app=None,
		idempotency_key=None,
	):
		if not WebhookService.is_enabled():
			return None
		if event_type not in WEBHOOK_EVENT_TYPES:
			frappe.throw(_("Unsupported webhook event type: {0}").format(event_type))

		settings = WebhookService._settings()
		target_url = (settings.webhook_target_url or "").strip()
		max_retries = int(settings.webhook_max_retries or 5)

		if reference_name and not reference_doctype:
			reference_name = None

		doc = frappe.get_doc(
			{
				"doctype": "Credit Webhook Event",
				"event_type": event_type,
				"status": "Pending",
				"payload_json": WebhookService._serialize_payload(payload),
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"source_app": source_app,
				"idempotency_key": idempotency_key,
				"target_url": target_url or None,
				"max_retries": max_retries,
				"retry_count": 0,
			}
		)
		doc.insert(ignore_permissions=True)

		if target_url:
			delivered, error = WebhookService._attempt_delivery(doc)
			if delivered:
				WebhookService._mark_delivered(doc)
			else:
				WebhookService._mark_failed(doc, error, schedule_retry=True)
		return doc.name

	@staticmethod
	def retry_failed_webhooks():
		if not frappe.db.exists("DocType", "Credit Webhook Event"):
			return {
				"status": "completed",
				"attempted": 0,
				"delivered": 0,
				"failed": 0,
				"skipped": 0,
				"errors": 0,
			}

		settings = WebhookService._settings()
		target_url = (settings.webhook_target_url or "").strip()
		now = now_datetime()
		summary = {
			"status": "completed",
			"attempted": 0,
			"delivered": 0,
			"failed": 0,
			"skipped": 0,
			"errors": 0,
		}

		events = frappe.get_all(
			"Credit Webhook Event",
			filters={"status": ["in", ["Pending", "Failed"]]},
			fields=["name", "status", "retry_count", "max_retries", "next_retry_at"],
			order_by="creation asc",
			limit=500,
		)

		for row in events:
			if row.status in {"Delivered", "Cancelled"}:
				summary["skipped"] += 1
				continue

			if row.next_retry_at and row.next_retry_at > now:
				summary["skipped"] += 1
				continue

			if int(row.retry_count or 0) >= int(row.max_retries or 5):
				summary["skipped"] += 1
				continue

			summary["attempted"] += 1
			doc = frappe.get_doc("Credit Webhook Event", row.name)

			if not target_url:
				WebhookService._mark_failed(
					doc,
					"No webhook target URL configured",
					schedule_retry=False,
				)
				summary["failed"] += 1
				continue

			try:
				delivered, error = WebhookService._attempt_delivery(doc)
				if delivered:
					WebhookService._mark_delivered(doc)
					summary["delivered"] += 1
				else:
					WebhookService._mark_failed(doc, error, schedule_retry=True)
					summary["failed"] += 1
			except Exception as exc:
				WebhookService._mark_failed(doc, cstr(exc), schedule_retry=True)
				summary["errors"] += 1
				summary["failed"] += 1

		return summary

	@staticmethod
	def maybe_emit_low_balance(result):
		if not WebhookService.is_enabled():
			return None

		settings = WebhookService._settings()
		threshold = float(settings.low_balance_threshold_default or 0)
		if threshold <= 0:
			return None

		available = float((result or {}).get("available_balance") or 0)
		if available > threshold:
			return None

		return WebhookService.emit_event(
			"credit.low_balance",
			{
				"credit_account": (result or {}).get("credit_account"),
				"credit_type": (result or {}).get("credit_type"),
				"available_balance": available,
				"threshold": threshold,
			},
			reference_doctype="Credit Account",
			reference_name=(result or {}).get("credit_account"),
		)

	@staticmethod
	def _attempt_delivery(doc):
		target_url = (doc.target_url or "").strip()
		if not target_url:
			return False, "No webhook target URL configured"

		payload = json.loads(doc.payload_json or "{}")
		body = {"event_type": doc.event_type, "payload": payload}
		if doc.idempotency_key:
			body["idempotency_key"] = doc.idempotency_key
		if doc.source_app:
			body["source_app"] = doc.source_app

		try:
			response = make_post_request(
				target_url,
				data=body,
				headers={"Content-Type": "application/json"},
			)
			if isinstance(response, dict) and response.get("status") == "error":
				return False, cstr(response.get("message") or response)[:500]
			return True, None
		except Exception as exc:
			return False, cstr(exc)[:500]

	@staticmethod
	def _mark_delivered(doc):
		doc.reload()
		doc.status = "Delivered"
		doc.delivered_at = now_datetime()
		doc.last_error = None
		doc.next_retry_at = None
		doc.save(ignore_permissions=True)

	@staticmethod
	def list_failed_webhook_events(limit=100):
		limit = int(limit or 100)
		return frappe.get_all(
			"Credit Webhook Event",
			filters={"status": ["in", ["Failed", "Pending"]]},
			fields=[
				"name",
				"event_type",
				"status",
				"retry_count",
				"max_retries",
				"next_retry_at",
				"last_error",
				"target_url",
				"creation",
			],
			order_by="modified desc",
			limit=limit,
		)

	@staticmethod
	def cancel_exhausted_webhook_events(dry_run=True, limit=500):
		limit = int(limit or 500)
		events = frappe.get_all(
			"Credit Webhook Event",
			filters={"status": ["in", ["Failed", "Pending"]]},
			fields=["name", "retry_count", "max_retries", "status"],
			order_by="modified asc",
			limit=limit,
		)

		eligible = [
			row.name
			for row in events
			if int(row.retry_count or 0) >= int(row.max_retries or 5)
		]
		cancelled = 0

		if dry_run:
			return {
				"status": "completed",
				"dry_run": True,
				"eligible": len(eligible),
				"cancelled": 0,
				"sample": eligible[:20],
			}

		for name in eligible:
			doc = frappe.get_doc("Credit Webhook Event", name)
			doc.status = "Cancelled"
			doc.next_retry_at = None
			doc.save(ignore_permissions=True)
			cancelled += 1

		frappe.db.commit()
		return {
			"status": "completed",
			"dry_run": False,
			"eligible": len(eligible),
			"cancelled": cancelled,
		}

	@staticmethod
	def _mark_failed(doc, error, schedule_retry=False):
		doc.reload()
		settings = WebhookService._settings()
		interval = int(settings.webhook_retry_interval_minutes or 30)
		doc.retry_count = int(doc.retry_count or 0) + 1
		doc.last_error = cstr(error)[:500] if error else None

		if int(doc.retry_count) >= int(doc.max_retries or 5):
			doc.status = "Failed"
			doc.next_retry_at = None
		elif schedule_retry:
			doc.status = "Failed" if doc.status != "Pending" else "Pending"
			doc.next_retry_at = add_to_date(now_datetime(), minutes=interval, as_datetime=True)
		else:
			doc.status = "Failed"
			doc.next_retry_at = None

		doc.save(ignore_permissions=True)