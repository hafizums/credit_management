frappe.pages["credit-admin-tools"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Credit Admin Tools"),
		single_column: true,
	});

	frappe.breadcrumbs.add("Credit Management");

	const can_mutate =
		frappe.user.has_role("Credit Manager") || frappe.user.has_role("System Manager");

	const tabs = frappe.ui.form.make_control({
		parent: page.main,
		df: {
			fieldtype: "Select",
			label: __("Section"),
			options: [
				can_mutate ? "Top Up Credits" : "",
				can_mutate ? "Refund Credits" : "",
				can_mutate ? "Release Reservation" : "",
				"Balance Quick View",
				"Reconciliation Review",
			]
				.filter(Boolean)
				.join("\n"),
			change() {
				render_section(tabs.get_value());
			},
		},
	});
	tabs.refresh();

	const body = $('<div class="credit-admin-tools-body" style="margin-top: 1rem;"></div>').appendTo(
		page.main
	);

	function render_section(section) {
		body.empty();
		if (section === "Top Up Credits") render_top_up(body);
		else if (section === "Refund Credits") render_refund(body);
		else if (section === "Release Reservation") render_release(body);
		else if (section === "Balance Quick View") render_balance(body);
		else if (section === "Reconciliation Review") render_reconciliation(body);
	}

	render_section(tabs.get_value());

	function owner_fields(parent, defaults = {}) {
		const fields = {};
		fields.owner_doctype = frappe.ui.form.make_control({
			parent,
			df: {
				fieldtype: "Link",
				label: __("Owner DocType"),
				options: "DocType",
				default: defaults.owner_doctype || "User",
				reqd: 1,
			},
		});
		fields.owner_name = frappe.ui.form.make_control({
			parent,
			df: {
				fieldtype: "Dynamic Link",
				label: __("Owner"),
				options: "owner_doctype",
				default: defaults.owner_name,
				reqd: 1,
			},
		});
		fields.credit_type = frappe.ui.form.make_control({
			parent,
			df: {
				fieldtype: "Link",
				label: __("Credit Type"),
				options: "Credit Type",
				default: defaults.credit_type || "GENERAL",
				reqd: 1,
			},
		});
		Object.values(fields).forEach((f) => f.refresh());
		return fields;
	}

	function render_top_up(parent) {
		parent.append(`<p class="text-muted">${__(
			"Grant credits via the trusted API. Creates a GRANT ledger entry."
		)}</p>`);
		const fields = owner_fields(parent);
		const amount = frappe.ui.form.make_control({
			parent,
			df: { fieldtype: "Float", label: __("Amount"), reqd: 1 },
		});
		const reason = frappe.ui.form.make_control({
			parent,
			df: { fieldtype: "Small Text", label: __("Grant Reason"), reqd: 1 },
		});
		const expires_on = frappe.ui.form.make_control({
			parent,
			df: { fieldtype: "Date", label: __("Expires On (optional)") },
		});
		[amount, reason, expires_on].forEach((f) => f.refresh());

		const btn = $(`<button class="btn btn-primary btn-sm">${__("Grant Credits")}</button>`).appendTo(
			parent
		);
		btn.on("click", () => {
			frappe.call({
				method: "credit_management.admin_ux.admin_top_up_credits",
				args: {
					owner_doctype: fields.owner_doctype.get_value(),
					owner_name: fields.owner_name.get_value(),
					credit_type: fields.credit_type.get_value(),
					amount: amount.get_value(),
					grant_reason: reason.get_value(),
					expires_on: expires_on.get_value(),
				},
				freeze: true,
				callback(r) {
					if (!r.message) return;
					const m = r.message;
					frappe.msgprint({
						title: __("Credits Granted"),
						indicator: "green",
						message: __(
							"Before: {0} → After: {1}. Ledger: {2} ({3})",
							[m.balance_before.current_balance, m.balance_after.current_balance, m.ledger_entry, m.entry_type]
						),
					});
				},
			});
		});
	}

	function render_refund(parent) {
		parent.append(`<p class="text-muted">${__(
			"Refund credits via the trusted API. Creates a REFUND ledger entry."
		)}</p>`);
		const fields = owner_fields(parent);
		const amount = frappe.ui.form.make_control({
			parent,
			df: { fieldtype: "Float", label: __("Amount"), reqd: 1 },
		});
		const reason = frappe.ui.form.make_control({
			parent,
			df: { fieldtype: "Small Text", label: __("Refund Reason"), reqd: 1 },
		});
		[amount, reason].forEach((f) => f.refresh());

		$(`<button class="btn btn-primary btn-sm">${__("Refund Credits")}</button>`)
			.appendTo(parent)
			.on("click", () => {
				frappe.call({
					method: "credit_management.admin_ux.admin_refund_credits",
					args: {
						owner_doctype: fields.owner_doctype.get_value(),
						owner_name: fields.owner_name.get_value(),
						credit_type: fields.credit_type.get_value(),
						amount: amount.get_value(),
						refund_reason: reason.get_value(),
					},
					freeze: true,
					callback(r) {
						if (!r.message) return;
						const m = r.message;
						frappe.msgprint({
							title: __("Credits Refunded"),
							indicator: "green",
							message: __(
								"Before: {0} → After: {1}. Ledger: {2} ({3})",
								[m.balance_before.current_balance, m.balance_after.current_balance, m.ledger_entry, m.entry_type]
							),
						});
					},
				});
			});
	}

	function render_release(parent) {
		parent.append(`<p class="text-muted">${__(
			"Release an active reservation. Creates a RELEASE_RESERVE ledger entry."
		)}</p>`);
		const reservation = frappe.ui.form.make_control({
			parent,
			df: {
				fieldtype: "Link",
				label: __("Credit Reservation"),
				options: "Credit Reservation",
				reqd: 1,
				change() {
					const name = reservation.get_value();
					if (!name) return;
					frappe.call({
						method: "credit_management.admin_ux.admin_get_reservation_details",
						args: { reservation_name: name },
						callback(r) {
							info.empty();
							if (!r.message) return;
							const d = r.message;
							info.html(
								`<pre style="font-size:12px;">${frappe.utils.escape_html(
									JSON.stringify(d, null, 2)
								)}</pre>`
							);
						},
					});
				},
			},
		});
		reservation.refresh();
		const info = $('<div class="text-muted" style="margin: 0.5rem 0;"></div>').appendTo(parent);
		const reason = frappe.ui.form.make_control({
			parent,
			df: { fieldtype: "Small Text", label: __("Release Reason"), reqd: 1 },
		});
		reason.refresh();

		$(`<button class="btn btn-primary btn-sm">${__("Release Reservation")}</button>`)
			.appendTo(parent)
			.on("click", () => {
				frappe.call({
					method: "credit_management.admin_ux.admin_release_reservation",
					args: {
						reservation_name: reservation.get_value(),
						reason: reason.get_value(),
					},
					freeze: true,
					callback(r) {
						if (!r.message) return;
						frappe.msgprint({
							title: __("Reservation Released"),
							indicator: "green",
							message: __(
								"Ledger {0} ({1}). Reservation status: {2}",
								[r.message.ledger_entry, r.message.entry_type, r.message.reservation_status]
							),
						});
					},
				});
			});
	}

	function render_balance(parent) {
		parent.append(`<p class="text-muted">${__(
			"Inspect balances, reservations, and recent ledger entries."
		)}</p>`);
		const fields = owner_fields(parent);
		const output = $('<div style="margin-top: 1rem;"></div>').appendTo(parent);

		$(`<button class="btn btn-primary btn-sm">${__("Load Balance")}</button>`)
			.appendTo(parent)
			.on("click", () => {
				frappe.call({
					method: "credit_management.admin_ux.admin_get_account_balance_overview",
					args: {
						owner_doctype: fields.owner_doctype.get_value(),
						owner_name: fields.owner_name.get_value(),
						credit_type: fields.credit_type.get_value(),
					},
					freeze: true,
					callback(r) {
						output.empty();
						if (!r.message) return;
						output.html(
							`<pre style="font-size:12px;">${frappe.utils.escape_html(
								JSON.stringify(r.message, null, 2)
							)}</pre>`
						);
					},
				});
			});
	}

	function render_reconciliation(parent) {
		parent.append(`<p class="text-muted">${__(
			"Review recent reconciliation runs. Re-run is detect-only — no auto-repair."
		)}</p>`);
		const table = $('<div class="reconciliation-table"></div>').appendTo(parent);

		function load_runs() {
			frappe.call({
				method: "credit_management.admin_ux.admin_get_reconciliation_review",
				args: { limit: 20 },
				callback(r) {
					table.empty();
					if (!r.message || !r.message.length) {
						table.text(__("No reconciliation runs found."));
						return;
					}
					const rows = r.message
						.map(
							(row) => `<tr>
							<td><a href="#Form/Credit Reconciliation Run/${row.name}">${row.name}</a></td>
							<td>${row.status}</td>
							<td>${row.credit_account || ""}</td>
							<td>${row.current_difference || 0}</td>
							<td>${row.reserved_difference || 0}</td>
							<td>${row.available_difference || 0}</td>
							<td>
								${row.credit_account ? `<button class="btn btn-xs btn-default rerun" data-account="${row.credit_account}">${__("Re-run")}</button>` : ""}
								${row.credit_account ? `<button class="btn btn-xs btn-default ledger" data-account="${row.credit_account}">${__("Ledger Report")}</button>` : ""}
							</td>
						</tr>`
						)
						.join("");
					table.html(
						`<table class="table table-bordered table-sm"><thead><tr>
						<th>${__("Run")}</th><th>${__("Status")}</th><th>${__("Account")}</th>
						<th>${__("Δ Current")}</th><th>${__("Δ Reserved")}</th><th>${__("Δ Available")}</th><th>${__("Actions")}</th>
						</tr></thead><tbody>${rows}</tbody></table>`
					);
					table.find(".rerun").on("click", function () {
						const account = $(this).data("account");
						frappe.call({
							method: "credit_management.admin_ux.admin_rerun_reconcile_account",
							args: { credit_account: account },
							freeze: true,
							callback(res) {
								frappe.msgprint({
									title: __("Reconciliation Complete"),
									indicator: res.message.reconciliation.summary_status === "Passed" ? "green" : "orange",
									message: __(
										"Status: {0}. Auto-repair: {1}",
										[res.message.reconciliation.summary_status, res.message.auto_repair_performed]
									),
								});
								load_runs();
							},
						});
					});
					table.find(".ledger").on("click", function () {
						const account = $(this).data("account");
						frappe.set_route("query-report", "Credit Ledger Report", { credit_account: account });
					});
				},
			});
		}

		load_runs();
		$(`<button class="btn btn-default btn-sm" style="margin-top:0.5rem;">${__("Refresh")}</button>`)
			.appendTo(parent)
			.on("click", load_runs);
	}
};