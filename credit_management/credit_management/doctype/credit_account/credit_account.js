// Copyright (c) 2026, Hafiz and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("Credit Account", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("New Transaction"), () => {
				frappe.new_doc("Credit Transaction", {
					credit_account: frm.doc.name,
					currency: frm.doc.currency,
				});
			});
		}
	},
});