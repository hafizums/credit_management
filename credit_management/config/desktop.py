from frappe import _


def get_data():
	return [
		{
			"module_name": "Credit Management",
			"type": "module",
			"label": _("Credit Management"),
			"color": "#2E86AB",
			"icon": "octicon octicon-credit-card",
		},
		{
			"type": "doctype",
			"name": "Credit Account",
			"label": _("Credit Account"),
			"description": _("Manage customer credit limits and balances"),
			"onboard": 1,
		},
		{
			"type": "doctype",
			"name": "Credit Transaction",
			"label": _("Credit Transaction"),
			"description": _("Record disbursements, repayments, and adjustments"),
			"onboard": 1,
		},
		{
			"type": "doctype",
			"name": "Credit Management Settings",
			"label": _("Credit Management Settings"),
			"description": _("Configure credit management defaults and rules"),
		},
	]