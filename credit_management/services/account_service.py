# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE

"""Account lifecycle and cached balance reads."""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import flt

from credit_management.exceptions import (
	CreditAccountSuspendedError,
	CreditManagementError,
	InsufficientCreditError,
)


class AccountService:
	@staticmethod
	def make_account_name(owner_doctype, owner_name, credit_type, company=None):
		key = "|".join([owner_doctype or "", owner_name or "", credit_type or "", company or ""])
		digest = hashlib.sha256(key.encode()).hexdigest()[:20]
		return f"CA-{digest}"

	@staticmethod
	def validate_owner_doctype(owner_doctype):
		if not owner_doctype:
			frappe.throw(_("Account owner DocType is required"), CreditManagementError)

		if not frappe.db.exists("DocType", owner_doctype):
			frappe.throw(
				_("Account owner DocType {0} does not exist").format(owner_doctype),
				CreditManagementError,
			)

	@staticmethod
	def get_active_credit_type(credit_type):
		if not credit_type:
			frappe.throw(_("Credit type is required"), CreditManagementError)

		if not frappe.db.exists("Credit Type", credit_type):
			frappe.throw(
				_("Credit Type {0} does not exist").format(credit_type),
				CreditManagementError,
			)

		type_doc = frappe.get_doc("Credit Type", credit_type)
		if not type_doc.is_active:
			frappe.throw(
				_("Credit Type {0} is not active").format(credit_type),
				CreditManagementError,
			)

		return type_doc

	@staticmethod
	def find_account(owner_doctype, owner_name, credit_type, company=None):
		account_name = AccountService.make_account_name(
			owner_doctype, owner_name, credit_type, company
		)
		if frappe.db.exists("Credit Account", account_name):
			return account_name
		return None

	@staticmethod
	def get_or_create_account(owner_doctype, owner_name, credit_type, company=None):
		AccountService.validate_owner_doctype(owner_doctype)
		AccountService.get_active_credit_type(credit_type)

		if not owner_name:
			frappe.throw(_("Account owner name is required"), CreditManagementError)

		account_name = AccountService.find_account(
			owner_doctype, owner_name, credit_type, company
		)
		if account_name:
			return frappe.get_doc("Credit Account", account_name)

		account_name = AccountService.make_account_name(
			owner_doctype, owner_name, credit_type, company
		)

		doc = frappe.get_doc(
			{
				"doctype": "Credit Account",
				"account_owner_doctype": owner_doctype,
				"account_owner_name": owner_name,
				"credit_type": credit_type,
				"company": company,
				"status": "Active",
				"current_balance": 0,
				"reserved_balance": 0,
				"available_balance": 0,
				"lifetime_granted": 0,
				"lifetime_consumed": 0,
				"lifetime_expired": 0,
			}
		)

		doc.flags.ignore_links = True
		try:
			doc.insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			return frappe.get_doc("Credit Account", account_name)

		return doc

	@staticmethod
	def lock_account(account_name):
		return frappe.get_doc("Credit Account", account_name, for_update=True)

	@staticmethod
	def get_balance(owner_doctype, owner_name, credit_type, company=None):
		account = AccountService.get_or_create_account(
			owner_doctype, owner_name, credit_type, company
		)
		return AccountService.balance_dict(account)

	@staticmethod
	def balance_dict(account):
		account = frappe.get_doc(account) if isinstance(account, str) else account
		return {
			"credit_account": account.name,
			"credit_type": account.credit_type,
			"current_balance": flt(account.current_balance),
			"reserved_balance": flt(account.reserved_balance),
			"available_balance": flt(account.available_balance),
		}

	@staticmethod
	def round_amount(amount, credit_type):
		precision = frappe.db.get_value("Credit Type", credit_type, "decimal_precision") or 2
		return flt(amount, int(precision))

	@staticmethod
	def negative_balance_allowed(credit_type):
		type_allows = frappe.db.get_value("Credit Type", credit_type, "allow_negative_balance")
		if type_allows:
			return True

		settings = frappe.get_single("Credit Settings")
		return bool(settings.allow_negative_balance_default)

	@staticmethod
	def _validate_account_is_active(account, action):
		if account.status in ("Suspended", "Closed"):
			frappe.throw(
				_("Credit Account {0} is {1} and cannot {2}").format(
					account.name, account.status.lower(), action
				),
				CreditAccountSuspendedError,
			)

	@staticmethod
	def validate_account_can_consume(account):
		AccountService._validate_account_is_active(account, "consume credits")

	@staticmethod
	def validate_account_can_reserve(account):
		AccountService._validate_account_is_active(account, "reserve credits")

	@staticmethod
	def validate_sufficient_balance(account, amount):
		if AccountService.negative_balance_allowed(account.credit_type):
			return

		if flt(account.available_balance) < flt(amount):
			frappe.throw(
				_("Insufficient available credit balance"),
				InsufficientCreditError,
			)

	@staticmethod
	def update_balances(
		account,
		*,
		current_balance=None,
		reserved_balance=None,
		lifetime_granted_delta=0,
		lifetime_consumed_delta=0,
		lifetime_expired_delta=0,
	):
		account = frappe.get_doc(account) if isinstance(account, str) else account

		current = flt(current_balance if current_balance is not None else account.current_balance)
		reserved = flt(reserved_balance if reserved_balance is not None else account.reserved_balance)
		available = flt(current - reserved)

		lifetime_granted = flt(account.lifetime_granted) + flt(lifetime_granted_delta)
		lifetime_consumed = flt(account.lifetime_consumed) + flt(lifetime_consumed_delta)
		lifetime_expired = flt(account.lifetime_expired) + flt(lifetime_expired_delta)

		frappe.db.set_value(
			"Credit Account",
			account.name,
			{
				"current_balance": current,
				"reserved_balance": reserved,
				"available_balance": available,
				"lifetime_granted": lifetime_granted,
				"lifetime_consumed": lifetime_consumed,
				"lifetime_expired": lifetime_expired,
			},
			update_modified=False,
		)
		account.reload()

		return account

	@staticmethod
	def serialize_metadata(metadata):
		if metadata is None:
			return None
		if isinstance(metadata, str):
			return metadata
		return json.loads(json.dumps(metadata))