// Copyright (c) 2026, Aquiveal and contributors
// For license information, please see license.txt

frappe.ui.form.on("Playbook Execution", {
    refresh(frm) {
        frm.add_custom_button(__("Debug in Editor"), () => {
            frappe.call({
                method: "frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.get_debug_url",
                args: { execution_name: frm.doc.name },
                callback: function(r) {
                    if (r.message) {
                        window.open(r.message, "_blank");
                    } else {
                        frappe.msgprint(__("Debug URL not available."));
                    }
                }
            });
        });
        
        frm.add_custom_button(__("Replay"), () => {
            frappe.call({
                method: "frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.replay",
                args: { execution_name: frm.doc.name },
                callback: function(r) {
                    frm.reload_doc();
                    frappe.show_alert({message: __("Execution Replayed"), indicator: "green"});
                }
            });
        });
    }
});
