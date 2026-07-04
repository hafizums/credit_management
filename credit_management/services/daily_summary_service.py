# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Daily credit metrics summary for scheduler tasks."""

import frappe
from frappe.utils import flt, getdate, today


class DailySummaryService:
	@staticmethod
	def generate_daily_credit_summary(summary_date=None):
		summary_date = getdate(summary_date or today())

		return {
			"status": "completed",
			"date": str(summary_date),
			"total_accounts": frappe.db.count("Credit Account"),
			"active_reservations": frappe.db.count(
				"Credit Reservation", {"status": ["in", ["Active", "Partially Consumed"]]}
			),
			"consumed_today": DailySummaryService._sum_ledger_amount(
				summary_date, ("CONSUME", "CONSUME_RESERVE")
			),
			"granted_today": DailySummaryService._sum_ledger_amount(summary_date, ("GRANT",)),
			"expired_today": DailySummaryService._sum_ledger_amount(summary_date, ("EXPIRE",)),
			"reserved_today": DailySummaryService._sum_ledger_amount(summary_date, ("RESERVE",)),
			"released_today": DailySummaryService._sum_ledger_amount(
				summary_date, ("RELEASE_RESERVE",)
			),
			"transfer_in_today": DailySummaryService._sum_ledger_amount(
				summary_date, ("TRANSFER_IN",)
			),
			"transfer_out_today": DailySummaryService._sum_ledger_amount(
				summary_date, ("TRANSFER_OUT",)
			),
		}

	@staticmethod
	def _sum_ledger_amount(summary_date, entry_types):
		result = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(amount), 0)
			FROM `tabCredit Ledger Entry`
			WHERE entry_type IN %(entry_types)s
			AND docstatus = 1
			AND DATE(creation) = %(summary_date)s
			""",
			{"entry_types": entry_types, "summary_date": summary_date},
		)
		return flt(result[0][0] if result else 0)