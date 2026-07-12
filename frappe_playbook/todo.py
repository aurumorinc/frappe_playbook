import frappe
import json

@frappe.whitelist(allow_guest=False)
def create(playbook_execution_name, template_name, callback_url=None, assignee=None, description=None, reference_type=None, reference_name=None, request_body=None):
    if not frappe.db.exists("Playbook Execution", playbook_execution_name):
        frappe.throw(f"Playbook Execution {playbook_execution_name} not found", frappe.DoesNotExistError)
        
    if template_name and not frappe.db.exists("DocType", "ToDo Template"):
        template_name = None

    if template_name and not frappe.db.exists("ToDo Template", template_name):
        template_name = None
        
    todo = frappe.get_doc({
        "doctype": "ToDo",
        "playbook_execution": playbook_execution_name,
        "todo_template": template_name,
        "callback_url": callback_url,
        "allocated_to": assignee,
        "description": description,
        "reference_type": reference_type,
        "reference_name": reference_name,
        "status": "Open"
    })
    
    todo.insert(ignore_permissions=True)
    return todo.name
