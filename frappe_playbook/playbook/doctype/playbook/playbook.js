// Copyright (c) 2026, Aquiveal and contributors
// For license information, please see license.txt

frappe.ui.form.on("Playbook", {
	refresh: function (frm) {
		console.log("Playbook JS loaded");

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
			
			frm.add_custom_button(__("Test Execution"), function () {
				frappe.call({
					method: "frappe_playbook.playbook.doctype.playbook.playbook.trigger_test_execution",
					args: {
						playbook_name: frm.doc.name
					},
					freeze: true,
					freeze_message: __("Triggering test execution..."),
					callback: function (r) {
						if (r.message && r.message.status === "success") {
							frappe.msgprint({
								title: r.message.title || __('Success'),
								indicator: 'green',
								message: r.message.message
							});
						} else if (r.message && r.message.status === "failed") {
							frappe.msgprint({
								title: r.message.title || __('Failed'),
								indicator: 'orange',
								message: r.message.message
							});
						}
					}
				});
			});
		}
	},
});
