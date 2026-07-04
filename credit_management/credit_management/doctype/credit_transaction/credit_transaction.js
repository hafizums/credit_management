// Copyright (c) 2026, Hafiz and contributors
// License: MIT. See LICENSE

frappe.ui.form.on("Credit Transaction", {
	credit_account(frm) {
		if (frm.doc.credit_account) {
			frappe.db.get_value("Credit Account", frm.doc.credit_account, "currency").then((r) => {
				if (r.message) {
					frm.set_value("currency", r.message.currency);
				}
			});
		}
	},
});