# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Decorators/helpers for public API integration logging and webhooks."""

import inspect

from credit_management.services.integration_log_service import IntegrationLogService
from credit_management.services.webhook_service import WebhookService

WEBHOOK_EVENTS = {
	"grant_credits": "credit.granted",
	"consume_credits": "credit.consumed",
	"reserve_credits": "credit.reserved",
	"consume_reserved_credits": "credit.reservation_consumed",
	"release_reservation": "credit.reservation_released",
	"refund_credits": "credit.refunded",
	"adjust_credits": "credit.adjusted",
	"transfer_credits": "credit.transferred",
	"expire_credits": "credit.expired",
	"reconcile_account": "credit.reconciliation_completed",
	"reconcile_all_accounts": "credit.reconciliation_completed",
}

LOW_BALANCE_OPERATIONS = frozenset(
	{
		"consume_credits",
		"consume_reserved_credits",
		"reserve_credits",
		"transfer_credits",
		"adjust_credits",
	}
)


def with_integration_logging(operation_name):
	def decorator(func):
		def wrapper(*args, **kwargs):
			bound = _bind_arguments(func, args, kwargs)
			request_payload = _build_request_payload(bound)
			context = _extract_context(bound)

			try:
				result = func(*args, **kwargs)
			except Exception as exc:
				IntegrationLogService.log_failure(
					operation_name,
					request=request_payload,
					error=exc,
					**context,
				)
				raise

			response_context = _extract_response_context(result)
			IntegrationLogService.log_success(
				operation_name,
				request=request_payload,
				response=result,
				**{**context, **response_context},
			)

			event_type = WEBHOOK_EVENTS.get(operation_name)
			if event_type:
				WebhookService.emit_event(
					event_type,
					_compact_webhook_payload(operation_name, request_payload, result),
					reference_doctype=response_context.get("reference_doctype"),
					reference_name=response_context.get("reference_name"),
					source_app=context.get("source_app"),
					idempotency_key=context.get("idempotency_key"),
				)

			if operation_name in LOW_BALANCE_OPERATIONS and isinstance(result, dict):
				WebhookService.maybe_emit_low_balance(result)

			return result

		wrapper.__name__ = func.__name__
		wrapper.__doc__ = func.__doc__
		return wrapper

	return decorator


def _bind_arguments(func, args, kwargs):
	signature = inspect.signature(func)
	return signature.bind_partial(*args, **kwargs).arguments


def _build_request_payload(bound):
	payload = {key: value for key, value in bound.items() if value is not None}
	if "metadata" in payload:
		payload["metadata"] = payload.get("metadata")
	return payload


def _extract_context(bound):
	return {
		"source_app": bound.get("source_app"),
		"idempotency_key": bound.get("idempotency_key"),
		"reference_doctype": bound.get("reference_doctype"),
		"reference_name": bound.get("reference_name"),
		"metadata": bound.get("metadata"),
	}


def _extract_response_context(result):
	if not isinstance(result, dict):
		return {}

	context = {}
	for field in ("credit_account", "ledger_entry", "reservation"):
		if result.get(field):
			context[field] = result.get(field)

	if result.get("reconciliation_run"):
		context["reference_doctype"] = "Credit Reconciliation Run"
		context["reference_name"] = result.get("reconciliation_run")

	return context


def _compact_webhook_payload(operation_name, request_payload, result):
	payload = {}
	if isinstance(result, dict):
		for key in (
			"credit_account",
			"credit_type",
			"ledger_entry",
			"reservation",
			"amount",
			"entry_type",
			"current_balance",
			"reserved_balance",
			"available_balance",
			"status",
			"checked_accounts",
			"mismatch_count",
			"summary_status",
			"reconciliation_run",
			"expired_count",
			"released_count",
		):
			if key in result:
				payload[key] = result.get(key)

	if operation_name in {"reconcile_account", "reconcile_all_accounts"}:
		payload["operation"] = operation_name
	elif request_payload:
		for key in (
			"owner_doctype",
			"owner_name",
			"credit_type",
			"amount",
			"from_account",
			"to_account",
			"reservation_name",
			"reason",
		):
			if key in request_payload:
				payload[key] = request_payload.get(key)

	return payload