# Copyright (c) 2026, Aurumor and contributors
# For license information, please see license.txt

import json
import importlib
import frappe

def after_migrate():
    sync_playbook_nodes()

def sync_playbook_nodes():
    playbook_nodes = frappe.get_hooks("playbook_nodes")
    if not playbook_nodes:
        return

    for node_module_path in playbook_nodes:
        try:
            module = importlib.import_module(node_module_path)
            node_name = getattr(module, "NODE_NAME", None)
            category = getattr(module, "CATEGORY", "Action")
            request_model = getattr(module, "RequestModel", None)

            if not node_name or not request_model:
                frappe.log_error(
                    f"Missing required attributes (NODE_NAME, RequestModel) in {node_module_path}",
                    "Playbook Node Sync"
                )
                continue

            ui_schema = json.dumps(request_model.model_json_schema())

            if frappe.db.exists("Playbook Node Type", node_name):
                doc = frappe.get_doc("Playbook Node Type", node_name)
                doc.category = category
                doc.python_module = node_module_path
                doc.ui_schema = ui_schema
                doc.save(ignore_permissions=True)
            else:
                doc = frappe.get_doc({
                    "doctype": "Playbook Node Type",
                    "node_type_name": node_name,
                    "category": category,
                    "python_module": node_module_path,
                    "ui_schema": ui_schema
                })
                doc.insert(ignore_permissions=True)
        except Exception as e:
            frappe.log_error(f"Failed to sync playbook node {node_module_path}: {str(e)}", "Playbook Node Sync")
    frappe.db.commit()
