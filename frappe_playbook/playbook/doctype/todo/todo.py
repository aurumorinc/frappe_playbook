import frappe
from frappe_playbook.playbook.doctype.playbook_execution.playbook_execution import queue_resume_execution as native_queue_resume_execution

def on_update(doc, method):
    if doc.status == "Closed" and doc.has_value_changed("status") and doc.playbook_execution:
        execution_doc = frappe.get_doc("Playbook Execution", doc.playbook_execution)
        native_queue_resume_execution(execution_doc, doc.response_body)
