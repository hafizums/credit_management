# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils import flt


def get_signed_amount(transaction_type: str, amount: float) -> float:
	amount = flt(amount)
	if transaction_type in ("Disbursement", "Interest Charge", "Adjustment (Increase)"):
		return amount
	if transaction_type in ("Repayment", "Adjustment (Decrease)"):
		return -amount
	frappe.throw(f"Unsupported transaction type: {transaction_type}")


def update_account_balance(credit_account: str, signed_amount: float) -> None:
	account = frappe.get_doc("Credit Account", credit_account)
	account.outstanding_balance = flt(account.outstanding_balance) + flt(signed_amount)
	account.update_available_credit()
	maybe_suspend_account(account)
	account.save(ignore_permissions=True)


def maybe_suspend_account(account) -> None:
	settings = frappe.get_single("Credit Management Settings")
	if not settings.auto_suspend_on_limit_exceeded:
		return
	if flt(account.outstanding_balance) >= flt(account.credit_limit) and account.status == "Active":
		account.status = "Suspended"


def reverse_account_balance(credit_account: str, signed_amount: float) -> None:
	update_account_balance(credit_account, -flt(signed_amount))