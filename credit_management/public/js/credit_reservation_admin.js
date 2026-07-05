frappe.ui.form.on("Credit Reservation", {
	refresh(frm) {
		if (
			!frm.doc.name ||
			!["Active", "Partially Consumed"].includes(frm.doc.status) ||
			!(frappe.user.has_role("Credit Manager") || frappe.user.has_role("System Manager"))
		) {
			return;
		}

		frm.add_custom_button(__("Release Reservation"), () => {
			frappe.prompt(
				[
					{
						fieldtype: "Small Text",
						fieldname: "reason",
						label: __("Release Reason"),
						reqd: 1,
					},
				],
				(values) => {
					frappe.call({
						method: "credit_management.admin_ux.admin_release_reservation",
						args: {
							reservation_name: frm.doc.name,
							reason: values.reason,
						},
						freeze: true,
						callback(r) {
							if (!r.message) return;
							frappe.show_alert({
								message: __("Released via {0}", [r.message.ledger_entry]),
								indicator: "green",
							});
							frm.reload_doc();
						},
					});
				},
				__("Release Reservation"),
				__("Release")
			);
		});
	},
});