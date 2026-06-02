import frappe
from frappe.model.document import Document
from frappe_controller.utils.background_jobs import enqueue
from frappe_controller.utils.controller import emit_event

from frappe_playbook.playbook.doctype.playbook_provider.playbook_provider import get_provider_instance

class PlaybookExecution(Document):
    def validate(self):
        old_doc = self.get_doc_before_save()
        if old_doc:
            valid_transitions = {
                "running": ["waiting", "success", "error", "canceled"],
                "waiting": ["running", "canceled"],
                "success": [],
                "error": [],
                "canceled": []
            }
            if self.status != old_doc.status and self.status not in valid_transitions.get(old_doc.status, []):
                frappe.throw(f"Invalid status transition from {old_doc.status} to {self.status}")

    def on_update(self):
        if self.has_value_changed("status") and self.status == "canceled":
            playbook_doc = frappe.get_doc("Playbook", self.playbook)
            if playbook_doc.provider:
                try:
                    provider_instance = get_provider_instance(playbook_doc.provider)
                    provider_instance.stop_execution(self)
                except Exception as e:
                    frappe.log_error(f"Failed to stop execution for Playbook Execution {self.name}: {str(e)}", "Playbook Provider Error")
                    frappe.msgprint(f"Warning: Failed to stop execution in provider {playbook_doc.provider}. Error: {str(e)}", indicator="orange", alert=True)

def queue_trigger_execution(playbook_doc, reference_doctype, reference_name, payload, idempotency_key, as_child=True):
    enqueue(
        "frappe_playbook.playbook.doctype.playbook_execution.playbook_execution.run",
        playbook_name=playbook_doc.name,
        reference_doctype=reference_doctype,
        reference_name=reference_name,
        payload=payload,
        idempotency_key=idempotency_key,
        as_child=as_child
    )
    
def queue_resume_execution(execution_doc, response_body):
    emit_event(key=f"playbook_resume_{execution_doc.name}", argument={"response": response_body})

def run(playbook_name, reference_doctype, reference_name, payload, idempotency_key):
    # Native execution logic goes here
    # Idempotency check
    if frappe.db.exists("Playbook Execution", {"idempotency_key": idempotency_key}):
        return

    # Create Playbook Execution
    execution_doc = frappe.get_doc({
        "doctype": "Playbook Execution",
        "playbook": playbook_name,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "status": "success", # Native execution is currently a no-op, so mark as success
        "idempotency_key": idempotency_key
    })
    execution_doc.insert(ignore_permissions=True)
    frappe.db.commit()
