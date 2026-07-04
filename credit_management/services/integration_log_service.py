# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Integration/API audit logging."""

import json

import frappe
from frappe.utils import cstr

SENSITIVE_KEYS = frozenset(
	{
		"api_key",
		"secret",
		"token",
		"authorization",
		"password",
		"provider_key",
		"access_token",
		"refresh_token",
		"client_secret",
		"webhook_secret",
	}
)

MAX_JSON_LENGTH = 50000


class IntegrationLogService:
	@staticmethod
	def is_enabled():
		if not frappe.db.exists("DocType", "Credit Integration Log"):
			return False
		return bool(frappe.get_single("Credit Settings").enable_integration_logs)

	@staticmethod
	def sanitize_payload(payload):
		if payload is None:
			return None
		if isinstance(payload, str):
			try:
				payload = json.loads(payload)
			except (TypeError, ValueError):
				return payload
		return IntegrationLogService._sanitize_value(payload)

	@staticmethod
	def _sanitize_value(value):
		if isinstance(value, dict):
			sanitized = {}
			for key, item in value.items():
				key_lower = cstr(key).lower()
				if key_lower in SENSITIVE_KEYS or any(
					sensitive in key_lower for sensitive in SENSITIVE_KEYS
				):
					sanitized[key] = "[REDACTED]"
					continue
				sanitized[key] = IntegrationLogService._sanitize_value(item)
			return sanitized
		if isinstance(value, list):
			return [IntegrationLogService._sanitize_value(item) for item in value]
		return value

	@staticmethod
	def _serialize_payload(payload):
		if payload is None:
			return None
		sanitized = IntegrationLogService.sanitize_payload(payload)
		text = json.dumps(sanitized, default=str)
		if len(text) > MAX_JSON_LENGTH:
			return text[:MAX_JSON_LENGTH] + "...[truncated]"
		return text

	@staticmethod
	def log_success(operation, request=None, response=None, **context):
		if not IntegrationLogService.is_enabled():
			return None
		return IntegrationLogService._insert_log(
			operation=operation,
			status="Success" if not (response or {}).get("idempotent_replay") else "Replayed",
			request=request,
			response=response,
			**context,
		)

	@staticmethod
	def log_failure(operation, request=None, error=None, **context):
		if not IntegrationLogService.is_enabled():
			return None
		return IntegrationLogService._insert_log(
			operation=operation,
			status="Failed",
			request=request,
			error_message=cstr(error)[:140] if error else None,
			**context,
		)

	@staticmethod
	def _insert_log(
		operation,
		status,
		request=None,
		response=None,
		error_message=None,
		source_app=None,
		idempotency_key=None,
		credit_account=None,
		ledger_entry=None,
		reservation=None,
		reference_doctype=None,
		reference_name=None,
		metadata=None,
		created_by_user=None,
	):
		if reference_name and not reference_doctype:
			reference_name = None

		doc = frappe.get_doc(
			{
				"doctype": "Credit Integration Log",
				"operation": operation,
				"status": status,
				"source_app": source_app,
				"idempotency_key": idempotency_key,
				"credit_account": credit_account,
				"ledger_entry": ledger_entry,
				"reservation": reservation,
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"request_json": IntegrationLogService._serialize_payload(request),
				"response_json": IntegrationLogService._serialize_payload(response),
				"error_message": error_message,
				"metadata_json": IntegrationLogService._serialize_payload(metadata),
				"created_by_user": created_by_user or frappe.session.user,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name