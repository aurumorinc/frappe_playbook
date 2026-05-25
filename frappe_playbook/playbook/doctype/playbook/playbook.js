// Copyright (c) 2026, Aquiveal and contributors
// For license information, please see license.txt

frappe.ui.form.on("Playbook", {
	refresh: function (frm) {
		console.log("Playbook JS loaded");
		
		// Always hide the provider field as requested
		frm.set_df_property("provider", "hidden", 1);

		// Check available providers to auto-set if there's only one
		frappe.db.get_list("Playbook Provider", {
			filters: {
				enabled: 1
			},
			fields: ["name"]
		}).then(providers => {
			if (providers.length === 1) {
				// If exactly one provider, auto-set
				let provider_name = providers[0].name;
				if (frm.doc.provider !== provider_name) {
					frm.set_value("provider", provider_name);
				}
			} else if (providers.length === 0) {
				// If no providers, clear
				if (frm.doc.provider) {
					frm.set_value("provider", "");
				}
			}
		});

		if (!frm.is_new()) {
			frm.add_custom_button(__("Playbook Builder"), function () {
				if (frm.doc.provider) {
					frappe.call({
						method: "frappe_playbook.playbook.doctype.playbook.playbook.get_builder_url",
						args: {
							playbook_name: frm.doc.name
						},
						callback: function (r) {
							if (r.message) {
								window.open(r.message, "_blank");
							} else {
								frappe.msgprint("Could not get builder URL from provider.");
							}
						}
					});
				} else {
					// Native builder
					frappe.msgprint("Native builder not implemented yet.");
				}
			});
		}
	},
});
