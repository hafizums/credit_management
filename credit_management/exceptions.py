# Copyright (c) 2026, Hafiz and contributors
# License: MIT. See LICENSE


class CreditManagementError(Exception):
	"""Base exception for credit_management operations."""


class InsufficientCreditError(CreditManagementError):
	"""Raised when an operation requires more credit than is available."""


class InvalidCreditAmountError(CreditManagementError):
	"""Raised when an amount is zero, negative, or otherwise invalid."""


class CreditAccountSuspendedError(CreditManagementError):
	"""Raised when an operation targets a suspended or closed account."""


class CreditReservationError(CreditManagementError):
	"""Raised when a reservation lifecycle operation fails."""


class DuplicateCreditOperationError(CreditManagementError):
	"""Raised when an idempotency key or duplicate operation is detected."""


class CreditReconciliationError(CreditManagementError):
	"""Raised when reconciliation detects or cannot resolve a mismatch."""


class InvalidCreditTransferError(CreditManagementError):
	"""Raised when a transfer request is invalid."""


class LedgerReversalError(CreditManagementError):
	"""Raised when a ledger entry cannot be safely reversed."""