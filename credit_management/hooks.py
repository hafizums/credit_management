app_name = "credit_management"
app_title = "Credit Management"
app_publisher = "Hafiz"
app_description = "Reusable credit management platform with ledger, reservations, and public API"
app_email = "hafiz@example.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/credit_management/css/credit_management.css"
# app_include_js = "/assets/credit_management/js/credit_management.js"

# include js, css files in header of web template
# web_include_css = "/assets/credit_management/css/credit_management.css"
# web_include_js = "/assets/credit_management/js/credit_management.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "credit_management/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"Credit Reservation": "public/js/credit_reservation_admin.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "credit_management.utils.jinja_methods",
# 	"filters": "credit_management.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "credit_management.install.before_install"
after_install = "credit_management.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "credit_management.uninstall.before_uninstall"
# after_uninstall = "credit_management.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "credit_management.utils.before_app_install"
# after_app_install = "credit_management.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "credit_management.utils.before_app_uninstall"
# after_app_uninstall = "credit_management.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "credit_management.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Credit Account": "credit_management.permissions.get_credit_account_query_conditions",
	"Credit Ledger Entry": "credit_management.permissions.get_credit_ledger_query_conditions",
	"Credit Reservation": "credit_management.permissions.get_credit_reservation_query_conditions",
	"Credit Grant": "credit_management.permissions.get_credit_grant_query_conditions",
	"Credit Expiry Lot": "credit_management.permissions.get_credit_expiry_lot_query_conditions",
	"Credit Transfer": "credit_management.permissions.get_credit_transfer_query_conditions",
	"Credit Type": "credit_management.permissions.get_credit_type_query_conditions",
	"Credit Settings": "credit_management.permissions.get_credit_settings_query_conditions",
	"Credit Integration Log": "credit_management.permissions.get_credit_integration_log_query_conditions",
	"Credit Webhook Event": "credit_management.permissions.get_credit_webhook_event_query_conditions",
}

has_permission = {
	"Credit Account": "credit_management.permissions.has_credit_account_permission",
	"Credit Ledger Entry": "credit_management.permissions.has_credit_ledger_permission",
	"Credit Reservation": "credit_management.permissions.has_credit_reservation_permission",
	"Credit Grant": "credit_management.permissions.has_credit_grant_permission",
	"Credit Expiry Lot": "credit_management.permissions.has_credit_expiry_lot_permission",
	"Credit Transfer": "credit_management.permissions.has_credit_transfer_permission",
	"Credit Type": "credit_management.permissions.has_credit_type_permission",
	"Credit Settings": "credit_management.permissions.has_credit_settings_permission",
	"Credit Integration Log": "credit_management.permissions.has_credit_integration_log_permission",
	"Credit Webhook Event": "credit_management.permissions.has_credit_webhook_event_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"hourly": [
		"credit_management.tasks.release_expired_reservations",
		"credit_management.tasks.reconcile_recent_accounts",
	],
	"daily": [
		"credit_management.tasks.expire_credits",
		"credit_management.tasks.generate_daily_credit_summary",
	],
	"cron": {
		"0/30 * * * *": [
			"credit_management.tasks.retry_failed_webhooks",
		],
	},
}

# Testing
# -------

before_tests = "credit_management.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "credit_management.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "credit_management.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["credit_management.utils.before_request"]
# after_request = ["credit_management.utils.after_request"]

# Job Events
# ----------
# before_job = ["credit_management.utils.before_job"]
# after_job = ["credit_management.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"credit_management.auth.validate"
# ]
