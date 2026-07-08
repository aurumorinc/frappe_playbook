import frappe
from frappe_playbook.playbook.doctype.playbook_provider.playbook_provider import get_provider_instance
from frappe_playbook.playbook.doctype.playbook_execution.playbook_execution import queue_resume_execution as native_queue_resume_execution

def on_update(doc, method):
    if doc.status == "Closed" and doc.has_value_changed("status") and doc.playbook_execution:
        execution_doc = frappe.get_doc("Playbook Execution", doc.playbook_execution)
        playbook_doc = frappe.get_doc("Playbook", execution_doc.playbook)
        
        execution_name = frappe.generate_hash(f"{doc.name}-{doc.modified}", length=10)
        
        if playbook_doc.provider:
            provider = get_provider_instance(playbook_doc.provider)
            provider.queue_resume_execution(execution_doc, doc.response_body, doc.callback_url, execution_name)
        else:
            native_queue_resume_execution(execution_doc, doc.response_body)
